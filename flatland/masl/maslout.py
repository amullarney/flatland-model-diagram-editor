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
        self.attrlist = []                        # list of discovered attributes
        self.identifiers = []                     # one or more denoted attributes
        self.identifiers.append(identifier("I"))  # by convention, all classes have a primary identifier..
        self.formalizations = []                  # a list of associations formalized for this class


# A discovered attribute belonging to a class.
# The flatland parser presents these as a block of text
# The details of each line are separately parsed by a dedicated parser.

class attribute:
    def __init__(self, attrname, attrtype):
        self.name = attrname
        self.type = attrtype
        self.is_preferred = False  # True only if the attribute is designated as {I}
        self.references = []       # references which formalize relationships using this attribute
        self.resolutions = []      # resolved referential linkage
        self.synthtype = False     # missing type name is synthesized from attribute/class name


# A collection of one or more attributes whose values constitute an instance identifier.
# The identifier 'number' is I,I2,Ix... from the {I, I2, Ix} notation
       
class identifier:
    def __init__(self, identnum):
        self.identnum = identnum  # the 'number' of the identifier: e.g. I / I2 /..
        self.iattrs = []           # a list of contributing attributes


# a representation an instance of a binary association - which may include an associative class.           

class binary_association:
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

class subsuper_association:
    def __init__(self, rnum, superclass):
        self.rnum = rnum
        self.superclass = superclass
        self.subclasslist = []
        self.classident = ""


# an instance of a resolved referential for a referential attribute:
# it records the 'target' class, attribute and phrase for one resolved relation.

class resolution:
    def __init__(self, rclass, rattr, rnum, rphrase, remark):
        self.rclass = rclass
        self.rattr = rattr
        self.rnum = rnum
        self.rphrase = rphrase
        self.category = remark  # reporting key, if other than exact name match
 
        
# a list of referential attributes that must be matched in referred-to class(es) for one association

class formalization:
    def __init__(self, relnum):
        self.relnum = relnum
        self.rel = 0
        self.formalizers = []  # the attributes that formalize this relationship

    # attempt to match each attribute in the formalizer list with an an attribute in the chosen identifier

    def resolve(self, refclass, phrase, identnum):
        ident = refclass.identifiers[0]
        if not identnum == "":
            for ident in refclass.identifiers:
                if ident.identnum == identnum:
                    break
        for rattr in self.formalizers:
            matched = False
            for iattr in ident.iattrs:
                if rattr.name == iattr.name:
                    print(self.relnum + ": formalization match: " + rattr.name + " to " + iattr.name + " in " + refclass.classname)
                    rattr.resolutions.append(resolution(refclass, iattr, self.relnum, phrase, "matched"))
                    matched = True
                    break
            if not matched:
                # if the attribute name matches the referred-to class and it has an 'ID' attribute, consider matched.
                for iattr in ident.iattrs:
                    if iattr.name == "ID":
                        ltxt = refclass.classname.lower()
                        if rattr.name == ltxt.capitalize():
                            #print(self.relnum + ": formalization match: " + rattr.name + " to ID in "  + refclass.classname)
                            rattr.resolutions.append(resolution(refclass, iattr, self.relnum, phrase, "ID"))
                            matched = True
                            break
                            
    # look for a single unmatched referential; 
    # if found, look for a single unmatched identifying attribute to be considered a match.
    
    def resolve2(self, refclass, phrase, identnum):                            
        ident = refclass.identifiers[0]
        if not identnum == "":
            for ident in refclass.identifiers:
                if ident.identnum == identnum:
                    break

        # look for unresolved attributes in the formalizer list.
        n = 0
        for rattr in self.formalizers:
            if rattr.resolutions == []:  # not resolved
                n = n + 1
                urattr = rattr

        if n == 1:  # exactly 1 unresolved referential - try to match it.
            n = 0
            for iattr in ident.iattrs:
                found = False
                for rattr in self.formalizers:
                    for res in rattr.resolutions:
                        if res.rattr == iattr:
                            found = True
                            break
                if not found:
                    print("found unmatched ident: " + iattr.name)
                    uiattr = iattr
                    n = n + 1
            if n == 1:
                print(self.relnum + ": matching single unmatched " + urattr.name + " to " + uiattr.name + " in " + refclass.classname)
                urattr.resolutions.append(resolution(refclass, uiattr, self.relnum, phrase, "SingleIdent"))
                
        
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


# a parser for an attribute description line

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
# for each of a class's identifiers, prepare a 'candidate' list of [attribute name, matched] pairs.
# after a match attempt, test candidates for any failed match: if any, try for another identifier.

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
                print("no match found for " + candidate.attr.name)
                useident = False
                break
        if useident:
            break
    if not useident:
        ident = refclass.identifiers[0]  # no good match; use primary identifier
    return ident
    

