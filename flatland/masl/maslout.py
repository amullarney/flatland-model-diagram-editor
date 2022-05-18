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
        #self.is_associative = False
        self.formalizedassocs = []

# A discovered attribute belonging to a class.
# The flatland parser presents these as a block of text
# The details of each line are separately parsed by a dedicated parser.

class attribute:
    def __init__(self, attrname, attrtype):
        self.name = attrname
        self.type = attrtype
        self.is_preferred = False  # True only if the attribute is designated as {I}
        self.references = []       # info about relationships formalized using this attribute

# One or more attributes whose values constitute an instance identifier.
# The identifier number is I,I2,Ix from the {I, I2, Ix} notation
       
class identifier:
    def __init__(self, identnum):
        self.identnum = identnum  # the 'number' of the identifier
        self.iattrs = []           # a list of contributing attributes

# A resolvable reference in a formalizing referential chain:
# attributes which formalize an association have, appended
# in their description, the relationship numbers involved.
# Resolution of a reference is achieved by determining
# the attribute of the referred-to class in the relationship
# that supplies the value of this referential attribute.
# An attribute may participate in formalization of more than
# one relationship.

class attr_rel_ref:  # attribute relationship reference               
    def __init__(self, relnum):
        self.relnum = relnum    # the number of a relationship 
        self.resolutions = []   # a list of one or more referential resolutions

# A method which attempts to resolve attribute referential references:
# Each 'resolve' attempts to match a 'target' attribute, by name, in a referred-to.
# Instances of resolution class are accumulated for each relationship resolved.
# Note that associative class attributes (non-reflexive) will search both target classes.
# If name matching fails, some heuristics are attempted
# In that associative case, guard against duplication of heuristic resolution - noduplicate:True

    def resolve(self, attrname, refclass, phrase, noduplicate, identnum):
        # param noduplicate: do not allow false matches (i.e. other than name match) for 2nd of associative pair.
        # param identnum: the one-based index specifying which referenced identifier group to match against
        ident = refclass.identifiers[0]  # default to using the primary identifier {I}
        if identnum == "I3":
            print("using I3 for " + refclass.classname)
        if not identnum == "":
            for ident in refclass.identifiers:
                if ident.identnum == identnum:
                    print("resolving " + attrname + " with ident " + ident.identnum)
                    break
        for attr in ident.iattrs:
            matched = False
            if attr.name == attrname:
                self.resolutions.append(resolution(refclass, attr, phrase))
                matched = True
                print(attrname + " is matched in " + refclass.classname + " with " + phrase)
                break
        if not matched:
            for attr in ident.iattrs:
                if attr.name == "ID":
                    ltxt = refclass.classname.lower()
                    if attrname == ltxt.capitalize():
                        self.resolutions.append(resolution(refclass, attr, phrase))
                        matched = True
                        print(attrname + " is matched with ID in " + refclass.classname + " with " + phrase)
                    break
        if not matched:
            # heuristic (1) : if there is only one {I} identifying attribute in the target, use it.
            if len(ident.iattrs) == 1 and self.resolutions == []:
                hres = resolution(refclass, ident.iattrs[0], phrase)
                self.resolutions.append(hres)
                matched = True
                print("heuristically singly resolved with: " + hres.rattr.name + ", type: " + hres.rattr.type + " with " + hres.rphrase)
            else:
                # heuristic (2) : as above, but guessing that 'Name' is special
                for attr in ident.iattrs:
                    if attr.name == "Name" and self.resolutions == []:
                        hres = resolution(refclass, attr, phrase)
                        self.resolutions.append(hres)
                        matched = True
                        print("heuristically resolved with Name attribute: " + " type: " + hres.rattr.type + " with " + hres.rphrase)

# see if all attributes in a candidate identifier can find matches in the formalizer list
# if all can be matched, this identifier is a good choice for formalization    
def iresolve(formalizers, ident, cname):
    for candidate in ident:
        for fattr in formalizers:
            if fattr.attr.name == candidate.attr.name: 
                candidate.match = True
            if fattr.attr.name == cname and candidate.attr.name == "ID":
                print(" *** matching " + candidate.attr.name + " to class " + cname + " ID attribute")
                candidate.match = True
                
# return the identifier which can match all its attributes in the formalization - or bottom out.
def matchident(formalization, refclass):
    for ident in refclass.identifiers:
        print("trying " + ident.identnum + " for " + refclass.classname)
        attrlist = []
        for iattr in ident.iattrs:
            cand = match_candidate(iattr)
            print(iattr.name)
            attrlist.append(cand)
        ltxt = refclass.classname.lower()
        cname = ltxt.capitalize()
        iresolve(formalization, attrlist, cname)
        useident = True
        for candidate in attrlist:
            if candidate.match == False:
                print("mismatch " + candidate.attr.name)
                useident = False
                break
        if useident:
            break
    return ident


# an attribute name - match pass/fail pair
class match_candidate:
    def __init__(self, attr):
        self.attr = attr
        self.match = False

# an instance of a resolved referential for a referential attribute:
# it records the 'target' class, attribute and phrase for one resolved relation.

