# -*- coding: UTF-8 -*-
# Copyright 2016 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""ccs2pcscmd{,-flatiron,-needle} commands"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

from ..command import Command, CommandAlias
from ..facts import cluster_pcs_flatiron
from ..filter import XMLFilter
from ..protocol import protocols
from ..utils_cman import PATH_CLUSTERCONF
from ._chains_pcs import ccsflat2pcscmd_chain, ccsflat2pcscmd_output


@Command.deco(('ccs2ccsflat',
                  ('ccs-disable-rg',
                      ('ccs2ccs-pcmk',
                          ('ccs-version-bump',
                              ('ccspcmk2pcscmd',
                                  ('stringiter-combine2',
                                       ('cmd-wrap')))))),
                  (ccsflat2pcscmd_chain,
                                  ('stringiter-combine2'  # , ('cmd-wrap' ...
                                   ))))
def ccs2pcscmd_flatiron(cmd_ctxt,
                        input=PATH_CLUSTERCONF,
                        output="-",
                        force=False,
                        noauth=False,
                        silent=False,
                        tmp_cib="{cib2pcscmd.defs[pcscmd_tmpcib]}",
                        dry_run=False,
                        enable=False,
                        start_wait="{ccspcmk2pcscmd.defs[pcscmd_start_wait]}",
                        noguidance=False,
                        text_width='0',
                        _common=XMLFilter.command_common):
    """(CMAN,rgmanager) cluster cfg. -> equivalent in pcs commands

    Options:
        input       input (CMAN,rgmanager) cluster configuration file
        output      pcs commands to reinstate the cluster per the inputs
        force       may the force be with emitted pcs commands
        noauth      skip authentication step (OK if already set up)
        silent      do not track the progress along the steps execution (echoes)
        tmp_cib     file to accumulate the changes (empty ~ direct push, avoid!)
        dry_run     omit intrusive commands (TMP_CIB reset if empty)
        enable      enable cluster infrastructure services (autostart on reboot)
        start_wait  fixed seconds to give cluster to come up initially
        noguidance  omit extraneous guiding
        text_width  for commands rewrapping (0/-1/neg. ~ auto/disable/hi-limit)
    """
    cmd_ctxt['pcscmd_force'] = force
    cmd_ctxt['pcscmd_noauth'] = noauth
    cmd_ctxt['pcscmd_verbose'] = not(silent)
    cmd_ctxt['pcscmd_tmpcib'] = tmp_cib
    cmd_ctxt['pcscmd_dryrun'] = dry_run
    cmd_ctxt['pcscmd_enable'] = enable
    cmd_ctxt['pcscmd_start_wait'] = start_wait
    cmd_ctxt['pcscmd_noguidance'] = noguidance
    cmd_ctxt['text_width'] = text_width
    # XXX possibility to disable cib-meld-templates

    file_proto = protocols.plugins['file'].ensure_proto
    return (
        file_proto(input),
        (
            (
                (
                    (
                        (
                            (
                                file_proto(output),
                            ),
                        ),
                    ),
                ),
            ),
            #ccsflat2cibfinal_output(
            #            (
            #                (
            #                    file_proto(output),  # already tracked
            #                ),
            #            ),
            #),
        ),
    )


@Command.deco(('ccs2ccsflat',
                  ('ccs-propagate-cman',
                      ('ccs2needlexml',
                          ('needlexml2pcscmd',
                              ('stringiter-combine2',
                                   ('cmd-wrap'))))),
                  (ccsflat2pcscmd_chain,
                              ('stringiter-combine2'  # , ('cmd-wrap' ...
                               ))))
def ccs2pcscmd_needle(cmd_ctxt,
                      input=PATH_CLUSTERCONF,
                      output="-",
                      force=False,
                      noauth=False,
                      silent=False,
                      tmp_cib="{cib2pcscmd.defs[pcscmd_tmpcib]}",
                      dry_run=False,
                      enable=False,
                      start_wait="{needlexml2pcscmd.defs[pcscmd_start_wait]}",
                      noguidance=False,
                      text_width='0',
                      _common=XMLFilter.command_common):
    """(CMAN,rgmanager) cluster cfg. -> equivalent in pcs commands

    Options:
        input       input (CMAN,rgmanager) cluster configuration file
        output      pcs commands to reinstate the cluster per the inputs
        force       may the force be with emitted pcs commands
        noauth      skip authentication step (OK if already set up)
        silent      do not track the progress along the steps execution (echoes)
        tmp_cib     file to accumulate the changes (empty ~ direct push, avoid!)
        dry_run     omit intrusive commands (TMP_CIB reset if empty)
        enable      enable cluster infrastructure services (autostart on reboot)
        start_wait  fixed seconds to give cluster to come up initially
        noguidance  omit extraneous guiding
        text_width  for commands rewrapping (0/-1/neg. ~ auto/disable/hi-limit)
    """
    cmd_ctxt['pcscmd_force'] = force
    cmd_ctxt['pcscmd_noauth'] = noauth
    cmd_ctxt['pcscmd_verbose'] = not(silent)
    cmd_ctxt['pcscmd_tmpcib'] = tmp_cib
    cmd_ctxt['pcscmd_dryrun'] = dry_run
    cmd_ctxt['pcscmd_enable'] = enable
    cmd_ctxt['pcscmd_start_wait'] = start_wait
    cmd_ctxt['pcscmd_noguidance'] = noguidance
    cmd_ctxt['text_width'] = text_width
    # XXX possibility to disable cib-meld-templates

    file_proto = protocols.plugins['file'].ensure_proto
    return (
        file_proto(input),
        (
            (
                (
                    (
                        (
                            file_proto(output),
                        ),
                    ),
                ),
            ),
            #ccsflat2cibfinal_output(
            #        (
            #            (
            #                file_proto(output),  # already tracked
            #            ),
            #        ),
            #),
        ),
    )


@CommandAlias.deco
def ccs2pcscmd(cmds, *sys_id):
    # cluster_pcs_needle assumed unless "cluster_pcs_flatiron"
    return (ccs2pcscmd_flatiron if cluster_pcs_flatiron(*sys_id) else
            ccs2pcscmd_needle)
