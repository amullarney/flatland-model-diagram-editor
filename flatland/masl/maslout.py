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
        self.identslist = []

class attribute:
    def __init__(self, attrname, attrtype):
        self.name = attrname
        self.type = attrtype
        self.is_preferred = False
        self.references = []
        self.resolved = []
        
class reference:
    def __init__(self, rel, isbinary, rclass):
        self.rel = rel
        self.isbinary = isbinary
        self.rclass = rclass
              
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
        for thisclass in self.subsys.classes:
            # Get the class name from the model; remove all white space
            txt = thisclass['name']
            cname = txt.replace(" ","")

            # There is an optional keyletter (class name abbreviation) displayed as {keyletter}
            # after the class name
            keyletter = str(thisclass.get('keyletter'))
            if keyletter == "None":
                keyletter = cname

            classattrs = thisclass['attributes']
            aclass = modelclass(cname, keyletter )
            model_class_list.append(aclass)
            while not classattrs == []:
                attrline = classattrs[0]
                # Now, parse this line for details
                attr_tree = att_parser.parse_attr(attrline)
                result = visit_parse_tree(attr_tree, AttrVisitor(debug=False))
                aline = {}
                for x in result:
                    aline.update(x)
                attrtype = "integer"  # default.. for now
                attrname = aline['name']
                attrtype = aline.get('type')
                if not attrtype:
                    attrtype = "undef"  # default.. for now
                
                thisattr = attribute(attrname, attrtype)
                aclass.attrlist.append(thisattr)
                
                info = aline.get('info')
                if info:
                    idents = info.get('idents')
                    refs = info.get('refs')
  
                if idents:
                    for i in idents:
                        if i == "I":
                            thisattr.preferred = True
                        else:
                            added = False
                            for l in aclass.identslist:
                                if l[0] == i:
                                    l[1].append(attrname)
                                    added = True
                            if not added:
                                alist = [attrname]
                                ilist = [i, alist]
                                aclass.identslist.append(ilist)

                if refs:
                    for ref in refs:
                        thisattr.references.append(ref)

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
                baclass = binassoc(rnum, tclass, tcond, tmult, tc, pp, pcond, pmult, pclass, aclass)
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
                    if attr.name.endswith("ID") and attr.type == "undef":
                        attr.type = "assigned_id"
                        print("update ID type for " + attr.name)
                else:
                    for ref in attr.references:
                        print("resolving: " + attr.name)
                        print(ref)
                        resolved = False
                        res = ""
                        for r in bin_rel_list:
                            if ref == r.rnum:
                                res = reference(r, True, r.pclass)
                                resolved = True;
                                break
                        if not resolved:
                            for r in sup_rel_list:
                                if ref == r.rnum:
                                    res = reference(r, False, r.superclass)
                        if res:
                            attr.resolved.append(res)
                            for a in res.rclass.attrlist:
                                if a.name == attr.name:
                                    print(a.name + " is matched in " + res.rclass.classname)
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
                if a.resolved:  # a referential
                    for res in a.resolved:
                        referred = res.rclass
                        phrase = " is_a "
                        if res.isbinary:
                            phrase = res.rel.pphrase
                        for ra in referred.attrlist:
                            if ra.name == a.name:
                               print("    " + a.name + " : ref ( " + ref + "." + phrase  + "." + referred.classname + "." + ra.name + " ) " + ra.type)
                               n = text_file.write(" referential : ( " + ref + "." + phrase  + "." + referred.classname + "." + ra.name + " ) " + ra.type)
                else:
                    print("    " + a.name + " : " + a.type)
                    
                text_file.write(";\n")

            if not c.identslist == []:
                line = "  identifier is "
                for l in c.identslist:
                    sep = ''
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
        text_file.close()
