# -*- coding: UTF-8 -*-
# Copyright 2017 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)

from __future__ import print_function

"""Testing `stringiter-combine*' filter(s)"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

from os.path import join, dirname; from sys import modules as m  # 2/3 compat
b = m.get('builtins', m.get('__builtin__')); e, E, h = 'exec', 'execfile', hash
c = lambda x: compile(x.read(), x.name, 'exec')
with open(join(dirname(dirname(__file__)), '_go')) as f:
    getattr(b, e, getattr(b, E, h)(f.name).__repr__.__name__.__ne__)(c(f))


from os.path import dirname, join
from unittest import TestCase

from .filter_manager import FilterManager
from .format import CompositeFormat
from .formats.string_iter import string_iter
from .utils_2to3 import bytes_enc, str_enc

flt = 'stringiter-combine2'
stringiter_combine2 = FilterManager.init_lookup(flt).filters[flt]


class FiltersStringitercombineTestCase(TestCase):
    def testStringiterCombine2(self):
        result = stringiter_combine2(
            CompositeFormat(
                ('composite', ('bytestringiter', 'bytestringiter')),
                (bytes_enc(b) for b in iter("ABC")),
                (bytes_enc(b) for b in iter("DEF")),
                #"ABC", "DEF",
                formats=(string_iter, string_iter),
            )
        )
        #print(result.BYTESTRING())
        self.assertEqual(str_enc(result.BYTESTRING(), 'utf-8'),
                         '\n'.join("ABCDEF") + '\n')


from os.path import join, dirname; from sys import modules as m  # 2/3 compat
b = m.get('builtins', m.get('__builtin__')); e, E, h = 'exec', 'execfile', hash
with open(join(dirname(dirname(__file__)), '_gone')) as f:
    getattr(b, e, getattr(b, E, h)(f.name).__repr__.__name__.__ne__)(f.read())
