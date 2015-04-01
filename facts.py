# -*- coding: UTF-8 -*-
# Copyright 2015 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""Utility functions wrt. cluster systems in general"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

from logging import getLogger

from .utils_func import apply_intercalate

log = getLogger(__name__)


#
# EXECUTABLE KNOWLEDGE ABOUT THE CLUSTER PACKAGES PER SYSTEM/DISTROS
#
# or a bit of a logic programming paradigm with Python...
#
# ... first, define some facts (in suitable data structures):
#

# core hierarchical (sparse!) map:
# system -> distro -> release -> package -> version
#
# The notation should be self-explanatory, perhaps except 'component[extra]'
# (borrowed from the very similar construct of setuptools, there can be more
# "extra traits" delimited with comma) ... simply 'pacemaker[cman]' means that
# such pacemaker is somehow associated with "cman" (more specificially, it is
# intended [compilation flags, etc.] to be used with cman), which apparently
# doesn't match 'pacemaker[coro]' component specification in the input query.
cluster_map = {
    'linux':
        {
            'debian': (
                ((6, ), {
                    # https://packages.debian.org/squeeze/{corosync,pacemaker}
                    'corosync':                      (1, 2),
                    'pacemaker[coro,hb]':            (1, 0, 9),
                }),
                ((7, ), {
                    # https://packages.debian.org/wheezy/{corosync,pacemaker}
                    'corosync':                      (1, 4),
                    'pacemaker[coro,hb]':            (1, 1, 7),
                }),
                ((8, ), {
                    # https://packages.debian.org/jessie/corosync (?)
                    'corosync':                      (1, 4, 6),
                }),
            ),
            'fedora': (
                ((13, ), {
                    'corosync':                      (1, 3),
                    'pacemaker[cman]':               (1, 1, 4),
                    #---
                    'pkg::mysql':                   'mysql-server',
                    #---
                    'cmd::pkg-install':             'yum install -y {packages}',
                }),
                ((14, ), {
                    'corosync':                      (1, 4),
                    'pacemaker[cman]':               (1, 1, 6),
                }),
                ((17, ), {
                    'corosync':                      (2, 3),
                    'pacemaker[coro]':               (1, 1, 7),
                }),
                ((18, ), {
                    'pacemaker[coro]':               (1, 1, 8),
                }),
                ((19, ), {
                    'pacemaker[coro]':               (1, 1, 9),
                    #---
                    # https://fedoraproject.org/wiki/Features/ReplaceMySQLwithMariaDB
                    'pkg::mysql':                   'mariadb-server',
                }),
                ((21, ), {
                    'pacemaker[coro]':               (1, 1, 11),
                }),
            ),
            'redhat': (
                ((6, 0), {
                    'corosync':                      (1, 2),
                    #---
                    'pkg::lvm':                     'lvm2',
                    'pkg::mysql':                   'mysql-server',
                    'pkg::postgresql':              'postgresql-server',
                    'pkg::virsh':                   'libvirt-client',
                    #---
                    'cmd::pkg-install':             'yum install -y {packages}',
                }),
                ((6, 2), {
                    'corosync':                      (1, 4),
                }),
                ((6, 5), {
                    'pacemaker[cman]':               (1, 1, 10),
                }),
                ((6, 6), {
                    'pacemaker[acls,cman]':          (1, 1, 11),
                }),
                ((7, 0), {
                    'corosync':                      (2, 3),
                    'pacemaker[coro]':               (1, 1, 10),
                    #---
                    'pkg::mysql':                   'mariadb-server',
                }),
                ((7, 1), {
                    'pacemaker[acls,coro]':          (1, 1, 12),
                }),
            ),
            'ubuntu': (
                ((13, 04), {
                    # https://packages.ubuntu.com/raring/{corosync,pacemaker}
                    'corosync':                      (1, 4),
                    'pacemaker[coro,hb]':            (1, 1, 7),
                }),
                ((13, 10), {
                    # https://packages.ubuntu.com/saucy/{corosync,pacemaker}
                    'corosync':                      (2, 3),
                    'pacemaker[coro,hb]':            (1, 1, 10),
                }),
            ),
        },
}

# mere aliases of the distributions (packages remain the same),
# i.e., downstream rebuilders;
# values in this dict should correspond to output of
# `platform.linux_distribution(full_distribution_name=0)`
# and the dict can contain also associate keys obtained as
# `platform.linux_distribution(full_distribution_name=1).lower()`
aliases_dist = {
    # aliases
    # XXX platform.linux_distribution(full_distribution_name=0), i.e.,
    #     short distro names of Scientific Linux et al. needed
    'centos': 'redhat',
    # full_distribution_name=1 (lower-cased) -> full_distribution_name=0
    'red hat enterprise linux server': 'redhat',
}

