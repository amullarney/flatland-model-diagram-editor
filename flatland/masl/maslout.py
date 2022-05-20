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


# class definitions:

# A modeled class discovered in the parse of the input file.
# These class descriptions are collected in a list.

class modelclass:
    def __init__(self, classname, keyletter):
        self.classname = classname
        self.keyletter = keyletter
        self.attrlist = []
        self.identifiers = []
        self.identifiers.append(identifier("I"))  # by convention, all classes have a primary identifier..
        self.formalizedassocs = []                # a list of associations formalized for this class


# A discovered attribute belonging to a class.
# The flatland parser presents these as a block of text
# The details of each line are separately parsed by a dedicated parser.

class attribute:
    def __init__(self, attrname, attrtype):
        self.name = attrname
        self.type = attrtype
        self.is_preferred = False  # True only if the attribute is designated as {I}
        self.references = []       # references which formalize relationships using this attribute


# A collection of one or more attributes whose values constitute an instance identifier.
# The identifier 'number' is I,I2,Ix... from the {I, I2, Ix} notation
       
class identifier:
    def __init__(self, identnum):
        self.identnum = identnum  # the 'number' of the identifier
        self.iattrs = []           # a list of contributing attributes


# a representation an instance of a binary association - which may include an associative class.           

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


# a representation of a super-subtype association        

class superassoc:
    def __init__(self, rnum, superclass):
        self.rnum = rnum
        self.superclass = superclass
        self.subclasslist = []
        self.classident = ""



# an instance of a resolved referential for a referential attribute:
# it records the 'target' class, attribute and phrase for one resolved relation.

class resolution:
    def __init__(self, rclass, rattr, rphrase, remark):
        self.rclass = rclass
        self.rattr = rattr
        self.rphrase = rphrase
        self.category = remark  # possible reporting key
 
        
# a list of referential attributes that must be matched in referred-to class(es) for one association

class formalizedassoc:
    def __init__(self, relnum):
        self.relnum = relnum
        self.rel = 0
        self.formalizers = []  # the attributes that formalize this relationship
        
# an [ attribute name - match pass/fail ] pair
# a set of these representing one referred-to class identifier is tested for match completeness

class match_candidate:
    def __init__(self, attr):
        self.attr = attr
        self.match = False

          

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
    # Each 'resolve' attempts to match a 'target' attribute in a referred-to.
    # Instances of resolution class are accumulated for each relationship resolved.
    # Note that associative class attributes (non-reflexive) will search both target classes.
    # Initial attempt at matching is by attribute name.
    # If name matching fails, some heuristics are attempted

    def resolve(self, attrname, refclass, phrase, identnum):
        # param identnum: referenced identifier group to match against
        ident = refclass.identifiers[0]  # default to using the primary identifier {I}
        if not identnum == "":
            for ident in refclass.identifiers:
                if ident.identnum == identnum:
                    break
        for attr in ident.iattrs:
            matched = False
            if attr.name == attrname:
                self.resolutions.append(resolution(refclass, attr, phrase, ""))
                matched = True
                print(attrname + " is matched in " + refclass.classname + " with " + phrase)
                break
        if not matched:
            for attr in ident.iattrs:
                if attr.name == "ID":
                    ltxt = refclass.classname.lower()
                    if attrname == ltxt.capitalize():
                        self.resolutions.append(resolution(refclass, attr, phrase, "ID"))
                        matched = True
                        print(attrname + " is matched with referred-to ID in " + refclass.classname + " with " + phrase)
                    break
        if not matched:
            # heuristic (1) : if there is only one {I} identifying attribute in the target, use it.
            if len(ident.iattrs) == 1 and self.resolutions == []:
                hres = resolution(refclass, ident.iattrs[0], phrase, "SingleIdent")
                self.resolutions.append(hres)
                matched = True
                print("heuristically SINGLY resolved with: " + hres.rattr.name + ", type: " + hres.rattr.type + " with " + hres.rphrase)
            else:
                # heuristic (2) : as above, but guessing that 'Name' is special
                for attr in ident.iattrs:
                    if attr.name == "Name" and self.resolutions == []:
                        hres = resolution(refclass, attr, phrase, "Name")
                        self.resolutions.append(hres)
                        matched = True
                        print("heuristically resolved with Name attribute: " + " type: " + hres.rattr.type + " with " + hres.rphrase)


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


# Utilities:

# see if all attributes in a candidate identifier can find matches in the formalizer list
# if all can be matched, this identifier is a good choice for formalization 
# special case: attribute matches referred-to class name, which offers an 'ID' identfier 

def identmatch(formalizers, ident, cname):
    for candidate in ident:
        for fattr in formalizers:
            if fattr.name == candidate.attr.name: 
                candidate.match = True
            if fattr.name == cname and candidate.attr.name == "ID":
                print(" *** matching " + candidate.attr.name + " to class " + cname + " ID attribute")
                candidate.match = True
                
