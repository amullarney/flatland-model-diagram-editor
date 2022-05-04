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

Attrtuple = namedtuple('attrline', 'attrdef')

class binassoc:
    def __init__(self, rnum, tphrase, tmult, tclass, pphrase, pmult, pclass, aclass ):
        self.rnum = rnum
        self.tphrase = tphrase
        self.tmult = tmult
        
class attr_parser:
    def __init__(self, grammar_file_name, root_rule_name ):
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
        masldomain = domain.replace(" ","") +".mod"
        print("Generating MASL domain definitions for " + domain + " to file: ", masldomain)
 
        text_file = open(masldomain, "w")
        n = text_file.write("domain " + domain + " is\n")
        for c in self.subsys.classes:
            # Get the class name from the model; remove all white space
            cname = c['name']
            maslname = cname.replace(" ","")
            text_file.write("  object "+ maslname + ";\n")

        print("    MASL relationships - written to file")
        
        # Get all association data - this will be needed to type referential attributes
        # TBD - create a set of association data classes for searching...
        bin_rel_list = []
        for r in self.subsys.rels:  # r is the model data without any layout info
            #print(r)
            rnum = r['rnum']
            n = text_file.write("relationship " + rnum + " is ")
            if not 'superclass' in r.keys():
                tside = r['t_side']
                cn = tside['cname']
                ct = cn.replace(" ","")
                n = text_file.write(ct)
                m = str(tside['mult'])
                if 'c' in m:
                    n = text_file.write(" conditionally ")
                else:
                    n = text_file.write(" unconditionally ")
                txt = tside['phrase']
                pt = txt.replace(" ","_")
                pside = r['p_side']
                cn = pside['cname']
                cp = cn.replace(" ","")
                n = text_file.write(pt)
                if 'M' in m:
                    n = text_file.write(" many ")
                else:
                    n = text_file.write(" one ")
                n = text_file.write(cp + ",\n")
                
                n = text_file.write("  " + cp)
                m = str(pside['mult'])
                if 'c' in m:
                    n = text_file.write(" conditionally ")
                else:
                    n = text_file.write(" unconditionally ")
                txt = pside['phrase']
                pp = txt.replace(" ","_")
                n = text_file.write(pp)
                if 'M' in m:
                    n = text_file.write(" many ")
                else:
                    n = text_file.write(" one ")
                n = text_file.write(cp)
                if 'assoc_mult' in r.keys():
                    ac = r['assoc_cname']
                    maslname = ac.replace(" ","")
                    n = text_file.write(" using " + maslname + ";\n")
                else:
                    n = text_file.write(";\n");
                #bin_rel_list.append([rnum,

            else:
                s = r['superclass']
                cn = s.replace(" ","")
                n = text_file.write(cn + " is_a (")
                subclasses = r['subclasses']
                sep = ""
                for s in subclasses:
                    cn = s.replace(" ","")
                    n = text_file.write(sep + cn)
                    sep = ", "
                n = text_file.write(");\n");
                


        # Output all of the classes
        self.logger.info("Outputting MASL classes")

        """Output class definitions"""

        print("    MASL class definitions - to console, for now")
        print(" ")
        
        for c in self.subsys.classes:

            # Get the class name from the model
            cname = c['name']
            masl_classname = cname.replace(" ","")
            print("  object ", masl_classname, " is")
            text_file.write("  object "+ masl_classname + " is\n")
            
            self.logger.info(f'Processing class: {cname}')

            # There is an optional keyletter (class name abbreviation) displayed as {keyletter}
            # after the class name
            keyletter = str(c.get('keyletter'))

            # Class might be imported. If so add a reference to subsystem or TBD in attr compartment
            import_subsys_name = c.get('import')
            if not import_subsys_name:
                internal_ref = []
            elif import_subsys_name.endswith('TBD'):
                internal_ref = [' ', f'{import_subsys_name.removesuffix(" TBD")} subsystem', '(not yet modeled)']
            else:
                internal_ref = [' ', f'(See {import_subsys_name} subsystem)']

            ac = c['attributes']
            #print("ac_attrs: ", ac)
            list_of_ident_lists = []
            while not ac == []:
                attrline = ac[0]
                # Now, parse this line for details
                attr_tree = att_parser.parse_attr(attrline)
                result = visit_parse_tree(attr_tree, AttrVisitor(debug=False))
                #print(result)
                attrtype =""
                for next in result:
                    if 'name' in next.keys():
                        attrname = next['name']
                        print(attrname)
                        text_file.write("    " + attrname + " : ")
                    if 'type' in next.keys():
                        attrtype = next['type']
                    if 'info' in next.keys():
                        info = next['info']
                        #print(info)
                        for inf in info:
                            if 'idents' in inf.keys():
                                idents = inf['idents']
                                for i in idents:
                                    if i == "I":
                                        #print(" preferred ")
                                        text_file.write(" preferred ")
                                    else:
                                        added = False
                                        for l in list_of_ident_lists:
                                            if l[0] == i:
                                                l[1].append(attrname)
                                                added = True
                                        if not added:
                                            alist = [attrname]
                                            ilist = [i, alist]
                                            list_of_ident_lists.append(ilist)
                            if 'refs' in inf.keys():
                                refs = inf['refs']
                                #for ref in refs:
                                    #print(" referential: " + ref)
                if attrtype == "":
                    attrtype = "integer" # for now...
                text_file.write(" " + attrtype)
                text_file.write(";\n")

                del attr_tree  # done with this attribute parse
                ac.pop(0)
            if not list_of_ident_lists == []:
                for l in list_of_ident_lists:
                    print("identifier is ( ")
                    sep = ''
                    text_file.write("    identifier is ( ")
                    for a in l[1]:
                        print(a + ",")
                        text_file.write(sep + a)
                        sep = ", "
                    text_file.write(" );\n")
                del list_of_ident_lists
            print("  end object;")
            text_file.write("  end object;\n")
            if "None" in keyletter:
                keyletter = masl_classname
            print("pragma key letter ( ",'"' + keyletter + '"'," );")
            n = text_file.write("pragma key_letter ( "'"' + keyletter + '"'" );\n\n")

        text_file.write("end domain;\n")
        text_file.close()

