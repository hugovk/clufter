# -*- coding: UTF-8 -*-
# Copyright 2014 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""CMAN helpers, mainly used in the filter definitions"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"


def get_nodes(etree):
    return etree.xpath('/cluster/clusternodes/clusternode')
