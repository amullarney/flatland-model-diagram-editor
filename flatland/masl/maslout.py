"""
maslout.py – Generates MASL class and relationship definitions
"""

import sys
import logging
from pathlib import Path
from flatland.flatland_exceptions import ModelGrammarFileOpen, ModelInputFileOpen, ModelInputFileEmpty
from flatland.flatland_exceptions import FlatlandIOException, MultipleFloatsInSameBranch
from flatland.flatland_exceptions import LayoutParseError, ModelParseError
from flatland.input.model_parser import ModelParser
from collections import namedtuple
from flatland.input.nocomment import nocomment
from flatland.text.text_block import TextBlock
from arpeggio.cleanpeg import ParserPEG
from arpeggio import visit_parse_tree, NoMatch
from collections import namedtuple
from flatland.masl.attr_visitor import AttrVisitor

# A modeled class discovered in the parse of the input file.
# These class descriptions are collected in a list.

class modelclass:
    def __init__(self, classname, keyletter):
        self.classname = classname
        self.keyletter = keyletter
        self.attrlist = []
        self.identifiers = []
        self.identifiers.append(identifier("I"))
        self.is_associative = False

# A discovered attribute belonging to a class.
# The details are separately parsed by a dedicated parser.

class attribute:
    def __init__(self, attrname, attrtype):
        self.name = attrname
        self.type = attrtype
        self.is_preferred = False  # True only if the attribute is designated as {I}
        self.references = []       # info about relationships formalized using this attribute

# One or more attributes whose values constitute an instance identifier.
       
class identifier:
    def __init__(self, identnum):
        self.identnum = identnum  # the 'number' of the identifier
        self.attrs = []           # a list of contributing attributes

# A resolvable reference in a formalizing referential chain:
# attributes which formalize an association have, appended
# in the description, the relationship numbers involved.
# Resolution of a reference is achieved by determining
# the attribute of the referred-to class in the relationship
# that will supply the value of this referential.
# An attribute may participate in formalization of more than
# relationship.

class attr_rel_ref:                 
    def __init__(self, relnum):
        self.relnum = relnum    # the number of a relationship 
        self.resolutions = []   # an list of one or more referential resolutions

# A method which attempts to resolve a referential:
# Attempts to match 'target' attributes by name.
# If that fails, some heuristics are attempted

    def resolve(self, attrname, refclass, phrase):
        for attr in refclass.attrlist:
            matched = False
            if attr.name == attrname:
                self.resolutions.append(resolution(refclass, attr, phrase))
                matched = True
                print(attrname + " is matched in " + refclass.classname + " with " + phrase)
                break
        if not matched:
            for attr in refclass.attrlist:
                taken = False
                if attr.name == "ID":
                    self.resolutions.append(resolution(refclass, attr, phrase))
                    matched = True
                    print(attrname + " is matched with ID in " + refclass.classname + " with " + phrase)
                    break
        if not matched:
            ident1 = refclass.identifiers[0]  # heuristic: only 1 {I} identifying attribute?
            if len(ident1.attrs) == 1:
                hres = resolution(refclass, ident1.attrs[0], phrase)
                self.resolutions.append(hres)
                print("heuristically resolved with: " + hres.rattr.name + ", type " + hres.rattr.type + " with " + hres.rphrase)
            else:
                for iattr in ident1.attrs:
                    if iattr.name == "Name":
                        hres = resolution(refclass, iattr, phrase)
                        self.resolutions.append(hres)
                        print("heuristically resolved with Name: " + ", type " + hres.rattr.type + " with " + hres.rphrase)
                        


# an instance of a resolved referential; it records the 'target' class, attribute and phrase.

class resolution:
    def __init__(self, rclass, rattr, rphrase):
        self.rclass = rclass
        self.rattr = rattr
        self.rphrase = rphrase         
              
class binassoc:
    def __init__(self, rnum, tphrase, tcond, tmult, tclass, pphrase, pcond, pmult, pclass, aclass):
        self.rnum = rnum
        self.tphrase = tphrase
        self.tcond = tcond
        self.tmult = tmult
        self.tclass = tclass
        self.pphrase = pphrase
        self.pcond = pcond
        self.pmult = pmult
        self.pclass = pclass
        self.aclass = aclass
        self.is_reflexive = False

        
class superassoc:
    def __init__(self, rnum, superclass):
        self.rnum = rnum
        self.superclass = superclass
        self.subclasslist = []
            
class attr_parser:
    def __init__(self, grammar_file_name, root_rule_name):
        self.root_rule_name = root_rule_name
        self.grammar_file_name = grammar_file_name
        grammar_file = Path(__file__).parent.parent / 'masl' / grammar_file_name
            # Read the grammar file
        try:
            self.attr_grammar = nocomment(open(grammar_file, 'r').read())
        except OSError as e:
            raise ModelGrammarFileOpen(grammar_file)
        self.parser = ParserPEG(self.attr_grammar, self.root_rule_name, skipws=False, debug=False)

    def parse_attr(self, attr_text):
        try:
            parse_tree = self.parser.parse(attr_text)
        except NoMatch as e:
            raise ModelParseError(attr_text, e) from None
        return parse_tree