class resolution:
    def __init__(self, rclass, rattr, rphrase):
        self.rclass = rclass
        self.rattr = rattr
        self.rphrase = rphrase
        
# gathers a list of referential attributes that must be matched in referred-to class(es)
class formalizedassoc:
    def __init__(self, relnum):
        self.relnum = relnum
        self.rel = 0
        self.formalizers = []
        
class formalization:
    def __init__(self, attr):
        self.attr = attr
        self.resolutions = []

# represents an instance of a binary association - which may include an associative class.           
class binassoc:
    def __init__(self, rnum, tphrase, tcond, tmult, tclass, pphrase, pcond, pmult, pclass):
        self.rnum = rnum
        self.tphrase = tphrase
        self.tcond = tcond
        self.tmult = tmult
        self.tclass = tclass
        self.pphrase = pphrase
        self.pcond = pcond
        self.pmult = pmult
        self.pclass = pclass
        self.aclass = 0
        self.is_associative = False
        self.is_reflexive = False
        self.tclassident = ""  # identifier index for formalization, if set
        self.pclassident = ""  # identifier index for formalization, if set

# an instance of a super-subtype association        
class superassoc:
    def __init__(self, rnum, superclass):
        self.rnum = rnum
        self.superclass = superclass
        self.subclasslist = []
        self.classident = ""
            
# a parser for an attribute description
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