# find class instance from class name

def getclassinstance(argname):
    for c in model_class_list:
        if c.classname == argname:
            break
    return c

model_class_list = []        


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

        for aclass in self.subsys.classes:
            # Get the class name from the model; remove all white space
            txt = aclass['name']
            classname = txt.replace(" ","_")
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
                else:
                    suffix = "ID"
                    if attrtype.endswith(suffix):
                       attrstrip = attrtype[:-len(suffix)]
                       attrtype = attrstrip
                    attrtype = attrtype + "_t"

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
                            # ORx are not true associations - see 'Ordinal' relationship discussion
                            # URx are deprecated
                            if not ref[0] == "R":
                                continue
                            relnum = ref.replace('c','')  # remove any 'c' constraint
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
                tc = cn.replace(" ","_")

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
                pc = cn.replace(" ","_")
                
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
                tclass = getclassinstance(tc)
                pclass = getclassinstance(pc)

                bin_assoc_class = binary_association(rnum, tp, tcond, tmult, tclass, pp, pcond, pmult, pclass)
                binary_rel_list.append(bin_assoc_class)

                if tclass == pclass:
                    bin_assoc_class.is_reflexive = True

                n = text_file.write(tc + pcondtxt + pp + pmulttxt + pc + ",\n")
                n = text_file.write("  " + pc + tcondtxt + tp + tmulttxt + tc)
                
                associator = 0
                associator = r.get('assoc_cname')
                if associator:
                    acname = associator.replace(" ","_")
                    #print(numtxt + " associative using " + acname)
                    assoc_class = getclassinstance(acname)
                    bin_assoc_class.aclass = assoc_class
                    bin_assoc_class.is_associative = True
                    n = text_file.write(" using " + bin_assoc_class.aclass.classname)

                n = text_file.write(";\n")

            else:  # this is a sub-supertype association
            
                s = r['superclass']
                cn = s.replace(" ","_")
                superclass = getclassinstance(cn)
                saclass = subsuper_association(rnum, superclass)
                subsup_rel_list.append(saclass)
                subclasses = r['subclasses']
                sep = ""
                n = text_file.write(cn + " is_a (")
                for s in subclasses:
                    cn = s.replace(" ","_")
                    n = text_file.write(sep + cn)
                    sep = ", "
                    subclass = getclassinstance(cn)
                    saclass.subclasslist.append(subclass)

                    # propagate any missing primary identifiers to subtype, denoting them as referential
                    for superattr in superclass.identifiers[0].iattrs:
                        if superattr.name == "ID":
                            continue  # not this one - the subtype has to have an primary identifier
                        found = False
                        for subattr in subclass.attrlist:
                            if subattr.name == superattr.name:
                                found = True
                                break
                        if not found:
                            newattr = attribute(superattr.name, superattr.type)
                            newattr.references.append(attr_rel_ref(rnum))
                            subclass.attrlist.append(newattr)
                            #print("added " + newattr.name + " to " + subclass.classname + " for " + rnum)
                n = text_file.write(");\n");
                
                
        # compute the formalizing attribute lists: for each class, for each association it formalizes
        # each attribute may contribute to one or more formalized associations.
        # build a list of associations this class wants to formalize.
        # each such list element is a list of the attribute(s) to be matched for the association.
        
        for c in model_class_list:
            for attr in c.attrlist:
                for ref in attr.references:
                    relnum = ref.relnum
                    found = False
                    for formr in c.formalizations:
                        if formr.relnum == relnum:
                            found = True
                            break
                    if not found:
                        formr = formalization(relnum)
                        c.formalizations.append(formr)
                    formr.formalizers.append(attr)
        
                
        # Now attempt to resolve the referential attributes
        # First step is to determine the appropriate identifier for the referred-to class:
        # i.e. the {In} which best matches the attributes required to formalize
               
        # when searching for best identifier, ensure longer attribute lists are tested first - more demanding!
        # so, sort the identifier list by decreasing length of the identifier's attribute list.
        for c in model_class_list:
            idents = c.identifiers
            if len(idents) == 1:  # no choice!
                continue
            idents.sort(reverse = True, key = lambda identifier: len(identifier.iattrs) )
                
        # look for best referred-to class identifier for each formalized association
        # stash the identifier choice in the relationship for use in the resolution pass.
                
        for c in model_class_list:
            for formr in c.formalizations:
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
                            # flatland does not require consistent ordering of relationship definitions:
                            # for this purpose, it is convenient to rely on which is the referred-to class.
                            # if necessary, switch the order of the relationship 'sides'
                            if r.pclass == c:  # the expected 'referred-to' class matches 'self'; swap
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
                        break
                for r in subsup_rel_list:
                    if formr.relnum == r.rnum:
                        formr.rel = r
                        ident = matchident(formr.formalizers, r.superclass)
                        #print(r.superclass.classname + " " + ident.identnum)
                        r.classident = ident.identnum
                        break

        # now add referential resolution instances to each attribute of every formalizer
        
        for c in model_class_list:
            for formr in c.formalizations:
                for r in binary_rel_list:
                    if formr.relnum == r.rnum:
                        if r.is_associative and not r.is_reflexive: # two half-associations involved...
                            formalization.resolve(formr, r.tclass, r.tphrase, r.tclassident)
                            formalization.resolve(formr, r.pclass, r.pphrase, r.pclassident)
                            # after both sides have had a chance to resolve, look for any unmatched.
                            formalization.resolve2(formr, r.tclass, r.tphrase, r.tclassident)
                            formalization.resolve2(formr, r.pclass, r.pphrase, r.pclassident)
                        else:
                            formalization.resolve(formr, r.pclass, r.pphrase, r.pclassident)
                            formalization.resolve2(formr, r.pclass, r.pphrase, r.pclassident)
                        break
                for r in subsup_rel_list:
                    if formr.relnum == r.rnum:
                        formalization.resolve(formr, r.superclass, "", r.classident)
                        formalization.resolve2(formr, r.superclass, "", r.classident)
                        break
        

        """Output class definitions"""

        print(" ")
        text_file.write("\n")
        
        for c in model_class_list:
           
            cname = c.classname
            print("  object ", cname, " is")
            text_file.write("  object "+ cname + " is\n")
            
            for attr in c.attrlist:
                p = ""
                if attr.is_preferred:
                    p = " preferred "
                if not attr.references:  # not a referential attribute
                    typ = attr.type
                    if typ == "undefinedType":  # attempt to type correctly
                        tlist = []
                        if attr.name == "ID" or attr.name == "Name":
                            tlist = c.classname.split("_")
                        else:
                            tlist = attr.name.split("_")
                        tname = ''
                        for titem in tlist:
                            tname = tname + titem.capitalize()
                        typ = tname + "_t"
                        attr.synthtype = True
                        attr.type = typ
                    print("    " + attr.name + " : " + p + typ)
                    text_file.write("    " + attr.name + " : " + p + typ + ";\n")
                else:
                    print("    " + attr.name + " : " + p + "referential ( ")
                    text_file.write("    " + attr.name + " : " + p + "referential ( ")
                    sep = ""
                    phrase = ""
                    for res in attr.resolutions:
                        classname = res.rclass.classname
                        attname = res.rattr.name
                        phrase = ""
                        if not res.rphrase == "":
                            phrase = "." + res.rphrase
                        rnum = res.rnum
                        print("   " + rnum + phrase  + "." + classname + "." + attname + ")")
                        n = text_file.write(sep + rnum + phrase  + "." + classname + "." + attname)
                        sep = ", "
                    text_file.write(" ) " +  "RefAttr;\n")

            # output identifier groups for all non-preferred
            
            for ident in c.identifiers:
                sep = ""
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
            keyletter = c.keyletter
            print("pragma key letter ( ",'"' + keyletter + '"'," );\n")
            n = text_file.write("  end object;\n")
            n = text_file.write("pragma key_letter ( "'"' + keyletter + '"'" );\n\n")

        text_file.write("end domain;\n")
        text_file.close()
        
        # report unresolved referentials

        print("\nThe following referential attributes were unmatched in a referred-to class:")
        for c in model_class_list:
            for formr in c.formalizations:
                for attr in formr.formalizers:
                    if attr.resolutions == []:
                        print(formr.relnum + ": " + c.classname + " has unresolved " + attr.name + " ref ")
        print("\nThe following referentials matched a referred-to class ID identifying attribute (probably safe):")
        for c in model_class_list:
            for formr in c.formalizations:
                for attr in formr.formalizers:
                    for res in attr.resolutions:
                        if res.rnum == formr.relnum and res.category == "ID":
                            print(res.rnum + ": " + c.classname + "." + attr.name + "  ID matched to  " + res.rclass.classname + "." + res.rattr.name)
        print("\nThe following referentials matched a single referred-to identifying attribute (likely safe):")
        for c in model_class_list:
            for formr in c.formalizations:
                for attr in formr.formalizers:
                    for res in attr.resolutions:
                        if res.rnum == formr.relnum and res.category == "SingleIdent":
                            print(res.rnum + ": " + c.classname + "." + attr.name + "  singly matched to  " + res.rclass.classname + "." + res.rattr.name)
        print("\nThe following attributes have been heuristically typed:")
        for c in model_class_list:
             for attr in c.attrlist:
                 if attr.synthtype:
                     print(c.classname + "." + attr.name + " has been given type: " + attr.type)
                            