class MaslOut:

    def __init__(self, xuml_model_path: Path, masl_file_path: Path):
        """Constructor"""
        self.logger = logging.getLogger(__name__)
        self.xuml_model_path = xuml_model_path
        self.masl_file_path = masl_file_path
        
        # Create a Parser which accepts just an attribute description line        
        att_parser = attr_parser("attr_grammar.peg", "attrdef" )

        self.logger.info("Parsing the model")
        # Parse the model
        try:
            self.model = ModelParser(model_file_path=self.xuml_model_path, debug=False)
        except FlatlandIOException as e:
            sys.exit(e)
        try:
            self.subsys = self.model.parse()
        except ModelParseError as e:
            sys.exit(e)
        
        domain = self.subsys.name['subsys_name']
        print("Generating MASL domain definitions for " + domain)
        path = domain.replace(" ","") +".mod"
        text_file = open(path, "w")
        n = text_file.write("domain " + domain + " is\n")

        model_class_list = []        
        for mclass in self.subsys.classes:
            # Get the class name from the model; remove all white space
            txt = mclass['name']
            cname = txt.replace(" ","")
            text_file.write("  object " + cname +";\n")

            # There is an optional keyletter (class name abbreviation) displayed as {keyletter}
            # after the class name
            keyletter = str(mclass.get('keyletter'))
            if keyletter == "None":
                keyletter = cname

            classattrs = mclass['attributes']
            thisclass = modelclass(cname, keyletter)
            model_class_list.append(thisclass)
            print("attribute info for : " + thisclass.classname)
            while not classattrs == []:
                attrline = classattrs[0]
                # Now, parse this line for details
                attr_tree = att_parser.parse_attr(attrline)
                result = visit_parse_tree(attr_tree, AttrVisitor(debug=False))
                aline = {}
                for x in result:
                    aline.update(x)
                attrname = aline['aname']
                attrtype = aline.get('atype')
                if not attrtype:
                    attrtype = "undefinedType"  # default.. for now

                thisattr = attribute(attrname, attrtype)
                thisclass.attrlist.append(thisattr)
                print("attribute: " + attrname)
                
                info = aline.get('info')
                if info:
                    idents = info.get('idents')  # identifier(s) this attribute contributes to
                    refs = info.get('refs')      # relationship number(s) formalized
  
                    if idents:
                        for i in idents:
                            if i == "I":
                                thisattr.is_preferred = True
                            found = False
                            for ident in thisclass.identifiers:
                                if ident.identnum == i:
                                    found = True
                                    break
                            if not found:
                                ident = identifier(i)
                                thisclass.identifiers.append(ident)
                            ident.attrs.append(thisattr)
                            print("add to ident: " + ident.identnum + " " + thisattr.name)
                    if refs:
                        for ref in refs:
                            relnum = ref
                            if not ref[0] == "R":
                                relnum = ref[1:]
                            aref = attr_rel_ref(relnum)
                            print(aref.relnum)
                            thisattr.references.append(aref)

                classattrs.pop(0)  # done with this attribute line

        # Get all association data - this will be needed to type referential attributes
        # Create a set of association data classes for searching...

        bin_rel_list = []
        sup_rel_list = []
        
        for r in self.subsys.rels:  # r is the model data without any layout info
            #print(r)
            numtxt = r['rnum']
            rnum = numtxt
            if not numtxt[0] == "R":
                rnum = numtxt[1:]  # strip those U/O prefixes
            n = text_file.write("relationship " + rnum + " is ")
            if not 'superclass' in r.keys():
                tside = r['t_side']
                cn = tside['cname']
                tc = cn.replace(" ","")

                m = str(tside['mult'])
                tcond = False
                tcondtxt = " unconditionally "
                if 'c' in m:
                    tcond = True
                    tcondtxt = " conditionally "
                tmult = False
                tmulttxt = " one "
                if 'M' in m:
                    tmult = True
                    tmulttxt = " many "
                txt = tside['phrase']
                tp = txt.replace(" ","_")
               
                pside = r['p_side']
                cn = pside['cname']
                pc = cn.replace(" ","")
                
                m = str(pside['mult'])
                pcond = False
                pcondtxt = " unconditionally "
                if 'c' in m:
                    pcond = True
                    pcondtxt = " conditionally "
                pmult = False
                pmulttxt = " one "
                if 'M' in m:
                    pmult = True
                    pmulttxt = " many "
                txt = pside['phrase']
                pp = txt.replace(" ","_")

                aclass = r.get('assoc_cname')
                if aclass:
                    acn = aclass.replace(" ","")
                    for ac in model_class_list:
                        if ac.classname == acn:
                            ac.is_associative = True

                tclass = 0
                pclass = 0
                for c in model_class_list:
                    if c.classname == tc:
                        tclass = c
                    if c.classname == pc:
                        pclass = c
                baclass = binassoc(rnum, tp, tcond, tmult, tclass, pp, pcond, pmult, pclass, aclass)
                if tclass == pclass:
                    baclass.is_reflexive = True
                bin_rel_list.append(baclass)

                n = text_file.write(tc + pcondtxt + pp + pmulttxt + pc + ",\n")
                n = text_file.write("  " + pc + tcondtxt + tp + tmulttxt + tc + ";\n")
                


            else:
                s = r['superclass']
                cn = s.replace(" ","")
                n = text_file.write(cn + " is_a (")
                for c in model_class_list:
                    if c.classname == cn:
                        break
                saclass = superassoc(rnum, c)
                sup_rel_list.append(saclass)
                subclasses = r['subclasses']
                sep = ""
                for s in subclasses:
                    cn = s.replace(" ","")
                    n = text_file.write(sep + cn)
                    sep = ", "
                    for c in model_class_list:
                        if c.classname == cn:
                            saclass.subclasslist.append(c)
                            break
                n = text_file.write(");\n");
                

        for c in model_class_list:
            print(" Defined class: " + c.classname)
            for attr in c.attrlist:
                if attr.references == []:
                    print("non-referential: " + attr.name + " " + attrtype)
                else:
                    print("resolving: " + attr.name)
                    for reference in attr.references:
                        print(" found relation number: " + reference.relnum)
                        for r in bin_rel_list:
                            if reference.relnum == r.rnum:
                                reference.rel = r
                                if c.is_associative:
                                    print("resolving associative references for: " + c.classname)
                                    reference.resolve(attr.name, r.tclass, r.tphrase)
                                    if not r.is_reflexive:
                                        reference.resolve(attr.name, r.pclass, r.pphrase)
                                    for res in reference.resolutions:
                                        print(res.rphrase)
                                    print("done with associative")
                                else:
                                    aclass = r.pclass
                                    aphrase = r.pphrase
                                    if c == r.pclass:   # inconsistency in relationship definition: swap sides
                                        print("oops! - T&P mixed " + r.pclass.classname)
                                        aclass = r.tclass
                                        aphrase = r.tphrase
                                    reference.resolve(attr.name, aclass, aphrase)
                                if not reference.resolutions == []:
                                    break
                        if reference.resolutions == []:
                            for r in sup_rel_list:
                                if reference.relnum == r.rnum:
                                    reference.rel = r
                                    if r.superclass.classname == c.classname:
                                        print("oops! - subsuper crossed up")
                                    reference.resolve(attr.name, r.superclass, "")
                if attr.type == "undefinedType":
                    attr.type = "RefAttr"

                                
                    print("all refs scanned for: " + attr.name + " : " + attr.type)
            print(" end class\n")
        print("all classes done")
        

        """Output class definitions"""

        print(" ")
        text_file.write("\n")
        
        for c in model_class_list:
           
            cname = c.classname
            print("  object ", cname, " is")
            text_file.write("  object "+ cname + " is\n")
            
            for a in c.attrlist:
                p = ""
                if a.is_preferred:
                    p = " preferred "
                if not a.references:
                    print("    " + a.name + " : " + p + a.type)
                    text_file.write("    " + a.name + " : " + p + a.type + ";\n")
                else:
                    print("    " + a.name + " : " + p + "referential ( ")
                    text_file.write("    " + a.name + " : " + p + "referential ( ")
                    sep = ""
                    for ref in a.references:
                        classname = "Noclass"
                        attname = "Undefined"
                        atttype = "RefAttr"
                        phrase = ""
                        for res in ref.resolutions:
                            referred = res.rclass
                            refattr = res.rattr
                            classname = referred.classname
                            attname = refattr.name
                            atttype = refattr.type
                            if not res.rphrase == "":
                                phrase = "." + res.rphrase
                            rel = ref.rel
                            rnum = rel.rnum
                            print("   " + rnum + phrase  + "." + classname + "." + attname)
                            n = text_file.write(sep + rnum + phrase  + "." + classname + "." + attname)
                            sep = ", "
                    text_file.write(" ) " + atttype + ";\n")

            for ident in c.identifiers:
                sep = ''
                if ident.identnum == "I":
                    continue
                line = "  identifier is ( "
                text_file.write("    identifier is ( ")
                for attr in ident.attrs:
                    line = line + sep + attr.name
                    text_file.write(sep + attr.name)
                    sep = ", "
                text_file.write(" );\n")
                print(line)
            print("  end object;")
            text_file.write("  end object;\n")
            keyletter = c.keyletter
            print("pragma key letter ( ",'"' + keyletter + '"'," );\n")
            n = text_file.write("pragma key_letter ( "'"' + keyletter + '"'" );\n\n")

        text_file.write("end domain;\n")
        text_file.close()

        for c in model_class_list:
            for attr in c.attrlist:
                for ref in attr.references:
                    if ref.resolutions == []:
                        print(c.classname + " has unresolved " + attr.name + " ref ")
