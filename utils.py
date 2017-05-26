# -*- coding: UTF-8 -*-
# Copyright 2017 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""Various little+independent helpers"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

from itertools import takewhile
from types import GeneratorType

from .utils_2to3 import PY3, basestring, iter_items


# inspired by http://stackoverflow.com/a/4374075
if PY3:
    immutable = lambda x: isinstance(x, (basestring, int, bool, float, tuple,
                                         GeneratorType))
else:
    immutable = lambda x: isinstance(x, (basestring, int, long, bool, float,
                                         tuple, GeneratorType))

tuplist = lambda x: isinstance(x, (tuple, list, set))
# turn args into tuple unless single tuplist arg
args2sgpl = \
    lambda x=(), *y: x if not y and tuplist(x) else (x, ) + y
arg2wrapped = \
    lambda x=(), *y: \
        x if not y and isinstance(x, tuple) else (x, ) + y
args2unwrapped = \
    lambda x=None, *y: x if not y else (x, ) + y
# turn args into tuple unconditionally
args2tuple = lambda *args: args
any2iter = \
    lambda x: \
        x if hasattr(getattr(x, 'next', getattr(x, '__next__', None)),
                     '__call__') \
        else iter(args2sgpl(x, None))

head_tail = \
    lambda x=None, *y, **kwargs: \
        (x, args2sgpl(*y)) if not tuplist(x) or kwargs.get('stop', 0) \
                           else (head_tail(stop=1, *tuple(x) + y))

nonetype = type(None)

identity = lambda x: x


#
# easily mangle with dicts/sets (eventually lists), returning dicts
#

filterdict_map = \
    lambda fn, src, *which, **update: \
        dict(((x, fn(x)) for x in which if x in src), **update)

# .copy() so as to allow for in-situ manipulations like .pop() without
# affecting the running iteration
filterdict_invmap = \
    lambda fn, src, *which, **update: \
        dict(((x, fn(x)) for x in src.copy() if x not in which), **update)

#

filterdict_keep = \
    lambda src, *which, **update: \
        filterdict_map(
            lambda x, fn=update.pop('_fn_', identity): fn(src[x]),
            src, *which, **update
        )

filterdict_invkeep = \
    lambda src, *which, **update: \
        filterdict_invmap(
            lambda x, fn=update.pop('_fn_', identity): fn(src[x]),
            src, *which, **update
        )

#

filterdict_pop = \
    lambda src, *which, **update: \
        filterdict_map(
            lambda x, fn=update.pop('_fn_', identity): fn(src.pop(x)),
            src, *which, **update
        )

filterdict_invpop = \
    lambda src, *which, **update: \
        filterdict_invmap(
            lambda x, fn=update.pop('_fn_', identity): fn(src.pop(x)),
            src, *which, **update
        )

# following supposes that remove() returns None (as is the case with set/list)

filterdict_remove = \
    lambda src, *which, **update: \
        filterdict_map(
            lambda x, fn=update.pop('_fn_', identity): fn(src.remove(x) or x),
            src, *which, **update
        )

filterdict_invremove = \
    lambda src, *which, **update: \
        filterdict_invmap(
            lambda x, fn=update.pop('_fn_', identity): fn(src.remove(x) or x),
            src, *which, **update
        )


#
# introspection related
#

def isinstanceexcept(subj, obj, *exc):
    return isinstance(subj, obj) and not isinstance(subj, exc)


def isinstanceupto(subj, obj, *exc):
    return isinstance(subj,
                      tuple(takewhile(lambda x: x not in exc, obj.__mro__)))


def areinstances(obj1, obj2):
    return isinstance(obj1, obj2.__class__) or isinstance(obj2, obj1.__class__)


def areinstancesupto(obj1, obj2, *exc):
    return isinstanceupto(obj1, obj2.__class__, *exc) \
        or isinstanceupto(obj2, obj1.__class__, *exc)


def popattr(obj, what, *args):
    assert len(args) < 2
    ret = getattr(obj, what, *args)
    try:
        delattr(obj, what)
    except AttributeError:
        if args:
            ret = args[0]
        else:
            raise
    return ret


def iterattrs(obj, skip_private=True):
    """Iterate through (unbound) attributes of obj, skipping private or not"""
    if skip_private:
        return ((n, v) for n, v in iter_items(obj.__dict__)
                if not n.startswith('__'))
    return iter_items(obj.__dict__)


def func_defaults_varnames(func, skip=0):
    """Using introspection, get arg defaults (dict) + all arg names (tuple)

    Parameters:
        skip                how many initial arguments to skip
    """
    code = func.__code__
    func_varnames = code.co_varnames[skip:code.co_argcount]

    func_defaults = dict(zip(
        reversed(func_varnames),
        reversed(func.__defaults__),
    ))

    return func_defaults, func_varnames


#
# decorators
#

def selfaware(func):
    """Decorator suitable for recursive staticmethod"""
    def selfaware_inner(*args, **kwargs):
        return func(selfaware(func), *args, **kwargs)
    for attr in ('__doc__', '__name__'):
        setattr(selfaware_inner, attr, getattr(func, attr))
    return selfaware_inner


# Inspired by http://stackoverflow.com/a/1383402
class classproperty(property):
    def __init__(self, fnc):
        property.__init__(self, classmethod(fnc))

    def __get__(self, this, owner):
        return self.fget.__get__(None, owner)()


class hybridproperty(property):
    def __init__(self, fnc):
        property.__init__(self, classmethod(fnc))

    def __get__(self, this, owner):
        return self.fget.__get__(None, this if this else owner)()


class hybridmethod(property):
    def __init__(self, fnc):
        property.__init__(self, classmethod(fnc))

    def __get__(self, this, owner):
        return self.fget.__get__(None, this if this else owner)


# inspired from speaklater: http://pypi.python.org/pypi/speaklater
class lazystring(object):
    """Mimic string that in fact is on-off constructed on-demand

    Note: only direct use, str methods and '+' operator supported.
    """
    def __init__(self, fnc, cache=True):
        self._fnc = fnc
        self._cache = cache

    @property
    def content(self):
        ret = self._cache
        if ret is False or ret is True:
            ret = self._fnc()
            if ret is True:
                self._cache = ret
        return ret

    def __str__(self):           return str(self.content)
    def __repr__(self):          return repr(self.content)
    def __getattr__(self, what): return getattr(self.content, what)
    def __add__(self, other):    return self.content + other
    def __radd__(self, other):   return other + self.content
