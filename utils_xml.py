# -*- coding: UTF-8 -*-
# Copyright 2017 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""XML helpers"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

from lxml import etree

from .error import ClufterPlainError
from .utils import selfaware
from .utils_2to3 import basestring, foreach_u, iter_items
from .utils_func import bifilter


NAMESPACES = {
    'clufter': 'http://people.redhat.com/jpokorny/ns/clufter',
    'rng':     'http://relaxng.org/ns/structure/1.0',
    'xsl':     'http://www.w3.org/1999/XSL/Transform',
}

# X=x and X_NS=url for each (x, url) in NAMESPACES
foreach_u(
    lambda ns, url:
        foreach_u(lambda k, v: globals().setdefault(k, v),
                  ((ns.upper(), ns), (ns.upper() + '_NS', url))),
    iter_items(NAMESPACES)
)


class UtilsXmlError(ClufterPlainError):
    pass


def squote(s):
    """Simple quote"""
    return "'" + s + "'"


def namespaced(ns, ident):
    """Return `ident` in Clark's notation denoting `ns` namespace"""
    ret = "{{{0}}}{1}".format(NAMESPACES.get(ns, ns), ident)
    return ret


def nselem(ns, tag, *args, **kwargs):
    ret = etree.Element(namespaced(ns, tag), **kwargs)
    strings, nonstrings = bifilter(lambda x: isinstance(x, basestring), args)
    ret.extend(ns for ns in nonstrings if ns is not None)
    # conditionally assigned so as to support self-closed tags where possible
    text = ' '.join(strings)
    if text:
        ret.text = text
    return ret


rng_get_start = etree.ETXPath("/{0}/{1}"
                              .format(namespaced(RNG, 'grammar'),
                                      namespaced(RNG, 'start')))
xml_get_root_pi = etree.XPath("/*/processing-instruction()")

# tag can also be a subclass of etree._Element when applied on `element.tag`
# --> return an empty string in such non-string cases
xmltag_get_localname = lambda tag: etree.QName(tag).localname \
                                   if isinstance(tag, basestring) else ''
xmltag_get_namespace = lambda tag: etree.QName(tag).namespace \
                                   if isinstance(tag, basestring) else ''

RNG_ELEMENT = ("/{0}//{1}".format(namespaced(RNG, 'grammar'),
                                  namespaced(RNG, 'element'))
               .replace('{', '{{').replace('}', '}}')
               + "[@name = '{0}']")


class ElementJuggler(object):
    """Element juggling, possibly utilizing own temporary holder

    This can be handy e.g. to automatically strip unused namespaces
    for `tostring` method, without a need to copy/reparse, followed
    by returning the element back.
    """

    _aside_tree = etree.ElementTree(etree.Element('ROOT'))

    def __init__(self, tree=_aside_tree):
        self._root = tree.getroot()

    def grab(self, elem):
        parent = elem.getparent()
        assert parent is not self._root
        if parent is None:
            parent_index = None
        else:
            parent_index = parent.index(elem)
        self._root.append(elem)
        return parent, parent_index

    @staticmethod
    def rebind(elem, parent_pos):
        parent, parent_index = parent_pos
        if parent is not None:
            parent.insert(parent_index, elem)
        return elem

    def drop(self, elem):
        parent = elem.getparent()
        if parent is not self._root:
            raise ValueError
        parent.remove(elem)

element_juggler = ElementJuggler()


@selfaware
def rng_pivot(me, et, tag):
    """Given Relax NG grammar etree as `et`, change start tag (in situ!)

    Use copy.deepcopy or so to (somewhat) preserve the original.

    Returns the live reference to the target element, i.e.,

        at_start = rng_pivot(et, tag)

    is equivalent to

        rng_pivot(et, tag)
        at_start = rng_get_start(et)[0]
    """
    start = rng_get_start(et)
    localname = xmltag_get_localname(tag)
    if len(start) != 1:
        raise UtilsXmlError("Cannot change start if grammar's `start' is"
                            " not contained exactly once ({0} times)"
                            .format(len(start)))
    target = etree.ETXPath(RNG_ELEMENT.format(tag))(et)
    if len(target) != 1:
        raise UtilsXmlError("Cannot change start if the start element `{0}'"
                            " is not contained exactly once ({1} times)"
                            .format(localname, len(target)))
    start, target = start[0], target[0]
    parent_start, parent_target = start.getparent(), target.getparent()
    index_target = parent_target.index(target)
    label = me.__name__ + '_' + localname

    # target's content place directly under /grammar wrapped with new define...
    new_define = nselem(RNG, 'define', name=label)
    new_define.append(target)
    parent_start.append(new_define)

    # ... while the original occurrence substituted in-situ with the reference
    new_ref = nselem(RNG, 'ref', name=label)
    parent_target.insert(index_target, new_ref)

    # ... and finally /grammar/start pointed anew to refer to the new label
    start_ref = nselem(RNG, 'ref', name=label)
    start.clear()
    start.append(start_ref)

    return target
