# -*- coding: UTF-8 -*-
# Copyright 2015 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

# following 2nd chance import is to allow direct usage context (testing, etc.)
try:
    from ....utils_xslt import xslt_is_member
except ValueError:  # Value?
    from ...utils_xslt import xslt_is_member

ccs_subst_nodes = '''\
    <xsl:key name="node-old-to-new"
             match="/cluster/clusternodes/clusternode/@name"
             use="substring-before(., '@')"/>
    <xsl:template match="/cluster/clusternodes/clusternode/@name">
        <xsl:attribute name="{name()}">
            <xsl:value-of select="substring-after(., '@')"/>
        </xsl:attribute>
    </xsl:template>
    <xsl:template match="/cluster/rm/failoverdomains/failoverdomain/failoverdomainnode/@name">
        <xsl:attribute name="{name()}">
            <xsl:value-of select="substring-after(key('node-old-to-new', .), '@')"/>
        </xsl:attribute>
    </xsl:template>
    <xsl:template match="/cluster/clusternodes/clusternode/fence/method/device[
                             @name = /cluster/fencedevices/fencedevice[
''' + (
                                 xslt_is_member('@agent', ('fence_xvm',
                                                           ))
) + '''                      ]/@name
                         ]/@port">
        <xsl:attribute name="{name()}">
            <xsl:value-of select="substring-after(key('node-old-to-new', .), '@')"/>
        </xsl:attribute>
    </xsl:template>
'''
