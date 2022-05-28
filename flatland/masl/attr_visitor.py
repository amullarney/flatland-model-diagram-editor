""" AttrVisitor.py """

from arpeggio import PTNodeVisitor

class AttrVisitor(PTNodeVisitor):

    # Elements
    def visit_nl(self, node, children):
        return None

    def visit_sp(self, node, children):
        return None

    def visit_lbrace(self, node, children):
        return None

    def visit_rbrace(self, node, children):
        return None

    def visit_colon(self, node, children):
        return None

    def visit_ident(self, node, children):
        return children[0] # discard any star (asterisk)

    def visit_rnum(self, node, children):
        return node.value

    def visit_comma(self, node, children):
        return None

    def visit_mult(self, node, children):
        """Binary association (not association class) multiplicity"""
        mult = node.value  # No children because literal 1 or M is thrown out
        return mult

    def visit_acword(self, node, children):
        """All caps word"""
        return node.value  # No children since this is a literal

    def visit_aword(self, node, children):
        """Any word"""
        return node.value  # No children since this is a literal

    def visit_icaps_name(self, node, children):
        """Model element name"""
        name = ''.join(children)
        return name

    def visit_referentials(self, node, children):
        return {"refs": children}

    def visit_attrtype(self, node, children):
        concat = ''.join(children)
        name = concat.replace(" ","")
        return {"atype": name}

    def visit_attrinfo(self, node, children):
        info = {}
        for child in children:
            info.update(child)
        return {"info": info}

    def visit_idents(self, node, children):
        return {"idents": children}

    def visit_attrname(self, node, children):
        concat = ''.join(children)
        name = concat.replace(" ","_")
        return {"aname": name}

    # Root
    def visit_attr_line(self, node, children):
        """The attribute description line"""
        return children


