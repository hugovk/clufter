# -*- coding: UTF-8 -*-
# Copyright 2017 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""Base format stuff (metaclass, classes, etc.)"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

# TODO: NamedTuple for tree_stack

import hashlib
from copy import deepcopy
from functools import reduce
from glob import glob
from imp import find_module, load_module
from itertools import dropwhile, islice
from logging import getLogger
from os import extsep, fdopen, stat, walk
from os.path import basename, commonprefix, dirname, exists, join, sep, splitext
from sys import modules
from time import time

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from lxml import etree

try:
    from .defaults import HASHALGO
except ImportError:
    HASHALGO = 'md5'
from .error import ClufterError, ClufterPlainError
from .plugin_registry import MetaPlugin, PluginRegistry
from .protocol import Protocol
from .utils import arg2wrapped, args2sgpl, args2tuple, args2unwrapped, \
                   classproperty, \
                   filterdict_keep, \
                   filterdict_pop, \
                   head_tail, \
                   hybridmethod, \
                   immutable, \
                   iterattrs, \
                   isinstanceupto, \
                   popattr, \
                   tuplist
from .utils_2to3 import MimicMeta, basestring, bytes_enc, iter_items, xrange
from .utils_func import bifilter_unpack, foreach
from .utils_lxml import etree_parser_safe
from .utils_prog import ProtectedDict, getenv_namespaced, namever_partition
from .utils_xml import rng_get_start, rng_pivot

log = getLogger(__name__)

DEFAULT_ROOT_DIR = join(dirname(__file__), 'formats')


class FormatError(ClufterError):
    pass

class FormatPlainError(ClufterPlainError, FormatError):
    pass


class formats(PluginRegistry):
    """Format registry (to be used as a metaclass for formats)"""
    def __init__(cls, name, bases, attrs):
        # could be called multiple times but only once per respective
        # __new__ (in plugin_registry) is required, rest would be waste
        # of resources if not harmful due to non-idempotent modifications
        if cls._probes > 1:
            return

        cls._protocols, cls._validators, cls._protocol_attrs = {}, {}, set()
        cls._context = set(popattr(cls, 'context_specs',
                                   attrs.pop('context_specs', ())))
        cls._update_to = OrderedDict()  # to be filled "retrospectively"
        compat = popattr(cls, 'compat_contingency',
                         attrs.pop('compat_contingency', ()))
        cls._update_from = OrderedDict((c.in_format, c) for c in compat)
        # protocols merge: top-down through inheritance
        # (real base class goes last, rest are "convertible siblings")
        for i, base in enumerate(reversed(bases)):
            if i or base is MetaPlugin:  # not a proper base or CompositeFormat
                continue
            cls._protocols.update(getattr(base, '_protocols', {}))
            cls._validators.update(getattr(base, '_validators', {}))
            cls._context.update(getattr(base, '_context', ()))
            cls._protocol_attrs.update(getattr(base, '_protocol_attrs', ()))
            if cls.name in base._update_from:
                base._update_from[cls] = flt = base._update_from.pop(cls.name)
                cls._update_to[base] = flt
        # updated with locally defined proto's (marked by `producing` wrapper)
        specs = popattr(cls, 'validator_specs',
                        attrs.pop('validator_specs', {}))

        for attr, obj in iterattrs(cls):
            if isinstance(obj, Protocol):
                cls._protocol_attrs.add(attr)
                continue
            try:
                protocol = obj._protocol
                delattr(obj, '_protocol')
                cls._protocols[protocol] = cls, attr
                cls._validators[protocol] = obj._validator, None
                delattr(obj, '_validator')
            except AttributeError:
                if not hasattr(obj, '_protocol'):
                    assert attr not in cls._protocols, 'Unexpected override'

        for protocol in cls._protocols:
            newspec = specs.get(protocol, None)
            validator, spec = cls._validators.get(protocol, (None, ''))
            newspec = newspec if newspec is not None else spec
            if validator:
                cls._validators[protocol] = validator, newspec