# in the queries, one can use following aliases to wildcard versions
# of particular packages
aliases_releases = {
    'corosync': {
        'flatiron':   '1',
        'needle':     '2',
    },
    'debian': {  # because of http://bugs.python.org/issue9514 @ 2.6 ?
        'squeeze':    '6',
        'wheezy':     '7',
        'wheezy/sid': '7.999',
    },
    'ubuntu': {
        'raring':     '13.04',
        'saucy':      '13.10',
    }
}


#
# ...then, define some executable inference rules, starting with their helpers:
#

def _parse_ver(s):
    name, ver = (lambda a, b=None: (a, b))(*s.split('=', 1))
    if ver:
        try:
            ver = aliases_releases[name][ver]
        except KeyError:
            pass
        ver = tuple(map(int, ver.split('.')))
    return name, ver


def _cmp_ver(v1, v2):
    if v1 and v2:
        v1, v2 = list(reversed(v1)), list(reversed(v2))
        while v1 and v2:
            ret = cmp(v1.pop(), v2.pop())
            if ret:
                return ret
    return 0


def _parse_extra(s):
    name, extra = (lambda a, b=None: (a, b))(*s.split('[', 1))
    extra = extra.strip(']').split(',') if extra and extra.endswith(']') else []
    return name, extra


def infer_error(smth, branches):
    raise RuntimeError("This should not be called")


def infer_sys(sys, branches=None):
    log.debug("infer_sys: {0}: {1}".format(sys, branches))
    # lists of system-level dicts
    # -> list of dist-level dicts pertaining the specified system(s)
    if branches is None:
        branches = [cluster_map]
    if sys == "*":
        return apply_intercalate([b.values() for b in branches])
    return [b[sys] for b in branches if sys in b]


def infer_dist(dist, branches=None):
    # list of dist-level dicts
    # -> list of component-level dicts pertaining the specified dist(s)
    # incl. dist alias resolution
    log.debug("infer_dist: {0}: {1}".format(dist, branches))
    if branches is None:
        branches = infer_sys('*')  # alt.: branches = [cluster_map.values()]
    if dist == '*':
        return apply_intercalate([c[1] for b in branches
                                  for c in b.itervalues()])
    ret = []
    dist, dist_ver = _parse_ver(dist)
    try:
        dist = aliases_dist[dist]
    except KeyError:
        pass
    cur_acc = {}
    for b in branches:
        for d, d_branches in b.iteritems():
            if d == dist:
                # first time, we (also) traverse whole sequence of per-distro
                # releases, in-situ de-sparsifying particular packages releases;
                # to avoid needlessly repeated de-sparsifying, we are using
                # '__proceeded__' mark to denote already proceeded dicts
                if '__proceeded__' not in d_branches or dist_ver:
                    for i, (dver, dver_branches) in enumerate(d_branches):
                        if dist_ver:
                            if (_cmp_ver(dist_ver, dver) >= 0 and
                                (i == len(d_branches) - 1
                                or _cmp_ver(dist_ver, d_branches[i+1][0]) < 0)):
                                ret.append(dver_branches)
                                if '__proceeded__' in dver_branches:
                                    break
                                else:
                                    dist_ver = None  # only desparsify since now
                            if '__proceeded__' in dver_branches:
                                continue  # only searching, no hit yet

                        for k, v in dver_branches.iteritems():
                            kk, k_extra = _parse_extra(k)
                            prev_extra = cur_acc.get(kk, '')
                            cur_acc.pop("{0}{1}".format(kk, prev_extra), None)
                            if k_extra:
                                cur_acc[kk] = "[{0}]".format(','.join(k_extra))
                            cur_acc[k] = v
                        for k, v in cur_acc.iteritems():
                            dver_branches[k] = v
                        dver_branches['__proceeded__'] = '[true]'

                if dist_ver is None and not ret:  # alt. above: dist_ver = ''
                    ret.extend(dver_branches for _, dver_branches in d_branches)
    return ret


def infer_comp(comp, branches=None):
    log.debug("infer_comp: {0}: {1}".format(comp, branches))
    # list of component-level dicts
    # -> list of component-level dicts pertaining the specified comp(s)
    # incl. component version alias resolution
    if branches is None:
        branches = infer_dist('*')  # alt.: branches = [cluster_map.values()]
    if comp == '*':
        return branches
    ret = []
    comp, comp_ver = _parse_ver(comp)
    comp, comp_extra = _parse_extra(comp)
    for b in branches:
        for c, c_ver in b.iteritems():
            c, c_extra = _parse_extra(c)
            if (c == comp
                and (not comp_extra or not set(comp_extra).difference(c_extra))
                and _cmp_ver(comp_ver, c_ver) == 0):
                    ret.append(b)
                    break

    return ret

