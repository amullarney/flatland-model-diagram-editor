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

class attref:                 # a resolvable link in a formalizing referential chain
    def __init__(self, ref):
        self.ref = ref
        self.rel = 0
        self.isbinary = 0
        self.rclass = 0
        self.attr = 0
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
                
                info = aline.get('info')
                if info:
                    idents = info.get('idents')  # identifier(s) this attribute contributes to
                    refs = info.get('refs')      # relationship number(s) formalized
  
                    if idents:
                        for i in idents:
                            if i == "I":
                                thisattr.preferred = True
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
                            aref = attref(relnum)
                            #print(aref.ref)
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
                rnum = numtxt[1:]
            n = text_file.write("relationship " + rnum + " is ")
            if not 'superclass' in r.keys():
                tside = r['t_side']
                cn = tside['cname']
                tc = cn.replace(" ","")
                n = text_file.write(tc)
                m = str(tside['mult'])
                tcond = False
                if 'c' in m:
                    tcond = True
                    n = text_file.write(" conditionally ")
                else:
                    n = text_file.write(" unconditionally ")
                txt = tside['phrase']
                tp = txt.replace(" ","_")
                n = text_file.write(tp)
                
                pside = r['p_side']
                cn = pside['cname']
                pc = cn.replace(" ","")
                tmult = False
                if 'M' in m:
                    tmult = True
                    n = text_file.write(" many ")
                else:
                    n = text_file.write(" one ")
                n = text_file.write(pc + ",\n")
                
                n = text_file.write("  " + pc)
                m = str(pside['mult'])
                pcond = False
                if 'c' in m:
                    pcond = True
                    n = text_file.write(" conditionally ")
                else:
                    n = text_file.write(" unconditionally ")
                txt = pside['phrase']
                pp = txt.replace(" ","_")
                n = text_file.write(pp)
                pmult = False
                if 'M' in m:
                    pmult = True
                    n = text_file.write(" many ")
                else:
                    n = text_file.write(" one ")
                n = text_file.write(pc)
                aclass = r.get('assoc_cname')
                if aclass:
                    acn = aclass.replace(" ","")
                    n = text_file.write(" using " + acn + ";\n")
                else:
                    n = text_file.write(";\n");
                tclass = 0
                pclass = 0
                for c in model_class_list:
                    if c.classname == tc:
                        tclass = c
                    if c.classname == pc:
                        pclass = c
                baclass = binassoc(rnum, tclass, tcond, tmult, tclass, pp, pcond, pmult, pclass, aclass)
                bin_rel_list.append(baclass)


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
                    if attr.name.endswith("ID") and attr.type == "undef":
                        attr.type = "assigned_id"
                        print("update ID type for " + attr.name)
                else:
                    print("resolving: " + attr.name)
                    for reference in attr.references:
                        print(" found relation number: " + reference.ref)
                        classresolved = False
                        for r in bin_rel_list:
                            if reference.ref == r.rnum:
                                reference.rel = r
                                xclass = r.pclass
                                if xclass.classname == c.classname:
                                    print("oops! - T&P mixed " + r.tclass.classname)
                                    xclass = r.tclass
                                reference.rclass = xclass
                                reference.isbinary = True;
                                classresolved = True;
                                break
                        if not classresolved:
                            for r in sup_rel_list:
                                if reference.ref == r.rnum:
                                    reference.rel = r
                                    if r.superclass.classname == c.classname:
                                        print("oops! - subsuper crossed up")
                                    reference.rclass = r.superclass
                                    classresolved = True
                        if classresolved:
                            print("resolved to class: " + reference.rclass.classname)
                            for ident in reference.rclass.identifiers:
                                for refattr in ident.attrs:
                                    if refattr.name == attr.name:
                                        print(attr.name + " is matched in " + reference.rclass.classname)
                                        reference.attr = refattr
                                        reference.resolved = True;
                                        #if refattr.references:
                                            #print("this reference chains")
                                        break
                                if reference.resolved:
                                    break
                            if not reference.resolved:
                                ident = reference.rclass.identifiers[0]
                                if len(ident.attrs) == 1:
                                    reference.attr = ident.attrs[0]
                                    print("resolved with " + reference.attr.name + " of type " + reference.attr.type)
                                    reference.resolved = True
                    print("all refs scanned for: " + attr.name + " : " + attr.type)
            print(" end class\n")
        print("all classes done")
        

        """Output class definitions"""

        print(" ")
        
        for c in model_class_list:
           
            cname = c.classname
            print("  object ", cname, " is")
            text_file.write("  object "+ cname + " is\n")
            
            for a in c.attrlist:
                atttype = ""
                if not a.references:
                    print("    " + a.name + " : " + a.type)
                    text_file.write("    " + a.name + " : " + a.type + ";\n")
                else:
                    print("    " + a.name + " referential : ( ")
                    text_file.write("    " + a.name + " referential : ( ")
                    for eachref in a.references:
                        ref = eachref
                        while ref:
                            print(" now looking at: " + ref.rclass.classname)
                            referred = ref.rclass
                            refattr = ref.attr
                            classname = referred.classname
                            attname = refattr.name
                            atttype = refattr.type
                            rel = ref.rel
                            rum = rel.rnum
                            phrase = ""
                            sep = ""
                            if ref.isbinary:
                                phrase = "." + rel.pphrase
                            print("   " + rnum + phrase  + "." + classname + attname + " ")
                            n = text_file.write(rnum + phrase  + "." + classname + attname + " ")
                            if refattr.references:
                                ref = refattr.references[0]
                                print(" jumping to " + ref.rclass.classname)
                            else:
                                break
                        
                    text_file.write(" ) " + atttype + ";\n")

            for ident in c.identifiers:
                sep = ''
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