# -*- coding: UTF-8 -*-
# Copyright 2017 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""Chains of filters used in *2pcs* commands"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

from os import fchmod, fstat
import stat

from ..utils import args2tuple, args2unwrapped, tuplist
from ..utils_func import apply_aggregation_preserving_passing_depth


terminalize = lambda args: \
    apply_aggregation_preserving_passing_depth(
        lambda i, d:
            tuple(a for a in i[:-1] if tuplist(a))
            + tuple([args.pop() if not tuplist(i[-1]) else i[-1]])
    )


def cast_output(chain):
    def cast_output_inner(*args):
        args = list(args)
        args.reverse()
        ret = terminalize(args)(chain)
        return ret
    return cast_output_inner


ccsflat2cibfinal_chain_exec = lambda cont=(): \
    ('ccs-revitalize',
        ('ccsflat2cibprelude',
            ('cibprelude2cibcompact',
                ('cibcompact2cib',
                    (args2unwrapped('cib2cibfinal',
                                    *(cont and args2tuple(cont))))))))
ccsflat2cibfinal_chain = ccsflat2cibfinal_chain_exec()
ccsflat2cibfinal_output = cast_output(ccsflat2cibfinal_chain)

cib2pcscmd_chain_exec = lambda cont=(): \
    ('cib-revitalize',
        ('cib-meld-templates',
            (args2unwrapped('cib2pcscmd',
                            *(cont and args2tuple(cont))))))
cib2pcscmd_chain = cib2pcscmd_chain_exec()
cib2pcscmd_output = cast_output(cib2pcscmd_chain)

ccsflat2pcscmd_chain_exec = lambda cont=(): \
    ccsflat2cibfinal_chain_exec(cib2pcscmd_chain_exec(cont))
#ccsflat2pcscmd_chain = (ccsflat2cibfinal_chain_exec(cib2pcscmd_chain))
ccsflat2pcscmd_chain = ccsflat2pcscmd_chain_exec()
ccsflat2pcscmd_output = cast_output(ccsflat2pcscmd_chain)


def output_set_exec(cmd_ctxt, output_flt):
    """Common post-processing for commands producing scripts, sets exec bits"""
    o = cmd_ctxt.filter(output_flt)['out'].FILE()
    if o.startswith('<') and o.endswith('>'):
        pass  # do not try to manipulate with stdout/stderr
    else:
        try:
            with open(o, 'rb') as f:
                fd = f.fileno()
                fchmod(fd, fstat(fd).st_mode | stat.S_IXUSR | stat.S_IXGRP)
        except IOError:
            from sys import stderr
            svc_output = cmd_ctxt.get('svc_output',
                                      lambda s, **kw: stderr.write(s + '\n'))
            svc_output("Cannot set output file `{0}` executable".format(o),
                       base="error", urgent=True)
