# -*- coding: UTF-8 -*-
# Copyright 2014 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""cluster-artefacts command"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

from ..command import Command
from ..protocol import protocols


@Command.deco('ccs-artefacts')
def ccs_artefacts(cmd_ctxt,
                  input="/etc/cluster/cluster.conf",
                  output="cman-artefacts-{ccs-artefacts.in.hash}.conf"):
    """Output artefacts referenced in the config. in CVS format

    Options:
        input   input CMAN-based cluster configuration file
        output  output file with collected artefacts (files, etc.)
    """

    file_proto = protocols.plugins['file'].ensure_proto
    return (
        file_proto(input),
        file_proto(output),
    )