# This classes one and only method uses the Flatland parser to discover model classes and associations.
# MASL output is generated along the way in some cases: see text_file.write()
# Associations are linked to their classes;
# Class attribute text blocks are parsed for details;
# Resolution of referential links is attempted;

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
            #ltxt = txt.lower()
            #ctxt = ltxt.capitalize()
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
                # Now, parse this attribute text line for details
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
                    refs = info.get('refs')      # relationship number(s) formalized by this attribute
  
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
                            ident.iattrs.append(thisattr)
                            #print("add to ident: >" + ident.identnum + "< " + thisattr.name)
                    if refs:
                        for ref in refs:
                            relnum = ref
                            if not ref[0] == "R":
                                if ref[0] == "O":
                                    continue
                                relnum = ref[1:]
                            aref = attr_rel_ref(relnum)
                            #print(aref.relnum)
                            thisattr.references.append(aref)
                            found = False
                            for formr in thisclass.formalizedassocs:
                                if formr.relnum == relnum:
                                    found = True
                                    break
                            if not found:
                                formr = formalizedassoc(relnum)
                                thisclass.formalizedassocs.append(formr)
                            fattr = formalization(thisattr)
                            formr.formalizers.append(fattr)
                            

                classattrs.pop(0)  # done with this attribute line

        # Get all association data - this will be needed to type referential attributes
        # Create two lists of association data class types - binary and sub-super
        # Following Flatland convention, binary associations have 't' and 'p' 'sides'

        bin_rel_list = []
        sup_rel_list = []
        
        for r in self.subsys.rels:  # for each discovered relationship..
            #print(r)
            numtxt = r['rnum']
            rnum = numtxt
            if not numtxt[0] == "R":
                if numtxt[0] == "O":
                    continue  # these are not formalizable associations: see https://github.com/modelint/shlaer-mellor-metamodel/wiki/Ordinal-Relationship
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
                
                tclass = 0
                pclass = 0
                for c in model_class_list:
                    if c.classname == tc:
                        tclass = c
                    if c.classname == pc:
                        pclass = c

                bin_assoc_class = binassoc(rnum, tp, tcond, tmult, tclass, pp, pcond, pmult, pclass)
                bin_rel_list.append(bin_assoc_class)

                if tclass == pclass:
                    bin_assoc_class.is_reflexive = True

                n = text_file.write(tc + pcondtxt + pp + pmulttxt + pc + ",\n")
                n = text_file.write("  " + pc + tcondtxt + tp + tmulttxt + tc)
                
                aclass = 0
                aclass = r.get('assoc_cname')
                if aclass:
                    acname = aclass.replace(" ","")
                    print(numtxt + " associative using " + acname)
                    for c in model_class_list:
                        if c.classname == acname:
                            assoc_class = c
                            bin_assoc_class.aclass = assoc_class
                            bin_assoc_class.is_associative = True
                            break
                            n = text_file.write(" using " + bin_assoc_class.aclass.classname)

                n = text_file.write(";\n")

            else:  # this is a sub-supertype association
            
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
                
        # Now attempt to resolve the referential attributes
        # The tricky issue is to find the appropriate identifier set.
        
        
        # when searching for best identifier, start with one with longest attribute list - most demanding!
        for c in model_class_list:
            idents = c.identifiers
            if len(idents) == 1:  # no choice!
                continue
            # ideally, a complete sort by descending number of identifying attributes... but, hey..
            i = 0
            longest = 1
            pos = 0
            for ident in idents:
                l = len(ident.iattrs)
                if l > longest:
                    longest = l
                    pos = i
                i = i + 1
            if longest > 1:
                x = idents.pop(pos)
                idents.insert(0, x)
                
        
        for c in model_class_list:
            for formr in c.formalizedassocs:
                attrstr = ""
                for fattr in formr.formalizers:
                    attrstr = attrstr + " " + fattr.attr.name
                print("formalize " + formr.relnum + " needs: " + attrstr)
                for r in bin_rel_list:
                    if formr.relnum == r.rnum:
                        formr.rel = r
                        if r.is_associative and not r.is_reflexive: # two half-associations involved...
                            ident = matchident(formr.formalizers, r.tclass)
                            print(r.tclass.classname + " " + ident.identnum)
                            r.tclassident = ident.identnum
                            ident = matchident(formr.formalizers, r.pclass)
                            print(r.pclass.classname + " " + ident.identnum)
                            r.pclassident = ident.identnum
                        else:
                            if r.pclass == c:  # inconsistent ordering of definition
                                print("swapping relationship sides for " + r.rnum)
                                aclass = r.pclass
                                aphrase = r.pphrase
                                acond = r.pcond
                                amult = r.pmult
                                r.pclass = r.tclass
                                r.pphrase = r.tphrase
                                r.pcond = r.tcond 
                                r.pmult = r.tmult
                                r.tclass = aclass
                                r.tphrase = aphrase
                                r.tcond = acond
                                r.tmult = amult
                            ident = matchident(formr.formalizers, r.pclass)
                            print(r.pclass.classname + " " + ident.identnum)
                            r.pclassident = ident.identnum
                        print(" --- ")
                        break
                for r in sup_rel_list:
                    if formr.relnum == r.rnum:
                        formr.rel = r
                        ident = matchident(formr.formalizers, r.superclass)
                        print(r.superclass.classname + " " + ident.identnum)
                        r.classident = ident.identnum
                        print(" +++ ")
                        break
               
                        
                    



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
                                if r.is_associative and not r.is_reflexive:
                                    print("resolving associative reference for: " + c.classname)
                                    print("ident " + r.tclassident)
                                    reference.resolve(attr.name, r.tclass, r.tphrase, False, r.tclassident)
                                    print("and ident " + r.pclassident)
                                    reference.resolve(attr.name, r.pclass, r.pphrase, True, r.pclassident)
                                else:
                                    # take a guess at picking the "other end" class in this binary association
                                    aclass = r.pclass
                                    aphrase = r.pphrase
                                    if c == r.pclass:   # inconsistency in relationship definition: swap sides
                                        #print("oops! - T&P mixed " + r.pclass.classname)
                                        aclass = r.tclass
                                        aphrase = r.tphrase
                                    reference.resolve(attr.name, aclass, aphrase, False, r.pclassident)
                                    if reference.resolutions == []:
                                        # heuristic (2) : look for an unmatched identifier in target, for this relationship
                                        #print("out of ideas for: " + c.classname + " " + attr.name + " " + r.rnum)
                                        takenlist = []
                                        for cattr in c.attrlist:
                                            for ref in cattr.references:
                                                if ref.relnum == r.rnum:
                                                    for res in ref.resolutions:
                                                        takenlist.append(res.rattr.name)
                                        #print(takenlist)
                                        ident1 = aclass.identifiers[0]
                                        for iattr in ident1.iattrs:  # try to find an unmatched identifying attribute...
                                            candidate = iattr.name
                                            for taken in takenlist:
                                                if iattr.name == taken:
                                                    candidate = ""
                                                    break
                                            if not candidate == "":
                                                #print("well, maybe: " + candidate)
                                                for iattr in ident1.iattrs:
                                                    if iattr.name == candidate:
                                                        res = resolution(aclass, iattr, aphrase)
                                                        reference.resolutions.append(res)
                                break
                        if reference.resolutions == []:  # not resolved; may be a sub-super association
                            for r in sup_rel_list:
                                if reference.relnum == r.rnum:
                                    reference.rel = r
                                    if r.superclass.classname == c.classname:
                                        print("oops! - subsuper crossed up")
                                    reference.resolve(attr.name, r.superclass, "", False, r.classident)
                if attr.type == "undefinedType":
                    attr.type = "RefAttr"

                                
                    #print("all refs scanned for: " + attr.name + " : " + attr.type)
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
                            #atttype = refattr.type # don't bother with this
                            if not res.rphrase == "":
                                phrase = "." + res.rphrase
                            rel = ref.rel
                            rnum = rel.rnum
                            print("   " + rnum + phrase  + "." + classname + "." + attname)
                            n = text_file.write(sep + rnum + phrase  + "." + classname + "." + attname)
                            sep = ", "
                    text_file.write(" ) " + atttype + ";\n")

            # output identifier groups for all non-preferred
            
            for ident in c.identifiers:
                sep = ''
                if ident.identnum == "I":  # skip this group of 'preferred' identifiers
                    continue
                line = "  identifier is ( "
                text_file.write("    identifier is ( ")
                for attr in ident.iattrs:
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
        
        # report unresolved referentials

        for c in model_class_list:
            for attr in c.attrlist:
                for ref in attr.references:
                    if ref.resolutions == []:
                        print(c.classname + " has unresolved " + attr.name + " ref ")
