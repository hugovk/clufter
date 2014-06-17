# -*- coding: UTF-8 -*-
# Copyright 2014 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""Various little+independent helpers"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"


# inspired by http://stackoverflow.com/a/4374075
immutable = lambda x: isinstance(x, (basestring, int, long, bool, float, tuple))

tuplist = lambda x: isinstance(x, (tuple, list))
# turn args into tuple unless single tuplist arg
args2sgpl = \
    lambda x=(), *y: x if not y and tuplist(x) else (x, ) + y
args2combsgpl = arg2wrapped = \
    lambda x=(), *y: x if not y and tuplist(x) and len(x) > 1 else (x, ) + y
args2unwrapped = \
    lambda x=None, *y: x if not y else (x, ) + y
# turn args into tuple unconditionally
args2tuple = lambda *args: tuple(args)
any2iter = \
    lambda x: \
        x if hasattr(x, 'next') and hasattr(x.next, '__call__') \
        else iter(args2sgpl(x, None))

head_tail = \
    lambda x=None, *y, **kwargs: \
        (x, args2sgpl(*y)) if not tuplist(x) or kwargs.get('stop', 0) \
                           else (head_tail(stop=1, *tuple(x) + y))

nonetype = type(None)

filterdict_keep = \
    lambda src, *which, **kw: \
        dict((x, src[x]) for x in which if x in src, **kw)
filterdict_invkeep = \
    lambda src, *which, **kw: \
        dict((x, src[x]) for x in src.iterkeys() if x not in which, **kw)
filterdict_pop = \
    lambda src, *which, **kw: \
        dict((x, src.pop(x)) for x in which if x in src, **kw)
filterdict_invpop = \
    lambda src, *which, **kw: \
        dict((x, src.pop(x)) for x in src if x in which, **kw)


#
# introspection related
#

def isinstanceexcept(subj, obj, exc=()):
    return isinstance(subj, obj) and not isinstance(subj, exc)


def func_defaults_varnames(func, skip=0):
    """Using introspection, get arg defaults (dict) + all arg names (tuple)

    Parameters:
        skip                how many initial arguments to skip
    """
    code = func.func_code
    func_varnames = code.co_varnames[skip:code.co_argcount]

    func_defaults = dict(zip(
        reversed(func_varnames),
        reversed(func.func_defaults)
    ))

    return func_defaults, func_varnames


#
# decorators
#

def selfaware(func):
    """Decorator suitable for recursive staticmethod"""
    def selfaware_inner(*args, **kwargs):
        return func(selfaware(func), *args, **kwargs)
    map(lambda a: setattr(selfaware_inner, a, getattr(func, a)),
        ('__doc__', '__name__'))
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
