# -*- coding: UTF-8 -*-
# Copyright 2016 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""Format representing merged/isolated (1/2 levels) of single command to exec"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
from logging import getLogger

log = getLogger(__name__)

from ..format import SimpleFormat
from ..protocol import Protocol
from ..utils import head_tail
from ..utils_func import apply_intercalate


class command(SimpleFormat):
    native_protocol = SEPARATED = Protocol('separated')
    BYTESTRING = SimpleFormat.BYTESTRING
    DICT = Protocol('dict')
    MERGED = Protocol('merged')

    @staticmethod
    def _escape(base, qs=("'", '"')):
        # rule: last but one item in qs cannot be escaped inside enquotion
        ret = []
        for b in base:
            use_qs = qs
            if any(b.startswith(q) or b.endswith(q) for q in use_qs) \
                    or (any(c in b for c in ' #$') and not b.startswith('<<')
                    and not any(b.startswith(s) for s in ("$(", "<("))):
                if '$' in b:
                    use_qs = tuple(c for c in use_qs if c != "'")
                use_q = ''
                for q in use_qs:
                    if q not in b:
                        use_q = q
                        break
                else:
                    use_q = use_qs[-1]
                    if use_q != use_qs[0]:
                        b = b.replace(use_q, '\\' + use_q)
                    else:
                        raise RuntimeError('cannot quote the argument')
                b = b.join((use_q, use_q))
            ret.append(b)
        return ret

    @SimpleFormat.producing(BYTESTRING, chained=True)
    def get_bytestring(self, *protodecl):
        """Return command as canonical single string"""
        # chained fallback
        return ' '.join(self.MERGED(protect_safe=True))

    @SimpleFormat.producing(SEPARATED, protect=True)
    def get_separated(self, *protodecl):
        merged = self.MERGED()
        merged.reverse()
        ret, acc, takes = [], [], 2  # by convention, option takes at most 1 arg
        while merged:
            i = merged.pop()
            # treat `-OPT` followed with `-NUMBER` just as if it was `NUMBER`
            if acc == ['--'] or i is None or \
                    i.startswith('-') and i != '-' and not i[1:].isdigit():
                if not acc:
                    pass
                elif acc[0].startswith('-'):
                    ret.extend(filter(bool, (tuple(acc[:takes]),
                                             tuple(acc[takes:]))))
                else:
                    ret.append(tuple(acc))
                acc, takes = [] if i is None else [i], 2  # reset option-arg cnt
            elif self._dict.get('magic_split', False):
                split = i.split('::')  # magic "::"-split
                if len(acc) == 1 and acc[0].startswith('-') and acc[0] != '-':
                    takes = len(split) + 1  # sticky option multi-arguments
                acc.extend(split)
            else:
                acc.append(i)
            if acc and not merged:
                merged.append(None)  # mark terminal acc -> ret propagation
        return ret

    @SimpleFormat.producing(MERGED, protect=True)
    def get_merged(self, *protodecl):
        # try to look (indirectly) if we have "separated" at hand first
        if self.BYTESTRING in self._representations:  # break the possible loop
            from shlex import split
            ret = split(self.BYTESTRING())
            if self._dict.get('enquote', True):
                ret = self._escape(ret)
            offset = 0
            for i, lexeme in enumerate(ret[:]):
                # heuristic(!) method to normalize: '-a=b' -> '-a', 'b'
                if (lexeme.count('=') == 1 and lexeme.startswith('-') and
                    ('"' not in lexeme or lexeme.count('"') % 2) and
                    ("'" not in lexeme or lexeme.count("'") % 2)):
                    ret[i + offset:i + offset + 1] = lexeme.split('=')
                    offset += 1
        elif self.DICT in self._representations:  # break the possible loop (2)
            d = self.DICT(protect_safe=True)
            if not isinstance(d, OrderedDict):
                log.warning("'{0}' format: not backed by OrderedDict".format(
                    self.__class__.name
                ))
            ret = list(d.get('__cmd__', ()))
            ret.extend((k, v) for k, vs in d.iteritems() for v in (vs or ((), ))
                                  if k not in ('__cmd__', '__args__'))
            ret.extend(d.get('__args__', ()))
        else:
            ret = self.SEPARATED(protect_safe=True)
        return apply_intercalate(ret)

    @SimpleFormat.producing(DICT, protect=True)
    # not a perfectly bijective mapping, this is a bit lossy representation,
    # on the other hand it canonicalizes the notation when turned to other forms
    def get_dict(self, *protodecl):
        separated = self.SEPARATED()
        separated.reverse()
        ret = OrderedDict()
        arg_bucket = '__cmd__'
        while separated:
            head, tail = head_tail(separated.pop())
            if head.startswith('-') and head != '-':
                arg_bucket = '__args__'
            else:
                head, tail = arg_bucket, head
            ret.setdefault(head, []).append(tail)
        return ret
