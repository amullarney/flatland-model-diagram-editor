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
from os.path import exists
from pathlib import Path

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
        self.fixup = False         # will be set if resolution is incomplete


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


# a representation of a subtype-supertype association        

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
        self.reltype = 0       # 0 = unknown; 1 = binary; 2 = subsuper
        self.rel = 0
        self.formalizers = []  # the attributes that formalize this relationship

    # attempt to match each attribute in the formalizer list with an an attribute from the chosen identifier

    def resolve(self, refclass, phrase, identnum):
        ident = refclass.identifiers[0]
        if not identnum == "":
            for ident in refclass.identifiers:
                if ident.identnum == identnum:
                    break
        # look for an exact attribute name match in formalizer and referred-to class:
        for rattr in self.formalizers:
            matched = False
            for iattr in ident.iattrs:
                if rattr.name == iattr.name:
                    print(self.relnum + ": formalization match: " + rattr.name + " to attribute name " + iattr.name + " in " + refclass.classname)
                    print(rattr.name + ": " + iattr.type)
                    rattr.resolutions.append(resolution(refclass, iattr, self.relnum, phrase, "matched"))
                    matched = True
                    break
            if not matched:
                # if the attribute name 'matches' the referred-to class-name which has an 'ID' attribute, consider matched.
                for iattr in ident.iattrs:
                    if iattr.name == "ID":
                        if rattr.name == attributize(refclass.classname):
                            print(self.relnum + ": formalization match: " + rattr.name + " to ID in "  + refclass.classname)
                            print(rattr.name + ": " + iattr.type)
                            rattr.resolutions.append(resolution(refclass, iattr, self.relnum, phrase, "ID"))
                            matched = True
                            break
                            
    # second attempt: look for a single unmatched referential; 
    # if found, look for a single unmatched identifying attribute to be considered a match.
    
    def resolve2(self, refclass, phrase, identnum, reflexassoc):                            
        ident = refclass.identifiers[0]
        if not identnum == "":
            for ident in refclass.identifiers:
                if ident.identnum == identnum:
                    break
        # look for unresolved attributes in the formalizer list.
        unresolveds = []
        for rattr in self.formalizers:
            if rattr.resolutions == []:  # not resolved
                unresolveds.append(rattr)

        if unresolveds != []:
            n = 0
            for iattr in ident.iattrs:
                found = False
                for rattr in self.formalizers:
                    for res in rattr.resolutions:
                        if res.rattr == iattr:
                            found = True
                            break
                if not found:
                    print("found unmatched ident: " + iattr.name + " in class " + refclass.classname)
                    uiattr = iattr
                    n = n + 1
            if n == 1:
                for urattr in unresolveds:
                    print(self.relnum + ": resolve2 matching unmatched " + urattr.name + " to " + uiattr.name + " in " + refclass.classname)
                    urattr.resolutions.append(resolution(refclass, uiattr, self.relnum, phrase, "SingleIdent"))
                    if uiattr.type != "undefinedType":
                        urattr.type = uiattr.type
                        urattr.synthtype = True
                    if not reflexassoc:  # only if reflexive associative, can 2 referentials match a single identifying attribute
                        break
                
        
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
            if fattr.name == cname and candidate.attr.name == "ID":  # this is a 'special' case
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
        identmatch(formalizers, attrlist, attributize(refclass.classname))
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
    

# format a class name to follow attribute naming convention

def attributize(argname):
        ltxt = argname.lower()
        return ltxt.capitalize()


# format one half of a relationship spec given conditionality and multiplicity

def assoctxt(cond, mult):
            if cond:
                txt = "0"
                if mult:
                    txt = txt + "..*"
                else:
                    txt = txt + "..1"
            else:
                txt = "1";
                if mult:
                    txt = txt + "..*"
            return txt


# class and relationship lists

model_class_list = []    
binary_rel_list = []
subsup_rel_list = []


# The heart of the matter:

