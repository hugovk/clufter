# -*- coding: UTF-8 -*-
# Copyright 2015 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""ccsflat2cibprelude filter"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

from ..filter import XMLFilter


# XXX temporary hack with plain ccs;
# check that it is indeed ccs-flat, by exploring flt_ctxt?
@XMLFilter.deco_xslt('ccs-flat', 'cib-prelude')
class ccsflat2cibprelude: pass
