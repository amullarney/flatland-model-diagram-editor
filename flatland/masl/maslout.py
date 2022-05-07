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

class attribute:
    def __init__(self, attrname, attrtype):
        self.name = attrname
        self.type = attrtype
        self.is_preferred = False
        self.references = []
        
class identifier:
    def __init__(self, identnum):
        self.identnum = identnum
        self.attrs = []

class attref:
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
            thisclass = modelclass(cname, keyletter )
            model_class_list.append(thisclass)
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
                    idents = info.get('idents')
                    refs = info.get('refs')
  
                    if idents:
                        for i in idents:
                            if i == "I":
                                thisattr.preferred = True
                            found = False
                            for ident in thisclass.identifiers:
                                if ident.identnum == i:
                                    found = True
                            if not found:
                                ident = identifier(i)
                            ident.attrs.append(thisattr)
                    if refs:
                        for ref in refs:
                            aref = attref(ref)
                            thisattr.references.append(aref)

                classattrs.pop(0)  # done with this attribute line

        # Get all association data - this will be needed to type referential attributes
        # Create a set of association data classes for searching...

        bin_rel_list = []
        sup_rel_list = []
        
        for r in self.subsys.rels:  # r is the model data without any layout info
            #print(r)
            rnum = r['rnum']
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
                        print(reference.ref)
                        classresolved = False
                        for r in bin_rel_list:
                            if reference.ref == r.rnum:
                                reference.rel = r
                                xclass = r.pclass
                                if xclass.classname == c.classname:
                                    print("oops! - T&P mixed " + r.tclass.classname)
                                    xclass = r.tclass
                                reference.rclass = xclass
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
                            print("resolving to class: " + reference.rclass.classname)
                            for refattr in reference.rclass.attrlist:
                                if refattr.name == attr.name:
                                    print(attr.name + " is matched in " + reference.rclass.classname)
                                    reference.attr = refattr
                                    if refattr.references:
                                        print("this reference chains")
                                    break
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
                text_file.write("    " + a.name)
                if a.references:  # a referential
                    for res in a.references:
                        referred = res.rclass
                        attname = ""
                        atttype = "unk"
                        ra = res.attr
                        if ra:
                            attname = ra.name
                            atttype = ra.type
                        phrase = ""
                        classname = ""
                        rnum = "UOxx"
                        if res.isbinary:
                            phrase = "." + res.rel.pphrase
                            classname = referred.classname + "."
                        else:
                            if res.rel:
                                rnum = res.rel.rnum
                        print("    " + a.name + " : ref ( " + rnum + phrase  + "." + classname + attname + " ) " + atttype)
                        n = text_file.write(" referential : ( " + rnum + phrase  + "." + classname + attname + " ) " + atttype)
                else:
                    print("    " + a.name + " : " + a.type)
                    
                text_file.write(";\n")

            if not c.identifiers == []:
                for l in c.identifiers:
                    sep = ''
                    line = "  identifier is "
                    text_file.write("    identifier is ( ")
                    for a in l[1]:
                        line = line + sep + a
                        text_file.write(sep + a)
                        sep = ", "
                    text_file.write(" );\n")
                    print(line)
            print("  end object;")
            text_file.write("  end object;\n")
            keyletter = c.keyletter
            print("pragma key letter ( ",'"' + keyletter + '"'," );\n")
            n = text_file.write("pragma key_letter ( "'"' + keyletter + '"'" );\n\n")

        text_file.write("end domain;\n")
        text_file.close()              sep = ", "
                    text_file.write(" );\n")
                    print(line)
            print("  end object;")
            text_file.write("  end object;\n")
            keyletter = c.keyletter
            print("pragma key letter ( ",'"' + keyletter + '"'," );\n")
            n = text_file.write("pragma key_letter ( "'"' + keyletter + '"'" );\n\n")

        text_file.write("end domain;\n")
        text_file.close()