class _Format(object):
    """Base for configuration formats

    Base principles:
        - protocols: string label denoting how to int-/externalize
          - union of protocols within inheritance hierarchy and
            locally defined ones (prioritized)
            - to define one, add a method decorated with
              `@Format.producing(<proto>)`
            - be default, all such protocols are suitable for both
              int- and externalization, but you can prevent the latter
              context by raising an exception in the method body
        - create format instance = internalize, call = externalize
        - protocols are property of the class, representation of an instance
        - basic inheritance rules apply to formats as well, notably that
          an instance of expected class' subclass is generally acceptable,
          but there are very specific subtleties that should rather be
          spelled out:
          - for a format hierarchy that explicitly arranges for older-to-newer
            instance upgrades (`cib` family of formats is one such example)
            - inheritance for `fmt` placeholder format should be arranged
              like this:  Format <-- ... <-- fmt <-- fmtN <-- ... <-- fmtM
              (also, care to stick with a linear inheritance between formats)
              (where "<--" denotes inheritance as usual, and fmtM/fmtN
              stands for oldest/newest supported version, respectively, hence
              we can conclude that older format versions derive from newer
              ones, transitively)
            - `fmt` top of the formats hierarchy should be the generalization
              of the format, that is, able to accept arbitrary instance of
              its subclasses-or-self (as long as the format has a way to
              distinguish the format version internally so it won't get lost)
            - for the rest (tail) of the hierarchy, we can easily see that
              instances of newer format versions cannot be used where older
              ones are explicitly required (forward-consciousness is not
              assumed at all), but the opposite direction, that is,
              backward-consciousness, is deliberately possible, implicitly
              through trial-and-error (a.k.a. lazy) arrangement (see below)
            - implicit forward compatibility takes the least-resistance
              approach -- no hassles are needed when an instance of an older
              format version validates per requirements imposed on the newer
              format, otherwise this new format is supposed to specify
              filter(s), via its `compat_contingency` member, sufficient
              to promote the older instance so it eventually validates
              (it's a fatal failure if this cannot be achieved)


    Little bit of explanation:

                           FORMAT INSTANCE
                           (concrete data)
     INSTANTIATION    /-----------------------\       CALL        /--------
     (internalize)    | -protocols = set(...) |   (externalize)   | effect
    ----------------->| -representations =    |------------------>| and/or ...
    (protocol, *args) |   {protocol: (*args)} | (protocol, *args) |  value
           ^          \-----------------------/             ^     \--------
           |                                                |
           |                                                |
           +-- adds (protocol, *args) to representations,   |
               usually does nothing else (lazy approach)    |
                                                            |
             with each protocol there is a representation --+
             of concrete data associated,  either this or
             any other  that  can be promoted  (awakening
             from the previous laziness)  to the desired
             one is required

        Externalization methods are marked with `producing` decorator
        that takes protocol name as a parameter.

    """
    context_specs = 'validator_specs', 'compat_contingency'

    @MimicMeta.passdeco(classproperty)
    def context(self):
        return tuple(self._context)

    @MimicMeta.passdeco(classproperty)
    def native_protocol(self):
        """Native protocol"""
        raise AttributeError

    ###

    @MimicMeta.method
    def _swallow(self, protocol, *args):
        """Called by native constructor/producer to store a format instance"""
        if protocol == 'native':
            protocol = self.native_protocol

        assert protocol in self._protocols, ("unrecognized protocol `{0}'"
                                             .format(protocol))
        assert args != (None, )
        constructing = not self._representations  # called from constructor
        prev = self._representations.setdefault(protocol, args)
        assert prev is args

        if not constructing:
            return  # trust that equivalent of once validated keeps the property
        log.debug("Will try to validate `{0}' instance"
                  .format(self.__class__.name))

        cands = (protocol, self.native_protocol) + tuple(self._validators)[:1]
        validating_protocol = args2unwrapped(*islice(dropwhile(lambda x: x not in
                                                               self._validators,
                                                               cands), 1))
        validator = self.validator(validating_protocol)
        if not validator:
            return  # cannot validate in any way

        obj = self(validating_protocol)
        entries, _ = head_tail(validator(obj))
        if isinstance(entries, basestring):
            log.warning(entries)
        elif entries:
            raise FormatError(self, "Validation: {0}".format(
                ', '.join(':'.join(args2tuple(str(e[0]), str(e[1]), *e[2:]))
                          for e in entries))
            )

    @MimicMeta.method
    def producer(self, protocol):
        protocol_cls, protocol_attr = self._protocols[protocol]
        if protocol_cls is self.__class__:
            return getattr(self, protocol_attr)  # has to be self
        return getattr(super(self.__class__, self), protocol_attr)

    @MimicMeta.method
    def produce(self, protocol, *args, **kwargs):
        """Called by implicit invocation to get data externalized"""
        if protocol == 'native':
            protocol = self.native_protocol

        assert protocol in self._protocols
        ret = self.producer(protocol)(protocol, *args, **kwargs)
        if ret is None:
            raise FormatError(self, "Cannot produce `{0}' format"
                                    " as `{1}'"
                                    .format(self.__class__.name, protocol))
        return ret

    @MimicMeta.method
    def __new__(cls, protocol, *args, **kwargs):
        """Format pre-constructor (possibly format-upgrading to parent class)"""
        good, bad = bifilter_unpack(lambda c, f: not isinstance(c, basestring),
                                    iter_items(cls._update_from))
        if bad:
            log.warning("Unresolved update-from filters for `{0}': {1}".format(
                        cls.name, ','.join(c for (c, _) in bad)))
        retself, worklist = None, list(reversed(good)) + [(cls, None)]
        while worklist:
            tryfmt, tryflt = worklist.pop()
            log.debug("Trying pre-construction of `{0}' format going from"
                      " `{1}'{2}"
                      .format(cls.name, tryfmt.name,
                              tryflt.name.join((" (using `", "' filter)"))
                              if tryflt else ""))
            try:
                # for tryflt case, we cannot use `tryflt.in_format` as it is
                # just a string here
                obj = object.__new__(tryfmt)
                obj._construct(protocol, *args, **kwargs)
                if not tryflt:
                    retself = obj
                else:
                    # note that tryflt is filter class that needs to be
                    # instantiated by being passed dictionary to resolved
                    # its formats at
                    flt = tryflt(formats={
                        tryflt.in_format: tryfmt,
                        cls.name: cls,
                    })
                    retself = flt(obj)
            except FormatError as e:
                retself = e
                continue
            else:
                break
        assert retself
        if isinstance(retself, FormatError):
            raise retself
        return retself

    @MimicMeta.method
    def _construct(self, protocol, *args, **kwargs):
        """Format constructor, i.e., object = concrete internal data"""
        # cannot be doubly-undescored otherwise the "foreign lookup" will miss
        assert not(getattr(self, '_representations', None)), "int. API misuse"
        rs = {}
        self._representations, self._representations_ro = rs, ProtectedDict(rs)
        if not hasattr(self, '_hash'):  # can be defined at the class level
            self._hash = None
        validator_specs = kwargs.pop('validator_specs', {})
        default = validator_specs.setdefault('', None)  # None ~ don't track
        validators = {}
        for p in self._validators:
            spec = validator_specs.get(p, default)
            if spec is None:
                continue
            validators[p] = (self._validators[p][0], spec)
        if validators:  # force per-instance customization
            self._validators = dict(self._validators, **validators)
        self._dict = kwargs
        # supercharge protocol objects with callability to provide
        # a syntactic sugar: self(self.PROTO, ...) -> self.PROTO(...))
        for attr in self._protocol_attrs:
            def get_protocol_proxy(obj):
                class wrapped_call(object):
                    #def __getattribute__(this, name):
                    #    return obj.__getattribute__(name)
                    #def __str__(self):
                    #    return str(obj)
                    def __call__(this, *a, **kw):
                        return self(this, *a, **kw)
                    def __eq__(self, other):
                        return str(obj) == other
                    def __hash__(self):  # for "x in bars"
                        return hash(obj)
                return wrapped_call()
            log.debug("Proxying {0} to add callability".format(attr))
            setattr(self, attr, get_protocol_proxy(getattr(self, attr)))
        self._swallow(protocol, *args)

    @MimicMeta.passdeco(classmethod)
    def common_protocols(cls, foreign):
        """Get common local vs. foreign protocols, native ones prioritized"""
        # XXX composite format
        if not hasattr(foreign, '_protocols'):
            raise FormatError(cls, "cannot check common protocols for `{0}'",
                              repr(foreign))
        return sorted(
            reduce(
                set.intersection,
                map(set, (cls._protocols, foreign._protocols))
            ),
            key=lambda x:
                int(x == cls.native_protocol) * 2
                + int(x == foreign.native_protocol)
        )

    @MimicMeta.classmethod
    def as_instance(cls, *decl_or_instance, **kwargs):
        """Create an instance or verify and return existing one"""
        if decl_or_instance and isinstance(decl_or_instance[0], Format):
            instance = decl_or_instance[0]
            if not isinstanceupto(instance, cls, Format):
                raise FormatError(cls, "input object: format mismatch"
                                  " (expected `{0}' or a superclass, got"
                                  " `{1}')", cls.name, instance.__class__.name)
            if instance.__class__.__bases__[0] is cls:
                return instance

            # convert using (preferably native) protocol
            com = instance.common_protocols(cls)
            if not com:
                raise FormatError(cls, "no common protocol with source format"
                                       " `{0}'", instance.name)
            decl_or_instance = (com[0], instance(com[0]))

        instance = cls(*decl_or_instance, **kwargs)
        return instance

    @MimicMeta.method
    def __call__(self, protocol='native', *args, **kwargs):
        """Way to externalize object's internal data"""
        return self.produce(protocol, *args, **kwargs)

    @MimicMeta.passdeco(classproperty)
    def protocols(self):
        """Set of supported protocols for int-/externalization"""
        return self._protocols.keys()  # installed by meta-level

    @MimicMeta.passdeco(hybridmethod)
    def validator(this, protocol=None, spec=None):
        """Return validating function or None

        This ought to be the authoritative (and only) way to use
        a validator, do not touch _validators and also validator_specs
        is dropped from class attributes for this very reason.
        """
        which = this.native_protocol if protocol is None else protocol
        try:
            validator, sp = this._validators[which]  # installed by meta-level
        except KeyError:
            return None
        spec = spec if spec is not None else sp
        if spec == '':
            return None
        return lambda *args, **kwargs: validator(this, *args,
                                                 **dict(kwargs, spec=spec))

    @MimicMeta.passdeco(property)
    def hash(self):
        if self._hash is None:
            raise NotImplementedError
        return self._hash

    @MimicMeta.passdeco(property)
    def representations(self):
        """Mapping of `protocol: initializing_data`"""
        # XXX should be ProtectedDict
        return self._representations_ro

    @MimicMeta.staticmethod
    def producing(protocol, chained=False, protect=False, validator=None):
        """Decorator for externalizing method understood by the `Format` magic

        As a bonus: caching of representations."""
        def deco_meth(meth):
            def deco_args(self, protocol, *args, **kwargs):
                # XXX enforce nochain for this iterative processing?
                do_protect = protect and not kwargs.pop('protect_safe', False)
                produced = None
                try:
                    # stored -> computed norm.: detuple if len == 1
                    produced = args2unwrapped(*self._representations[protocol])
                except KeyError:
                    produced = None
                    # seemingly absurd inversion of starting with this `prev`:
                    # arranged like this for empty _protocols (hence `get`s)
                    worklist = [(Format, self.__class__)] * 2
                    this_proto = self._protocols[protocol]
                    while worklist:
                        prev_cls, that_cls = worklist.pop()
                        that_proto = that_cls._protocols[protocol]
                        prev_proto = prev_cls._protocols.get(protocol)
                        if that_proto in (this_proto, prev_proto):
                            if worklist or that_proto == prev_proto:
                                if chained:
                                    worklist.extend((that_cls, b) for b in
                                                    that_cls.__bases__ if
                                                    protocol in b._protocols)
                                 # also ensures meth fired atmost once (@level?)
                                continue
                            producer = lambda *args, **kwargs: \
                                           meth(self, *args, **kwargs)
                        else:
                            producer = getattr(super(prev_cls, self),
                                               that_proto[1])
                        produced = producer(protocol, *args, **kwargs)
                        if produced is None:
                            continue
                        if (that_cls is self.__class__
                            and protocol not in self._representations):
                            # computed -> stored normalization
                            self._swallow(protocol, *arg2wrapped(produced))
                        else:
                            do_protect = False
                        break

                if do_protect and not immutable(produced):
                    log.debug("{0}:{1}:Forced deepcopy of `{2}' instance"
                              .format(self.__class__.name, meth.__name__,
                                      type(produced).__name__))
                    produced = deepcopy(produced)
                return produced

            deco_args.__name__, deco_args.__doc__ = meth.__name__, meth.__doc__
            deco_args._protocol = protocol  # mark for later recognition
            if validator:
                deco_args._validator = validator
            return deco_args
        return deco_meth