rule_error = (0, infer_error)
inference_rules = {
    # type (of clause): (handling priority, handler)
    'error': rule_error,
    'sys':   (1, infer_sys),
    'dist':  (2, infer_dist),
    'comp':  (3, infer_comp),
}


#
# ...and application-specific inference engine:
#

def infer(query, system=None, system_extra=None):
    """Get/infer answers for system-distro-release-package-version queries

    Query grammar is (currently = least resistance, generalization needed):

    QUERY      ::= TERM | TERM WS* '+' WS* QUERY
    TERM       ::= TYPE:SPEC | comp:COMPSPEC  # comp~component
    WS         ::= [ ]                        # whitespace
    TYPE       ::= sys | dist                 # sys~system, dist~distro
    SPEC       ::= NAME | NAME=SUBSPEC
    COMPSPEC   ::= NAME | NAME-EXTRA | NAME=COMPSUBSPEC | NAME-EXTRA=COMPSUBSPEC
    NAME       ::= [a-zA-Z_-]+                # generally anything reasonable
    SUBSPEC    ::= NUMBER '.' NUMBER | '*'    # arbitrary version as such
    NAME-EXTRA ::= NAME '[' EXTRAS ']'
    EXTRAS     ::= NAME | NAME ',' EXTRAS
    COMPSUBSPEC::= NUMBER '.' NUMBER | NUMBER ',' '*'  # arbitrary minor version
    NUMBER     ::= [0-9]+

    with notes:

    - (COMP)SUBSPEC can be defined as a single number, minor version is assumed
      to be 0 in that case, but it's more like a syntactic sugar thant the
      full-fledged grammar case

    - for simplier expressions, several alias resolutions are in place:
        . distro (almost same set of packages known under different names)
        . component version codename (usually to denote whole major releases)

    - for working examples, see the define predicates below

    """
    # XXX trace_back=comp/dist/sys to anchor the result back in the higher sets
    # XXX only AND is supported via '+', also OR ('/'? even though in some uses
    #     '+' denotes this) together with priority control (parentheses) would
    #     be cool :)
    prev, ret = None, None
    q = [p.strip().split(':', 1) for p in query.split('+')]
    if system:
        q.append(('sys', system.lower()))
    if system_extra:
        q.append(('dist', '='.join(system_extra[:2]).lower()))
    q.sort(key=lambda t: inference_rules.get(t[0], rule_error)[0])
    level = ''
    for q_type, q_content in q:
        inference_rule = inference_rules.get(q_type, rule_error)[1]
        if q_type != level:
            prev = ret
        inferred = inference_rule(q_content, prev)
        log.debug("inferred: {0}".format(inferred))
        ret = [i for i in ret if i in inferred] if q_type == level else inferred
        level = q_type
    return ret


#
# and finally, some wrapping predicates:
#

def cluster_pcs_flatiron(*sys_id):
    """Whether particular `sys_id` corresponds to pcs-flatiron cluster system"""
    return bool(infer("comp:corosync=flatiron + comp:pacemaker[cman]", *sys_id))


def cluster_pcs_needle(*sys_id):
    """Whether particular `sys_id` corresponds to pcs-needle cluster system"""
    return bool(infer("comp:corosync=needle + comp:pacemaker[coro]", *sys_id))


def cluster_pcs_1_2(*sys_id):
    """Whether particular `sys_id` corresponds to pacemaker with 1.2+ schema"""
    return not any((
        infer("comp:pacemaker=1.1.0", *sys_id),
        infer("comp:pacemaker=1.0", *sys_id),
        infer("comp:pacemaker=0", *sys_id),
    ))


def _find_meta(meta, which, *sys_id, **kwargs):
    meta_comp = '::'.join((meta, which))
    res = infer(':'.join(('comp', meta_comp)), *sys_id)
    for i in res:
        if meta_comp in i:
            return i[meta_comp]
    else:
        return kwargs.get('default')


def package(which, *sys_id):
    return _find_meta('pkg', which, *sys_id, default=which)


def cmd_pkg_install(pkgs, *sys_id):
    # ready to deal with pkgs being a generator
    cmd = _find_meta('cmd', 'pkg-install', *sys_id)
    packages = ' '.join(pkgs)
    return cmd.format(packages=packages) if cmd and packages else ''


cluster_systems = (cluster_pcs_flatiron, cluster_pcs_needle)


def cluster_unknown(*sys_id):
    return not(any(cluster_sys(*sys_id) for cluster_sys in cluster_systems))
