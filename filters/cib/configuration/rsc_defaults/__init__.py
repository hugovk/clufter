# -*- coding: UTF-8 -*-
# Copyright 2015 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

###

from ....filters._2pcscmd import verbose_ec_test, verbose_inform
from ....utils_xslt import NL


cib2pcscmd = ('''\
    <xsl:if test="meta_attributes/nvpair">
''' + (
        verbose_inform('"set resource defaults"')
) + '''
        <xsl:value-of select='concat($pcscmd_pcs, "resource defaults")'/>
        <xsl:for-each select="meta_attributes">
            <xsl:for-each select="nvpair">
                <xsl:value-of select='concat(" &apos;", @name, "=", @value, "&apos;")'/>
            </xsl:for-each>
        </xsl:for-each>
        <xsl:value-of select="'%(NL)s'"/>
''' + (
        verbose_ec_test
) + '''
    </xsl:if>
''') % dict(
    NL=NL,
)