Format = MimicMeta('Format', formats, _Format)


class Nothing(Format):
    """Empty format, typically an input for "generator" type of filters"""
    native_protocol = VOID = Protocol('void')

    _hash = hash(None)

    @Format.producing(VOID)
    def get_void(self, *iodecl):
        pass  # same as return None


class SimpleFormat(Format):
    """This is what most of the format classes want to subclass"""
    native_protocol = BYTESTRING = Protocol('bytestring')
    FILE = Protocol('file')
    void_file = '/dev/null'  # XXX not multi-platform

    def _construct(self, protocol, *args, **kwargs):
        """Format constructor, i.e., object = concrete uniformat data"""
        assert isinstance(protocol, basestring), \
               "protocol has to be string for `{0}', not `{1}'" \
               .format(self.__class__.name, protocol)
        super(SimpleFormat, self)._construct(protocol, *args, **kwargs)

    @Format.producing(BYTESTRING)
    def get_bytestring(self, *iodecl):
        if self.FILE in self._representations:  # break the possible loop
            infile = self.FILE()
            if hasattr(infile, 'read'):
                # assume fileobj out of our control, do not close
                return bytes_enc(infile.read(), 'utf-8')

            assert isinstance(infile, basestring)
            with open(infile, 'rb') as f:
                return f.read()

    @Format.producing(FILE)
    def get_file(self, *iodecl):
        outfile = iodecl[-1]
        if hasattr(outfile, 'write'):
            # assume fileobj out of our control, do not close
            if hasattr(outfile, 'buffer'):  # PY3: std{in,out,err} text mode
                outfile.buffer.write(self.BYTESTRING())
            else:
                outfile.write(self.BYTESTRING())
            return outfile.name

        assert isinstance(outfile, basestring)
        with open(outfile, 'wb') as f:
            f.write(bytes_enc(self.BYTESTRING(), 'utf-8'))
        return outfile

    @property
    def hash(self):
        """Compute hash trying to uniquely identify the format instance"""
        if self._hash is None:
            # to prevent possible brute-force-based attacks on e.g.,
            # configuration files with sensitive data obfuscated
            # but with hash of the original contained in the output
            # filename as per the common interpolation, we add some
            # salt based either on input's mtime (if it is a file)
            # or current UNIX time (otherwise -- as we cannot anchor
            # it reliably anyway);  this way in such cases, for the
            # unchanged input provided as a file, we always get the
            # identical respective part of the output name, without
            # putting the content of the original at risk (hopefully)
            #
            # manual verification (provided HASHALGO=md5, default):
            # w/o salt:   md5sum $FILE
            # with salt:  { stat --printf "%Y" $FILE; cat $FILE; } | md5sum
            content, salt = '', ''
            hash_algo = getenv_namespaced('HASHALGO', HASHALGO)
            do_salt = getenv_namespaced('NOSALT', '0') in ('0', 'false')
            try:
                hash_algo = getattr(hashlib, hash_algo)
            except AttributeError:
                log.warning("`{0}' hash algorithm unknown".format(hash_algo))
                hash_algo = hashlib.md5
            try:
                h = hash_algo()
            except:
                h = hash_algo(usedforsecurity=False)  # Fedora/RHEL-specific

            if self.FILE in self._representations:
                if do_salt:
                    try:
                        salt = str(int(stat(self.FILE()).st_mtime))
                    except (OSError, TypeError):  # TypeError~coerce to Unicode
                        pass
                self.BYTESTRING()  # ensure bytestring repr (assumed "cheap")

            if not salt and do_salt:
                salt = str(int(time()))
            h.update(bytes_enc(salt))

            if self.BYTESTRING in self._representations:
                content = self.BYTESTRING()
            else:
                content = str(hash(self))
            h.update(bytes_enc(content))

            # only use first quarter of the whole hexdigest
            self._hash = h.hexdigest()[:h.digest_size//2]  # expected even
        return self._hash

    @classmethod
    def io_decl_specials(cls, io_decl, in_mode, magic_fds, interpolations={}):
        """Special file decl. treatment: "magic files", string interpolation

        Only return number if we've hit "magic file" (otherwise None),
        preceded with the string interpolation (via string.format())
        behind the curtains for "file" decl.
        """
        # turning @DIGIT+ magic files into fileobjs (needs global view)
        if tuplist(io_decl) and len(io_decl) >= 2 and io_decl[0] == cls.FILE:
            try:
                # incl. late/dynamic interpolation of defaults ~ filters' inputs
                io_decl = args2tuple(io_decl[0],
                                     io_decl[1].format(**interpolations),
                                     *io_decl[2:])
            except (ValueError, KeyError):
                pass
            except ((AttributeError, ) if not in_mode else ()):
                pass  # input terminals have to be interpolation-complete by now
            fdef = io_decl[1]
            fdef = "@{0}".format(int(not(in_mode))) if fdef == '-' else fdef
            if (isinstance(fdef, basestring)
                    and fdef.rstrip('0123456789') == '@'):
                fd = int(fdef[1:])
                if fd not in magic_fds:
                    # XXX be careful about not duplicating? (especially '-')
                    #     maybe even nothing should be duplicated at all?
                    try:
                        magic_fds[fd] = fdopen(fd, 'r+b' if in_mode else 'ab')
                    except (OSError, IOError):
                        # keep untouched
                        pass
                    else:
                        return io_decl
                io_decl = args2sgpl(io_decl[0], magic_fds[fd],
                                    *io_decl[2:])
        return io_decl


class CompositeFormat(Format, MetaPlugin):
    """Quasi-format to stand in place of multiple formats at once

    It is intended to build on top of atomic formats (and only these,
    i.e., multi-level nesting is not supported as it doesn't bring
    any better handling anyway).

    Common format API is overridden so as to be performed per each
    contained/designated format in isolation, whereas the aggregated
    result is then returned.

    Note that the semantics implicitly require protocols prescribing
    the `CompositeFormat` instantiation to also become "composite",
    i.e., having form like ('composite', ('file', 'file')) instead
    of mere scalar like 'file' (IOW, whole declaration remains
    fully "typed").

    See also: Format, SimpleFormat
    """
    native_protocol = 'composite'  # to be overridden by per-instance one
                                   # XXX: hybridproperty?

    # XXX def __new__

    def _construct(self, protocol, *args, **kwargs):
        """Format constructor, i.e., object = concrete multiformat data

        Parameters:
            protocol    protocol, should match: ('composite', ('file', ...))
                        where 'file' is indeed variable
            args        each should represent arguments to be passed
                        into format instantiation for respective (order-wise)
                        protocol within the composite one
            kwargs      further keyword arguments; supported:
                        formats     iterable of format classes involved,
                                    matching the order of the "proper data
                                    part" within protocols
        """
        assert isinstance(protocol, tuple) and protocol \
               and protocol[0] == self.__class__.native_protocol, \
               "protocol has to be tuple initiated with {0} for {1}" \
               .format(self.__class__.native_protocol, self.__class__.__name__)
        formats = kwargs.pop('formats')  # has to be present
        # further checks
        assert len(protocol) > 1
        assert tuplist(protocol[1]) and len(protocol[1]) > 1
        assert tuplist(formats) and len(protocol[1]) == len(formats)
        assert len(args) == len(formats)
        assert all(p in f._protocols or p == 'native'
                   for (f, p) in zip(formats, protocol[1]))
        self._protocols[protocol] = lambda *_: args  # just to pass the assert
        self.native_protocol = (self.__class__.native_protocol,
                                tuple(f.native_protocol for f in formats))
        # instantiate particular designated formats
        self._designee = tuple(
            f(p, *args2tuple(a), **kwargs)
            for (f, p, a) in zip(formats, protocol[1], args)
        )
        super(CompositeFormat, self)._construct(protocol, *args, **kwargs)

    def __iter__(self):
        return iter(self._designee)

    def __getitem__(self, index):
        return self._designee[index]

    def produce(self, protocol, *args, **kwargs):
        """Called by implicit invocation to get data externalized"""
        if protocol == 'native':
            protocol = self.native_protocol

        assert tuplist(protocol) and len(protocol) > 1
        assert protocol[0] == self.__class__.native_protocol
        assert len(protocol[1]) == len(self._designee)
        args = args or ((),) * len(protocol[1])
        # should call produce instead
        return tuple(f.producer(p)(p, *a, **kwargs)
                     for f, p, a in zip(self._designee, protocol[1], args))

    @property
    def hash(self):
        """Compute hash trying to uniquely identify the format instance"""
        if self._hash is None:
            self._hash = hex(reduce(lambda a, b: a ^ int(b.hash, base=16),
                                    self._designee, 0))[2:]
        return self._hash  # XXX hex digest can possibly be shorter that normal


class XML(SimpleFormat):
    """Base for XML-based configuration formats"""

    MAX_DEPTH = 1000

    root = ''  # root tag of the XML document

    @staticmethod
    def _walk_schema_step_up(tree_stack):
        """Step up within the tree_stack (bottom-up return in dir structure)"""
        child_root, child_data = (lambda x, *y: (x, y))(*tree_stack.pop())
        log.debug("Moving upwards: `{0}' -> `{1}'"
                  .format(child_root, tree_stack[-1][0]))
        current_tracking = tree_stack[-1][2]
        if len(child_data[1]):
            name = basename(child_root)
            if name in current_tracking:
                to_update = current_tracking[name][1]
            else:
                to_update = current_tracking
            to_update.update(child_data[1])

        return current_tracking

    @staticmethod
    def _walk_schema_step_down(tree_stack, root):
        """Step down within the tree_stack (top-down diving in dir structure)

        Based on the fact that we traverse down by one level to already
        (shallowly) explored level so the item is already tracked at
        the parent and the shallow knowledge (dict) is passed down to be
        potentially extended -- as dict is mutable, this knowledge
        is shared between parent and child level.
        """
        log.debug("Moving downwards:`{0}' -> `{1}'"
                  .format(tree_stack[-1][0], root))
        tree_stack.append((root, None, {}))

        return tree_stack[-1][2]  # current tracking

    @classmethod
    def walk_schema(cls, root_dir, symbol=None, preprocess=lambda s, n: s,
                    sparse=True, xml_root=None):
        """
        Get recipe for visiting symbol(s) within the XML as (sparsely) arranged

        Example of output::

            {
                'A': (<symbol>, {
                    'C': (<symbol>, {}),
                    'D': (<symbol>, {
                        'F': (<symbol>, {
                        })
                    })
                })
                'Z': (<symbol>, {})
            }

        NB: order of keys really does not matter.
        """
        xml_root = xml_root or cls.root
        particular_namespace = '.'.join((cls.namespace, symbol or xml_root))
        result = {}
        tree_stack = [(root_dir, None, result)]  # for bottom-up reconstruction
        for root, dirs, files in walk(root_dir):
            try:
                dirs.remove('__pycache__')  # PY3
            except ValueError:
                pass
            # multi-step upwards and (followed by)/or single step downwards
            while commonprefix((root, tree_stack[-1][0])) != tree_stack[-1][0]:
                cls._walk_schema_step_up(tree_stack)
            if root != tree_stack[-1][0]:
                current_tracking = cls._walk_schema_step_down(tree_stack, root)
            else:
                assert root == root_dir
                # at root, we do not traverse to any other dir than `xml_root`
                foreach(lambda d: d != xml_root and dirs.remove(d), dirs[:])
                current_tracking = tree_stack[-1][2]
                files = []

            for i in dirs + files:
                name, ext = splitext(i)  # does not hurt even if it is a dir
                if name.startswith('_') or name.startswith('.') \
                or i in files and ext != extsep + 'py':
                    continue

                log.debug("Trying `{0}' at `{1}'".format(name, root))
                mfile, mpath, mdesc = find_module(name, [root])
                # need to obfuscate the name due to, e.g., "logging" clash
                mname = '.'.join((particular_namespace, 'walk_' + name))
                # suppress problems with missing parent in module hierarchy
                modules.setdefault(particular_namespace, modules[__name__])
                if mname in modules:
                    mod = modules[mname]
                    if hasattr(mod, '__path__') and mod.__path__[0] != mpath:
                        # XXX robust?
                        raise FormatError(cls, "`{0}' already present"
                                          .format(mname))
                else:
                    try:
                        mod = load_module(mname, mfile, mpath, mdesc)
                    except ImportError as e:
                        log.warning("Cannot load `{0}': {1}".format(mpath, e))
                        continue
                    finally:
                        if mfile:
                            mfile.close()

                available = set(dir(mod)) - set(dir(type(mod)))
                swag = None
                if not symbol or symbol in available:
                    swag = getattr(mod, symbol) if symbol else tuple(available)
                    swag = preprocess(swag, name)
                if swag is None and (sparse or i in files):
                    continue  # files are terminals anyway
                current_tracking[name] = (swag, {})

        for i in xrange(cls.MAX_DEPTH):
            try:
                if cls._walk_schema_step_up(tree_stack) is result:
                    return result
            except IndexError:
                raise FormatError(cls, "Format tree structure inconsistency"
                                       " detected")
        else:
            raise FormatError(cls, "INFLOOP detected")

    ###

    native_protocol = ETREE = Protocol('etree')
    BYTESTRING = SimpleFormat.BYTESTRING

    validator_specs = {
        ETREE: '*.rng'  # grab whatever you'll find (with backtrack)
    }

    @classmethod
    def _etree_rng_validator_specs(cls, root_dir=None, spec=None):
        if modules[cls.__module__].__file__ == __file__:
            spec = ()    # skip validating for plain XML
        else:
            if spec is None:
                _, spec = cls._validators[cls.ETREE]  # installed by meta-level
            # XXX use spec getter a was the intention before
            if not root_dir:
                root_dir = dirname(modules[cls.__module__].__file__)
            if sep not in spec:
                spec = join(root_dir, cls.root, spec)
            if any(filter(lambda c: c in spec, '?*')):
                globbed = glob(spec)
                spec = globbed or spec
            elif exists(spec):
                spec = args2tuple(spec)
            if not tuplist(spec):
                raise FormatPlainError("Cannot validate, no matching spec:"
                                       " `{0}'".format(spec))
        return spec

    @classmethod
    def etree_rng_validator_proper_specs(cls, **kwargs):
        """Return class-exclusive validating RNG files, name/version ordered"""
        specs = set(cls._etree_rng_validator_specs(
            **filterdict_keep(kwargs, 'root_dir', 'spec')
        ))
        ancestor_specs = set()
        for ancestor in cls._update_from:
            this_ancestor_specs = ancestor._etree_rng_validator_specs(
                **filterdict_keep(kwargs, 'root_dir', 'spec')
            )
            if this_ancestor_specs:
                ancestor_specs.update(this_ancestor_specs)
        specs.difference(ancestor_specs)
        return sorted(specs, key=lambda x: namever_partition(splitext(x)[0]))

    @classmethod
    def etree_rng_validator(cls, et, start=None, **kwargs):
        """RNG-validate `et` ElementTree with schemes as per `root_dir`+`spec`

        ... and, optionally, narrowed to `start`-defined grammar segment.

        The `spec` can either be relative (`root` is an initial path then)
        or absolute wildcard (as in shell  globbing) or specific name.
        All validators matching the specification will be tried in an
        alphabetical order, first success wins, overall validation fails
        otherwise.

        `start` is either plain tag or namespaced one using Clark's notation.

        Returns tuple of:
            iterable of validation errors
            path of the "master" validating schema (first good one/last used)
            snippet from "master" validating schema relevant to `start`
        """
        # XXX holds its private cache under cls._validation_cache
        try:
            spec = cls._etree_rng_validator_specs(
                **filterdict_pop(kwargs, 'root_dir', 'spec')
            )
        except FormatPlainError as e:
            return (((0, 0, str(e)), ), None, None)
        fatal, master, master_snippet = [], '', ''
        for s in reversed(sorted(spec)):
            fatal, master = [], s
            try:
                schema, rng = cls._validation_cache.get(s, (None, None))
            except AttributeError:
                setattr(cls, '_validation_cache', {})
                schema = None
            if schema is None:
                try:
                    schema = etree.parse(s, parser=etree_parser_safe)
                    rng = etree.RelaxNG(schema)
                    cls._validation_cache[s] = schema, rng
                except (etree.RelaxNGError, etree.XMLSyntaxError):
                    log.warning("Problem processing RNG file `{0}'".format(s))
                    continue
            if start is not None:
                schema = deepcopy(schema)
                target = rng_pivot(schema, start)
                rng = etree.RelaxNG(schema)
            else:
                target = rng_get_start(schema)[0]
            try:
                rng.assertValid(et)
            except etree.DocumentInvalid:
                log.warning("Invalid as per RNG file `{0}'".format(s))
                for entry in rng.error_log:
                    fatal.append((entry.line, entry.column, entry.message))
                master_snippet = etree.tostring(target, pretty_print=True)
            else:
                break
        else:
            log.warning("None of the validation attempts succeeded with"
                        " validator spec: {0}".format(', '.join(spec)))

        return fatal, master, master_snippet.strip()

    etree_validator = etree_rng_validator

    @SimpleFormat.producing(BYTESTRING, chained=True)
    def get_bytestring(self, *iodecl):
        # chained fallback
        return etree.tostring(self.ETREE(protect_safe=True),
                              encoding='UTF-8', pretty_print=True)

    @SimpleFormat.producing(ETREE, protect=True,
                            validator=etree_validator.__get__(1).__func__)
    def get_etree(self, *iodecl):
        return etree.fromstring(self.BYTESTRING(),
                                parser=etree_parser_safe).getroottree()