# return the identifier choice which can match all its attributes in the formalization - or run out of choices.
# note: the match is tested 'from' the referred-to identifier; the formalization may span two classes in associative case.
# for each of a class's identifiers, prepare a 'candidate' list of [ attribute name,  matched ] pairs.
# after a match attempt, test for any failed match: if any, try for another identifier.

def matchident(formalizers, refclass):
    for ident in refclass.identifiers:
        attrlist = []
        for iattr in ident.iattrs:
            candidate = match_candidate(iattr)
            attrlist.append(candidate)
        ltxt = refclass.classname.lower()
        cname = ltxt.capitalize()
        identmatch(formalizers, attrlist, cname)
        useident = True
        for candidate in attrlist:
            if candidate.match == False:
                #print("no match found for " + candidate.attr.name)
                useident = False
                break
        if useident:
            break
    return ident


# The heart of the matter:

# This class's one and only method uses the Flatland parser to discover model classes and associations.
# MASL output is generated along the way in some cases: see text_file.write()
# Classes are discovered; their attribute text blocks are supplementally parsed for details;
# Associations are discovered and linked to their classes;
# Resolution of referential links is attempted:
# - this involves some work with class identifiers and referential attributes

class MaslOut:

    def __init__(self, xuml_model_path: Path, masl_file_path: Path):
        """Constructor"""
        self.logger = logging.getLogger(__name__)
        self.xuml_model_path = xuml_model_path
        self.masl_file_path = masl_file_path
        
        # Create a Parser which accepts just an attribute description line        
        att_parser = attr_parser("attr_grammar.peg", "attrdef" )

        self.logger.info("Parsing the model for MASL output")
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
        for aclass in self.subsys.classes:
            # Get the class name from the model; remove all white space
            txt = aclass['name']
            classname = txt.replace(" ","")
            text_file.write("  object " + classname +";\n")

            # Optional keyletter (class name abbreviation) after the class name?
            keyletter = str(aclass.get('keyletter'))
            if keyletter == "None":
                keyletter = classname

            classattrs = aclass['attributes']
            thisclass = modelclass(classname, keyletter)
            model_class_list.append(thisclass)
            #print("attribute info for : " + thisclass.classname)
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
                                if ref[0] == "O":  # OR 'relationships' are not 'associations'
                                    continue
                                relnum = ref[1:]
                            aref = attr_rel_ref(relnum)
                            thisattr.references.append(aref)

                classattrs.pop(0)  # done with this attribute line


        # Get all association data - this will be needed to type referential attributes
        # Create two lists of association data class types - binary and sub-super
        # Following Flatland convention, binary associations have 't' and 'p' 'sides'

        binary_rel_list = []
        subsup_rel_list = []
        
        for r in self.subsys.rels:  # for each discovered relationship..
            #print(r)
            numtxt = r['rnum']
            rnum = numtxt
            if not numtxt[0] == "R":
                if numtxt[0] == "O":
                    continue  # these are not formalizable associations: 
                              # see https://github.com/modelint/shlaer-mellor-metamodel/wiki/Ordinal-Relationship
                rnum = numtxt[1:]  # strip any U prefixes
            n = text_file.write("relationship " + rnum + " is ")

            if not 'superclass' in r.keys():  # treat binary associations here..
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
                binary_rel_list.append(bin_assoc_class)

                if tclass == pclass:
                    bin_assoc_class.is_reflexive = True

                n = text_file.write(tc + pcondtxt + pp + pmulttxt + pc + ",\n")
                n = text_file.write("  " + pc + tcondtxt + tp + tmulttxt + tc)
                
                aclass = 0
                aclass = r.get('assoc_cname')
                if aclass:
                    acname = aclass.replace(" ","")
                    #print(numtxt + " associative using " + acname)
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
                subsup_rel_list.append(saclass)
                subclasses = r['subclasses']
                sep = ""
                for s in subclasses:
                    cn = s.replace(" ","")
                    n = text_file.write(sep + cn)
                    sep = ", "
                    for aclass in model_class_list:
                        if aclass.classname == cn:
                            saclass.subclasslist.append(aclass)
                            for superattr in c.identifiers[0].iattrs:
                                if superattr.name == "ID":
                                    continue
                                found = False
                                for subattr in aclass.attrlist:
                                    if subattr.name == superattr.name:
                                        found = True
                                        break
                                if not found:
                                    newattr = attribute(superattr.name, superattr.type)
                                    newattr.references.append(attr_rel_ref(rnum))
                                    aclass.attrlist.append(newattr)
                                    print("added " + newattr.name + " to " + aclass.classname + " for " + rnum)
                                    
                            break
                n = text_file.write(");\n");
                
                
        # compute the formalizing attribute lists for each association, for each class.
        # each attribute may contribute to one or more formalized associations.
        # build a list of associations this class must formalize.
        # each list element is a list of the attribute(s) to be matched for the association.
        
        for c in model_class_list:
            for attr in c.attrlist:
                for ref in attr.references:
                    relnum = ref.relnum
                    found = False
                    for formr in c.formalizedassocs:
                        if formr.relnum == relnum:
                            found = True
                            break
                    if not found:
                        formr = formalizedassoc(relnum)
                        c.formalizedassocs.append(formr)
                    formr.formalizers.append(attr)
        
                
        # Now attempt to resolve the referential attributes
        # First step is to determine the appropriate identifier for the referred-to class:
        # i.e. the {In} which best matches the attributes required to formalize
               
        # when searching for best identifier, ensure longer attribute lists are tested first - more demanding!
        for c in model_class_list:
            idents = c.identifiers
            if len(idents) == 1:  # no choice!
                continue
            idents.sort(reverse = True, key = lambda identifier: len(identifier.iattrs) )
                
        # look for best referred-to class identifier for each formalized association
        # stash the identifier choice in the relationship for use in resolution.
                
        for c in model_class_list:
            for formr in c.formalizedassocs:
                attrstr = ""
                for fattr in formr.formalizers:
                    attrstr = attrstr + " " + fattr.name
                print("formalize " + formr.relnum + " needs: " + attrstr)

                for r in binary_rel_list:
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
                            if r.pclass == c:  # inconsistent ordering of relationship definition
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
                            #print(r.pclass.classname + " " + ident.identnum)
                            r.pclassident = ident.identnum
                        print(" --- ")
                        break
                for r in subsup_rel_list:
                    if formr.relnum == r.rnum:
                        formr.rel = r
                        ident = matchident(formr.formalizers, r.superclass)
                        #print(r.superclass.classname + " " + ident.identnum)
                        r.classident = ident.identnum
                        print(" +++ ")
                        break


        # with the best identifier now determined for each association, create the referential resolutions
        
        for c in model_class_list:
            print(" Defined class: " + c.classname)
            for attr in c.attrlist:
                if attr.references == []:
                    print("non-referential: " + attr.name + " " + attrtype)
                else:
                    print("resolving: " + attr.name)
                    for reference in attr.references:
                        print(" found relation number: " + reference.relnum)
                        for r in binary_rel_list:
                            if reference.relnum == r.rnum:
                                reference.rel = r
                                if r.is_associative and not r.is_reflexive:
                                    print("resolving associative reference for: " + c.classname)
                                    print("ident " + r.tclassident)
                                    reference.resolve(attr.name, r.tclass, r.tphrase, r.tclassident)
                                    print("and ident " + r.pclassident)
                                    reference.resolve(attr.name, r.pclass, r.pphrase, r.pclassident)
                                else:
                                    reference.resolve(attr.name, r.pclass, r.pphrase, r.pclassident)
                                if reference.resolutions == []:  # not resolved: last hope...
                                    # this would be the place to look for a single unresolved identifying attribute
                                    print("seeking to resolve " + attr.name)
                                    # to be addressed...
                                break

                        if reference.resolutions == []:  # not resolved; may be a sub-super association
                            for r in subsup_rel_list:
                                if reference.relnum == r.rnum:
                                    reference.rel = r
                                    if r.superclass.classname == c.classname:
                                        print("oops! - subsuper crossed up")
                                    reference.resolve(attr.name, r.superclass, "", r.classident)
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

        print("\nThe following referential attributes were unmatched in a referred-to class:")
        for c in model_class_list:
            for attr in c.attrlist:
                for ref in attr.references:
                    if ref.resolutions == []:
                        print(ref.rel.rnum + ": " + c.classname + " has unresolved " + attr.name + " ref ")
        print("\nThe following referentials matched a referred-to class ID identifying attribute (probably safe):")
        for c in model_class_list:
            for attr in c.attrlist:
                for ref in attr.references:
                    for res in ref.resolutions:
                        if res.category == "ID":
                            print(ref.rel.rnum + ": " + c.classname + " " + attr.name)
        print("\nThe following referentials matched a single referred-to identifying attribute (likely safe):")
        for c in model_class_list:
            for attr in c.attrlist:
                for ref in attr.references:
                    for res in ref.resolutions:
                        if res.category == "SingleIdent":
                            print(ref.rel.rnum + ": " + c.classname + " " + attr.name + " was matched to " + res.rattr.name)
        print("\nThe following referentials matched a referred-to class 'Name' identifying attribute (safe?):")
        for c in model_class_list:
            for attr in c.attrlist:
                for ref in attr.references:
                    for res in ref.resolutions:
                        if res.category == "Name":
                            print(ref.rel.rnum + ": " + c.classname + " " + attr.name)
                            