# This class's one and only method uses the Flatland parser to discover model classes and associations.
# MASL output is generated along the way in some cases: see text_file.write()
# 1. Classes are discovered; their attribute text blocks are supplementally parsed for details;
# 2. Associations are discovered and linked to their classes;
# 3. Formalizing attribute sets are constructed for each association.
# 4. Referred-to identifier choices are evaluated for best referential resolution.
# 5. Resolution of referential links is attempted, adding resolution data for each attribute.

class MaslOut:

    def __init__(self, xuml_model_path: Path, domain):
        """Constructor"""
        self.logger = logging.getLogger(__name__)
        self.xuml_model_path = xuml_model_path
        
        # Create a Parser which accepts just an attribute description line        
        att_parser = attr_parser("attr_grammar.peg", "attrdef" )

        self.logger.info("Parsing the model for micca output")
        # Parse the model
        try:
            self.model = ModelParser(model_file_path=self.xuml_model_path, debug=False)
        except FlatlandIOException as e:
            sys.exit(e)
        try:
            self.subsys = self.model.parse()
        except ModelParseError as e:
            sys.exit(e)
        
        
        # read a file of attributes to be excluded from population data
        # one line for each: format: <classname>:<attribute_name>
        exclusions = []   
        if exists("exclusions.txt"):
            exclusions = Path("exclusions.txt").read_text().splitlines()
            print("Attribute exclusion entries:")
            for x in exclusions:
                print(x)
        else:
            print("cannot find exclusions file")
        print("")

        # read a file of type names which must be treated as strings
        # one line for each: format: typename
        stringtypes = []   
        if exists("stringtypes.txt"):
            stringtypes = Path("stringtypes.txt").read_text().splitlines()
            print("String type entries:")
            for x in stringtypes:
                print(x)
        else:
            print("cannot find stringtypes file")
        print("")

        print("Generating micca domain definitions for " + domain)
        maslfile = domain.replace(" ","") +".masl"
        text_file = open(maslfile, "w")
        text_file.write("domain " + domain + " is\n")

        for aclass in self.subsys.classes:
            # Get the class name from the model; remove all white space
            txt = aclass['name']
            classname = txt.replace(" ","_")

            # Optional keyletter (class name abbreviation) after the class name?
            keyletter = str(aclass.get('keyletter'))
            if keyletter == "None":
                keyletter = classname
            text_file.write("  object " + keyletter +";\n")

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
                    aline.update(x)  # 'gather' child node data
                # check for derived (function) attribute
                attrname = aline['aname']
                if attrname.startswith('/'):    # UML notation for 'derived' attribute
                    print("skipping derived: " + attrname)
                    classattrs.pop(0)
                    continue
                # check for attribute exclusion
                matchattr = classname + ':' + attrname
                match = False
                for x in exclusions:
                    if matchattr == x:
                        match = True
                        break
                if match:
                    print("skipping excluded: " + matchattr)
                    classattrs.pop(0)
                    continue
                attrtype = aline.get('atype')
                if not attrtype:
                    attrtype = "undefinedType"  # default.. to be tested for later
                else:
                    # attempt to follow convention in forming attribute type name
                    suffix = "ID"
                    if attrtype.endswith(suffix):
                       attrstrip = attrtype[:-len(suffix)]
                       attrtype = attrstrip
                    attrtype = attrtype + "_t"
                    print("constructed type: " +  attrtype + " for " + attrname + " of " + classname)

                thisattr = attribute(attrname, attrtype)
                thisclass.attrlist.append(thisattr)
                
                # gather auxiliary attribute information - nominated as identifier? - formalizer?
                
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





        # chase down identifier attribute types

        for c in model_class_list:
            for attr in c.attrlist:
                if attr.type == "undefinedType" and not attr.references:
                    print(attr.name + " is undefined for " + c.classname)
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
                    print("synthesized " + typ)
                    attr.type = typ

        # Get all association data - this will be needed to type referential attributes
        # Create two lists of association data class types - binary and sub-super
        # Following Flatland convention, binary associations have 't' and 'p' 'sides'

        for r in self.subsys.rels:  # for each discovered relationship..
            #print(r)
            numtxt = r['rnum']
            rnum = numtxt
            if not numtxt[0] == "R":
                if numtxt[0] == "O":
                    continue  # these are not formalizable associations: 
                              # see https://github.com/modelint/shlaer-mellor-metamodel/wiki/Ordinal-Relationship
                rnum = numtxt[1:]  # strip any U prefixes
            text_file.write("relationship " + rnum + " is ")

            if not 'superclass' in r.keys():  # treat binary associations here..
                tside = r['t_side']
                cname = tside['cname']
                tc = cname.replace(" ","_")

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
                cname = pside['cname']
                pc = cname.replace(" ","_")
                
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

                text_file.write(tclass.keyletter + pcondtxt + pp + pmulttxt + pclass.keyletter + ",\n")
                text_file.write("  " + pclass.keyletter + tcondtxt + tp + tmulttxt + tclass.keyletter)
                
                # check for a named associative class for this relationship
                
                associator = 0
                associator = r.get('assoc_cname')
                if associator:
                    acname = associator.replace(" ","_")
                    #print(numtxt + " associative using " + acname)
                    assoc_class = getclassinstance(acname)
                    bin_assoc_class.aclass = assoc_class
                    bin_assoc_class.is_associative = True
                    text_file.write(" using " + bin_assoc_class.aclass.keyletter)
                text_file.write(";\n")

            else:  # this is a sub-supertype association
            
                s = r['superclass']
                cname = s.replace(" ","_")
                superclass = getclassinstance(cname)
                saclass = subsuper_association(rnum, superclass)
                subsup_rel_list.append(saclass)
                subclasses = r['subclasses']
                sep = ""
                text_file.write(superclass.keyletter + " is_a (")
                for s in subclasses:
                    cname = s.replace(" ","_")
                    subclass = getclassinstance(cname)
                    text_file.write(sep + subclass.keyletter)
                    sep = ", "
                    saclass.subclasslist.append(subclass)

                    # propagate any missing primary identifiers to subtype, denoting them as referential (non-SM usage)
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
                text_file.write(");\n");
                
                
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
               
        # look for best referred-to class identifier for each formalized association
        # when searching for best identifier, ensure longer attribute lists are tested first - more demanding!
        # so, first sort the identifier list by decreasing length of the identifier's attribute list.

        for c in model_class_list:
            idents = c.identifiers
            if len(idents) == 1:  # no choice!
                continue
            idents.sort(reverse = True, key = lambda identifier: len(identifier.iattrs))
                
        # now find best match, stashing the identifier choice in the relationship for use in the resolution pass.
                
        for c in model_class_list:
            for formr in c.formalizations:
                attrstr = ""
                for fattr in formr.formalizers:
                    attrstr = attrstr + " " + fattr.name
                print("formalize " + formr.relnum + " needs: " + attrstr)

                for r in binary_rel_list:
                    if formr.relnum == r.rnum:
                        formr.rel = r
                        formr.reltype = 1  # will need this later
                        if r.is_associative:
                            if not r.is_reflexive: # two half-associations involved...
                                ident = matchident(formr.formalizers, r.tclass)
                                print(r.tclass.classname + " " + ident.identnum)
                                r.tclassident = ident.identnum
                                ident = matchident(formr.formalizers, r.pclass)
                                print(r.pclass.classname + " " + ident.identnum)
                                r.pclassident = ident.identnum
                            else:
                                print(" reflexive ")
                                ident = matchident(formr.formalizers, r.tclass)
                                print(r.tclass.classname + " " + ident.identnum)
                                r.tclassident = ident.identnum
                                
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
                            print(r.pclass.classname + " " + ident.identnum)
                            r.pclassident = ident.identnum
                        break
                for r in subsup_rel_list:
                    if formr.relnum == r.rnum:
                        formr.rel = r
                        formr.reltype = 2
                        ident = matchident(formr.formalizers, r.superclass)
                        #print(r.superclass.classname + " " + ident.identnum)
                        r.classident = ident.identnum
                        break

        # now, using chosen identifiers, attempt to resolve the formalizations.
        # add referential resolution instances to each attribute of every formalizer
        # note that a second attempt may match a previously unresolved formalizer
        
        for c in model_class_list:
            for formr in c.formalizations:
                r = formr.rel
                if formr.reltype == 1:
                    if r.is_associative:
                        if not r.is_reflexive: # two half-associations involved...
                            formalization.resolve(formr, r.tclass, r.tphrase, r.tclassident)
                            formalization.resolve(formr, r.pclass, r.pphrase, r.pclassident)
                            # after both sides have had a chance to resolve, look for any unmatched.
                            formalization.resolve2(formr, r.tclass, r.tphrase, r.tclassident, False)
                            formalization.resolve2(formr, r.pclass, r.pphrase, r.pclassident, False)
                        else:
                            # reflexive: all referentials resolve against the single class involved
                            # two cases: heuristic match uncertain; referential to both sides.
                            formalization.resolve(formr, r.tclass, "FIX THIS!!", r.tclassident)
                            # after both sides have had a chance to resolve, look for any unmatched.
                            formalization.resolve2(formr, r.tclass, "FIX THIS!!", r.tclassident, True)
                            for rattr in formr.formalizers:
                                fixes = []
                                for res in rattr.resolutions:
                                    if res.rphrase == "FIX THIS!!":
                                        fixes.append(res)
                                if len(fixes) == 2:    # referential points at both sides of reflexive
                                    fixes[0].rphrase = r.tphrase
                                    fixes[1].rphrase = r.pphrase
                                if len(fixes) == 1:    # some uncertainty about resolution
                                    fixes[0].rphrase = r.tphrase + " FIX THIS !!! "
                                    rattr.fixup = True
                    else:
                        formalization.resolve(formr, r.pclass, r.pphrase, r.pclassident)
                        formalization.resolve2(formr, r.pclass, r.pphrase, r.pclassident, False)  # 2nd chance
                if formr.reltype == 2:
                      formalization.resolve(formr, r.superclass, "", r.classident)
                      formalization.resolve2(formr, r.superclass, "", r.classident, False)  # 2nd chance
        



        for c in model_class_list:
            for attr in c.attrlist:
                if attr.references and attr.type == "undefinedType":
                    print("trying to type: " + attr.name + " for " + c.classname)
                    rattr = attr
                    while rattr.resolutions != []:
                        res = rattr.resolutions[0]
                        if res:
                            print(res.rattr.name + " " + res.rattr.type)
                            rattr = res.rattr
                        else:
                            break
                    attr.type = rattr.type
                    print(c.classname + ":  " + attr.name + " now typed as " + attr.type)



        # Output MASL class definitions

        print(" ")
        text_file.write("\n")
        
        for c in model_class_list:
           
            cname = c.keyletter
            print("  object ", cname, " is")
            text_file.write("  object "+ cname + " is\n    instance_label : string;\n")
            
            for attr in c.attrlist:
                p = ""
                if attr.is_preferred:
                    p = " preferred "
                if not attr.synthtype:
                    typ = attr.type
                    print("attr: " + attr.name + " " + typ)
                    if typ == "undefinedType":  # attempt to define type correctly
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
                        print("synthesized " + typ)
                        attr.type = typ

                if not attr.references:
                    print("    " + attr.name + " : " + p + attr.type)
                    typ = "string"
                    text_file.write("    " + attr.name + " : " + p + typ + ";\n")
                else:
                    print("    " + attr.name + " : " + p + "referential ( ")
                    text_file.write("    " + attr.name + " : " + p + "referential ( ")
                    sep = ""
                    phrase = ""
                    for res in attr.resolutions:
                        cname = res.rclass.keyletter
                        attname = res.rattr.name
                        phrase = ""
                        if not res.rphrase == "":
                            phrase = "." + res.rphrase
                        rnum = res.rnum
                        print("   " + rnum + phrase  + "." + cname + "." + attname + ")")
                        text_file.write(sep + rnum + phrase  + "." + cname + "." + attname)
                        sep = ", "
                    text_file.write(" ) " +  "RefAttr;\n")

            # output identifier groups for all non-preferred

            idents = c.identifiers
            idents.sort( key = lambda identifier: identifier.identnum )  # order them
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
            text_file.write("  end object;\n")
            text_file.write("pragma key_letter ( "'"' + keyletter + '"'" );\n\n")

        text_file.write("end domain;\n")
        text_file.close()
        
        # report unresolved referentials and synthesized types

        print("\nThe following referential attributes were unmatched/not fully matched in a referred-to class:  [search for FIX THIS !!!]")
        for c in model_class_list:
            for formr in c.formalizations:
                for attr in formr.formalizers:
                    if attr.resolutions == [] or attr.fixup:
                        print(formr.relnum + ": " + c.classname + " has unresolved " + attr.name + " ref ")
        print("\nThe following referentials matched a referred-to class ID identifying attribute (probably safe):")
        for c in model_class_list:
            for formr in c.formalizations:
                for attr in formr.formalizers:
                    for res in attr.resolutions:
                        if res.rnum == formr.relnum and res.category == "ID":
                            print(res.rnum + ": " + c.classname + "." + attr.name + "  ID matched to  " + res.rclass.classname + "." + res.rattr.name)
        print("\nThe following referentials matched a single referred-to identifying attribute (likely safe, but check associative classes):")
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


        # output OAL for instance labeling and population data output
                            
        path = domain.replace(" ","") +".oal"
        text_file = open(path, "w")

        for c in model_class_list:
            cname = c.keyletter
            text_file.write("// Check instance_label for " + cname + " instances\n")
            text_file.write("select many " + cname + "_insts" + " from instances of " + cname + ";\n")
            text_file.write("lblnum = 1;\n")
            text_file.write("for each " + cname + "_inst" + " in " + cname + "_insts\n")
            text_file.write("  lbl = " + cname + "_inst.instance_label;\n")
            text_file.write("  if lbl == " + '"' + '"' + ";\n")
            text_file.write("    genlabel = " + '"' +  cname + '"' + " + " + "\"_\"" + " + STR::itoa(i:lblnum);\n")
            text_file.write("    " + cname + "_inst.instance_label = genlabel;\n")
            text_file.write("    lblnum = lblnum + 1;\n")
            text_file.write("  else\n")
            text_file.write("    " + cname + "_inst.instance_label = STRING::replaceall(s:lbl, pattern:" + '"' + "-" + '"' + ", replacement:" + '"' + "_" + '"' + ");\n")
            text_file.write("  end if;\n") 
            text_file.write("end for;\n\n")


        for c in model_class_list:
           
            cname = c.keyletter
            text_file.write("// Output instances of " + cname + "\n")
            text_file.write("  select many " + cname + "_insts" + " from instances of " + cname + ";\n")
            text_file.write("  T::push_buffer();\n")
            text_file.write("  instances = " + '"' + '"' + ";\n")
            text_file.write("  for each " + cname + "_inst" + " in " + cname + "_insts\n")
            for attr in c.attrlist:
                text_file.write("    attrname = " + '"' + attr.name + '"' + ";\n")
                text_file.write("    attrvalue = " + cname + "_inst." + attr.name + ";\n")
                match = False
                for x in stringtypes:
                    if attr.type == x:
                        match = True
                        break
                if match:
                    text_file.write("    T::include(file:"'"' + "attrquote.java" + '"'");\n")
                else:
                    text_file.write("    T::include(file:"'"' + "attribute.java" + '"'");\n")
            text_file.write("    attributes = T::body();\n")
            for formr in c.formalizations:
                rel = formr.rel
                text_file.write("    relnum = "'"' +  rel.rnum + '"'";\n")
                if formr.reltype == 1:
                    pphrase = ""
                    tphrase = ""
                    if rel.is_reflexive:
                        pphrase = "." + rel.pphrase
                        tphrase = "." + rel.tphrase
                    if not rel.is_associative:
                        other = c
                        if c == rel.tclass:
                            other = rel.pclass
                            phrase = pphrase
                        else:
                            other = rel.tclass
                            phrase = tphrase
                        text_file.write("    select one " + other.keyletter + " related by " + cname + "_inst->" + other.keyletter + "[" + rel.rnum + phrase + "];\n")
                        text_file.write("    if not_empty " + other.keyletter + "\n")
                        text_file.write("      targetname = " + other.keyletter + ".instance_label;\n")
                        text_file.write("      T::include(file:"'"' + "simpleassoc.java" + '"'");\n")
                        text_file.write("    end if;\n")
                    else:
                        text_file.write("    select one " + rel.tclass.keyletter + " related by " + cname + "_inst->" + rel.tclass.keyletter + "[" + rel.rnum + tphrase + "];\n")
                        text_file.write("    forward = " + rel.tclass.keyletter + ".instance_label;\n")
                        text_file.write("    select one " + rel.pclass.keyletter + " related by " + cname + "_inst->" + rel.pclass.keyletter + "[" + rel.rnum + pphrase + "];\n")
                        text_file.write("    backward = " + rel.pclass.keyletter + ".instance_label;\n")
                        if rel.is_reflexive:
                            text_file.write("    T::include(file:"'"' + "assocreflx.java" + '"'");\n")
                        else:
                            text_file.write("    from = "'"' + rel.tclass.keyletter + '"'";\n")
                            text_file.write("    to = "'"' + rel.pclass.keyletter + '"'";\n")
                            text_file.write("    T::include(file:"'"' + "assocassoc.java" + '"'");\n")
                else:
                    text_file.write("    select one " + rel.superclass.keyletter + " related by " + cname + "_inst->" + rel.superclass.keyletter + "[" + rel.rnum + "];\n")
                    text_file.write("    targetname = " + rel.superclass.keyletter + ".instance_label;\n")
                    text_file.write("    T::include(file:"'"' + "subsupassoc.java" + '"'");\n")
            text_file.write("    associations = T::body();\n")
            
            text_file.write("    instance_label = " + cname + "_inst.instance_label;\n")
            text_file.write("    T::include(file:"'"' + "instance.java" + '"'");\n")
            text_file.write("    instances = instances + T::body();\n")
            text_file.write("  end for;\n")
            text_file.write("  T::pop_buffer();\n")

            text_file.write("  classname = "'"' +  cname + '"'";\n")
            text_file.write("  emptyallocate = false;\n")
            text_file.write("  if empty " + cname + "_insts\n")
            text_file.write("    emptyallocate = true;\n")
            text_file.write("  end if;\n")
            text_file.write("  T::include(file:"'"' + "class.java" + '"'");\n\n")
        text_file.write("population = T::body();\n")
        text_file.write("domain = "'"' +  domain + '"'";\n")
        text_file.write("T::include(file:"'"' + "population.java" + '"'");\n")
        text_file.write("T::emit(file:"'"' + "population.micca" + '"'");\n\n")

                    
        # output domain definitions in Micca format
                    
        path = domain.replace(" ","") +".micca"
        text_file = open(path, "w")
        text_file.write("domain " + domain + " {\n")
        
        # emit class definitions
        for c in model_class_list:
            text_file.write("\nclass " + c.keyletter + " {\n")
            for attr in c.attrlist:
                text_file.write("    attribute " + attr.name + " {" + attr.type + "}\n")
            text_file.write("}\n")

        # emit sub-super associations
        backslash = "\\"
        for subsup in subsup_rel_list:
            superclass = subsup.superclass
            text_file.write("\ngeneralization " + subsup.rnum + " " + superclass.keyletter + backslash + "\n")
            for sub in subsup.subclasslist:
                text_file.write("    " + sub.keyletter + backslash + "\n")

        #emit binary associations                
        for binassoc in binary_rel_list:
            text_file.write("\nassociation " + binassoc.rnum + " ")
            if binassoc.is_associative:
                text_file.write("-associator " + binassoc.aclass.keyletter + backslash + "\n    ")
            ttxt = assoctxt(binassoc.tcond, binassoc.tmult)
            ptxt = assoctxt(binassoc.pcond, binassoc.pmult)
            if binassoc.pmult and not binassoc.tmult:
                text_file.write(binassoc.pclass.keyletter + " " + ptxt)
                text_file.write("--")
                text_file.write(ttxt + " " + binassoc.tclass.keyletter + "\n")
            else:
                text_file.write(binassoc.tclass.keyletter + " " + ttxt)
                text_file.write("--")
                text_file.write(ptxt + " " + binassoc.pclass.keyletter + "\n")

        text_file.write("\n}\n")
               

                            