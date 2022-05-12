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

class modelclass:
    def __init__(self, classname, keyletter):
        self.classname = classname
        self.keyletter = keyletter
        self.attrlist = []
        self.identifiers = []
        self.identifiers.append(identifier("I"))
        self.is_associative = False

class attribute:
    def __init__(self, attrname, attrtype):
        self.name = attrname
        self.type = attrtype
        self.is_preferred = False
        self.references = []  # info about relationships formalized using this attribute
        
class identifier:
    def __init__(self, identnum):
        self.identnum = identnum
        self.attrs = []

# a resolvable link in a formalizing referential chain
# attributes which will formalize an association have 
# appended, the relationship numbers involved.
# resolution of a reference is achived by determining
# the attribute of the referred-to class in the relationship
# that will supply the value of this referential.

class attribute_relationship_reference:                 
    def __init__(self, relnum):
        self.relnum = relnum    # the number of a relationship 
        self.rel = 0            # the relationship instance matching the number
        self.isbinary = 0       # true if not a sub/supertype relationship
        self.rclass = 0         # when resolved, the referred-to class
        self.rphrase = ""       # when resolved, the relationship ohrase
        self.attr = 0           #
        self.resolved = False
              
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
                attrname = aline['name']
                attrtype = aline.get('type')
                if not attrtype:
                    attrtype = "undef"  # default.. for now
                
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
                            aref = attribute_relationship_reference(relnum)
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
                    print("non-referential: " + attr.name)
                    if attr.type == "undef":
                        if attr.name.endswith("ID"):
                            attr.type = "assigned_id"
                            print("update ID type for " + attr.name)
                else:
                    print("resolving: " + attr.name)
                    for reference in attr.references:
                        print(" found relation number: " + reference.relnum)
                        classresolved = False
                        for r in bin_rel_list:
                            if reference.relnum == r.rnum:
                                reference.rel = r
                                if c.is_associative:
                                    binref_resolve(reference, attr.name, r.tclass, r.tphrase)
                                    if not reference.resolved:
                                        binref_resolve(reference, attr.name, r.pclass, r.pphrase)
                                else
                                    aclass = r.pclass
                                    aphrase = r.pphrase
                                    if c == r.tclass:   # if reflexive, that's OK
                                        if r.is_reflexive:
                                            binref_resolve(reference, attr.name, r.tclass, r.pphrase)
                                        else:  # inconsistency in relationship definition: swap sides
                                            print("oops! - T&P mixed " + r.tclass.classname)
                                            aclass = r.tclass
                                            aphrase = r.tphrase
                                    binref_resolve(reference, attr.name, aclass, aphrase)
                                classresolved = True;
                                break
                        if not classresolved:
                            for r in sup_rel_list:
                                if reference.relnum == r.rnum:
                                    reference.rel = r
                                    if r.superclass.classname == c.classname:
                                        print("oops! - subsuper crossed up")
                                    reference.rclass = r.superclass
                                    classresolved = True
                        if classresolved:
                            print(attr.name + " resolved to class: " + reference.rclass.classname)
                            for ident in reference.rclass.identifiers:
                                for refattr in ident.attrs:
                                    if refattr.name == attr.name:
                                        print(attr.name + " is matched in " + reference.rclass.classname)
                                        reference.attr = refattr
                                        reference.resolved = True;
                                        break
                                if reference.resolved:
                                    break
                            if not reference.resolved:
                                ident = reference.rclass.identifiers[0]
                                if len(ident.attrs) == 1:
                                    reference.attr = ident.attrs[0]
                                    print("resolved with " + reference.attr.name + " of type " + reference.attr.type)
                                    reference.resolved = True
                if attr.type == "undef":
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
                        referred = ref.rclass
                        refattr = ref.attr
                        classname = referred.classname
                        attname = "Undefined"
                        atttype = "Integer"
                        if refattr:
                            attname = refattr.name
                            atttype = refattr.type
                        rel = ref.rel
                        rnum = rel.rnum
                        phrase = ""
                        if ref.isbinary:
                            phrase = "." + ref.rphrase
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
                    if not ref.resolved:
                        print(c.classname + " has unresolved " + attr.name + " ref ")
