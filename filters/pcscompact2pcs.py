# -*- coding: UTF-8 -*-
# Copyright 2014 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""pcscompact2pcs filter"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

from ..filter import XMLFilter


@XMLFilter.deco('pcs-compact', 'pcs')
def pcscompact2pcs(flt_ctxt, in_obj):
    return ('etree', flt_ctxt.ctxt_proceed_xslt(in_obj))
