# -*- coding: UTF-8 -*-
# Copyright 2017 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

# see also:
# https://github.com/ClusterLabs/pacemaker/blob/Pacemaker-1.1.17-rc2/xml/upgrade-1.3.xsl
# https://github.com/ClusterLabs/pacemaker/pull/1275
#
# NOTE: the first template is a local extension so as to explicitly set the
#       minimum schema version
fmt_cib_1to2 = '''\
<xsl:template match="cib">
  <xsl:copy>
    <xsl:apply-templates select="@*"/>
    <xsl:attribute name="validate-with">
      <xsl:value-of select="$cib2_min_ver"/>
    </xsl:attribute>
    <xsl:apply-templates select="node()"/>
  </xsl:copy>
</xsl:template>

<xsl:template match="role_ref">
  <xsl:element name="role">
    <xsl:apply-templates select="@*|node()"/>
  </xsl:element>
</xsl:template>

<xsl:template match="read|write|deny">
  <xsl:element name="acl_permission">

    <xsl:copy-of select="@id"/>
    <xsl:attribute name="kind"><xsl:value-of select="name()"/></xsl:attribute>

    <!-- previously, one could have a single element "matched" multiple times,
         each time using a different attribute (or no attribute at all), which
         would result, after the generalization (stripping @attribute) in
         multiple possibly conflicting ACL behaviours for given element(s);
         we could take this into account by, at the very least, preferring
         the behavior at attribute-less specification, if any -->
    <xsl:choose>
      <xsl:when test="@ref">
        <xsl:attribute name="reference"><xsl:value-of select="@ref"/></xsl:attribute>
        <xsl:if test="@attribute">
          <!-- alternatively, rephrase (generalized a bit) turning it to @xpath -->
          <xsl:message>ACLs: @attribute cannot accompany @ref for upgrade-1.3.xsl purposes, ignoring</xsl:message>
        </xsl:if>
      </xsl:when>
      <xsl:when test="@tag">
        <xsl:attribute name="object-type"><xsl:value-of select="@tag"/></xsl:attribute>
        <xsl:if test="@attribute">
          <xsl:message>ACLs: @attribute (with @tag) handling generalized a bit for upgrade-1.3.xsl purposes</xsl:message>
          <xsl:copy-of select="@attribute"/>
        </xsl:if>
      </xsl:when>
      <xsl:otherwise>
        <!-- must have been xpath per the schema, then -->
        <xsl:choose>
          <xsl:when test="@attribute">
            <xsl:message>ACLs: @attribute (with @xpath) handling generalized a bit for upgrade-1.3.xsl purposes</xsl:message>
            <xsl:attribute name="xpath">
              <xsl:value-of select="concat(@xpath,'[@', @attribute, ']')"/>
            </xsl:attribute>
          </xsl:when>
          <xsl:otherwise>
            <xsl:copy-of select="@xpath"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:otherwise>
    </xsl:choose>

  </xsl:element>
</xsl:template>

<xsl:template match="acl_user[role_ref]">
  <!-- schema disallows role_ref's AND deny/read/write -->
  <xsl:element name="acl_target">
    <xsl:apply-templates select="@*|node()"/>
  </xsl:element>
</xsl:template>

<xsl:template match="acl_user[not(role_ref)]">

  <xsl:element name="acl_target">
    <xsl:apply-templates select="@*"/>

    <xsl:if test="count(deny|read|write)" >
      <xsl:element name="role">
        <xsl:attribute name="id">
          <xsl:value-of select="concat('auto-', @id)"/>
        </xsl:attribute>
      </xsl:element>
    </xsl:if>

  </xsl:element>

  <xsl:if test="count(deny|read|write)" >
    <xsl:element name="acl_role">
      <xsl:attribute name="id">
        <xsl:value-of select="concat('auto-', @id)"/>
      </xsl:attribute>
      <xsl:apply-templates select="*"/>
    </xsl:element>
  </xsl:if>

</xsl:template>
'''
