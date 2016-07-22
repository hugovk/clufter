# -*- coding: UTF-8 -*-
# Copyright 2016 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""ccs2pcs{,-flatiron,-needle} commands"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

from ..command import Command, CommandAlias
from ..facts import cluster_pcs_1_2, cluster_pcs_flatiron
from ..filter import XMLFilter
from ..protocol import protocols
from ..utils import args2tuple
from ..utils_cman import PATH_CLUSTERCONF
from ._chains_pcs import ccsflat2cibfinal_chain, ccsflat2cibfinal_output


def _check_pacemaker_1_2(cmd_ctxt):
    system = cmd_ctxt.get('system') or 'UNKNOWN-SYSTEM'
    system_extra = cmd_ctxt.get('system_extra') or ('UNKNOWN-DISTRO', )
    if not cluster_pcs_1_2(system, system_extra):
        from sys import stderr
        svc_output = cmd_ctxt.get('svc_output',
                                  lambda s, **kwargs: stderr.write(s + '\n'))
        svc_output("Resulting configuration will likely not be applicable to"
                   " ``{0}'' system as it seems so outdated as far as Pacemaker"
                   " not supporting validation schema v1.2"
                    .format(': '.join(args2tuple(system, *system_extra))),
                   base="error",
                   urgent=True,
        )


@Command.deco(('ccs2ccsflat',
                  ('ccs-disable-rg',
                      ('ccs2ccs-pcmk',
                          ('ccs-version-bump'))),
                  (ccsflat2cibfinal_chain)))
def ccs2pcs_flatiron(cmd_ctxt,
                     input=PATH_CLUSTERCONF,
                     ccs_pcmk="cluster-{ccs2ccsflat.in.hash}.conf",
                     cib="cib-{ccs2ccsflat.in.hash}.xml",
                     _common=XMLFilter.command_common):
    """(CMAN,rgmanager)->(Corosync/CMAN,Pacemaker) cluster cfg.

    More specifically, the output is suitable for Pacemaker integrated
    with Corosync ver. 1 (Flatiron) as present, e.g., in RHEL 6.{5, ..},
    and consists of Corosync/CMAN configuration incl. fencing pass-through
    (~cluster.conf) along with Pacemaker proper one (~cib.xml).

    Options:
        input     input (CMAN,rgmanager) cluster configuration file
        ccs_pcmk  output Corosync/CMAN (+fencing pass-through) config. file
        cib       output proper Pacemaker cluster config. file (CIB)
    """
    _check_pacemaker_1_2(cmd_ctxt)

    file_proto = protocols.plugins['file'].ensure_proto
    return (
        file_proto(input),
        (
            (
                (
                    file_proto(ccs_pcmk),
                ),
            ),
            ccsflat2cibfinal_output(
                file_proto(cib),
            ),
        ),
    )


@Command.deco(('ccs2ccsflat',
                  ('ccs-propagate-cman',
                      ('ccs2needlexml',
                          ('xml2simpleconfig'))),
                  (ccsflat2cibfinal_chain)))
def ccs2pcs_needle(cmd_ctxt,
                   input=PATH_CLUSTERCONF,
                   coro="corosync-{ccs2ccsflat.in.hash}.conf",
                   cib="cib-{ccs2ccsflat.in.hash}.xml",
                   _common=XMLFilter.command_common):
    """(CMAN,rgmanager)->(Corosync v2,Pacemaker) cluster cfg.

    More specifically, the output is suitable for Pacemaker integrated
    with Corosync ver. 2 (Needle) as present, e.g., in RHEL 7, and consists
    of Pacemaker (~cib.xml) and Corosync (~corosync.conf) configurations.

    Options:
        input     input (CMAN,rgmanager) cluster configuration file
        coro      output Corosync v2 config. file
        cib       output proper Pacemaker cluster config. file (CIB)
    """
    _check_pacemaker_1_2(cmd_ctxt)

    file_proto = protocols.plugins['file'].ensure_proto
    return (
        file_proto(input),
        (
            (
                (
                    file_proto(coro),
                ),
            ),
            ccsflat2cibfinal_output(
                file_proto(cib),
            ),
        ),
    )


@CommandAlias.deco
def ccs2pcs(cmds, *sys_id):
    # cluster_pcs_needle assumed unless "cluster_pcs_flatiron"
    return ccs2pcs_flatiron if cluster_pcs_flatiron(*sys_id) else ccs2pcs_needle
