# -*- coding: UTF-8 -*-
# Copyright 2017 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""cib2pcscmd command"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

from ..command import Command
try:
    from ..defaults import SHELL_POSIX
except ImportError:
    SHELL_POSIX = ''
from ..filter import XMLFilter
from ..protocol import protocols
from ..utils_cib import PATH_CIB
from ._chains_pcs import cib2pcscmd_chain_exec  #, cib2pcscmd_output


@Command.deco(('cmd-annotate',
                  ('stringiter-combine2',
                      ('cmd-wrap'))),
              (cib2pcscmd_chain_exec(
                  ('stringiter-combine2'  # , ('cmd-wrap' ...
                   ))))
def cib2pcscmd(cmd_ctxt,
               input=PATH_CIB,
               output="-",
               force=False,
               noauth=False,
               silent=False,
               tmp_cib="{cib2pcscmd.defs[pcscmd_tmpcib]}",
               dry_run=False,
               set_exec=False,
               text_width='0',
               _common=XMLFilter.command_common):
    """CIB -> equivalent in pcs commands

    Options:
        input       input proper Pacemaker cluster configuration file (CIB)
        output      pcs commands to reinstate the cluster per the inputs
        force       may the force be with emitted pcs commands
        noauth      skip authentication step (OK if already set up)
        silent      do not track the progress along the steps execution (echoes)
        tmp_cib     file to accumulate the changes (empty ~ direct push, avoid!)
        dry_run     omit intrusive commands (TMP_CIB reset if empty)
        set_exec    make the output file executable (not recommended)
        text_width  for commands rewrapping (0/-1/neg. ~ auto/disable/hi-limit)
    """
    cmd_ctxt['pcscmd_force'] = force
    cmd_ctxt['pcscmd_noauth'] = noauth
    cmd_ctxt['pcscmd_verbose'] = not(silent)
    cmd_ctxt['pcscmd_tmpcib'] = tmp_cib
    cmd_ctxt['pcscmd_dryrun'] = dry_run
    cmd_ctxt['text_width'] = text_width

    cmd_ctxt['annotate_shell'] = SHELL_POSIX
    # XXX possibility to disable cib-meld-templates

    void_proto = protocols.plugins['void'].ensure_proto
    file_proto = protocols.plugins['file'].ensure_proto
    yield (
        (
            void_proto(),
            (
                    (
                        file_proto(output),
                    ),
            ),
        ), (
            file_proto(input),
            # already tracked
            #cib2pcscmd_output(
            #        (
            #            file_proto(output),
            #        ),
            #),
        ),
    )
    # post-processing (make resulting file optionally executable)
    if set_exec:
        output_set_exec(cmd_ctxt, 'cmd-wrap')
