# -*- coding: UTF-8 -*-
# Copyright 2017 Red Hat, Inc.
# Part of clufter project
# Licensed under GPLv2+ (a copy included | http://gnu.org/licenses/gpl-2.0.txt)
"""Easy (at least for usage) plugin framework"""
__author__ = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

from contextlib import contextmanager
from fnmatch import translate
from imp import PY_SOURCE, find_module, get_suffixes, load_module
from logging import getLogger
from os import pathsep, walk
from os.path import abspath, dirname, isabs, isdir, join, splitext
from re import compile as re_compile
from sys import modules

try:
    from .defaults import EXTPLUGINS_SHARED
except ImportError:
    EXTPLUGINS_SHARED = ''
from .utils import args2tuple, \
                   args2sgpl, \
                   classproperty, \
                   filterdict_keep, \
                   filterdict_pop, \
                   filterdict_remove, \
                   hybridproperty, \
                   tuplist
from .utils_2to3 import StandardError, filter_u, foreach_u  #, iter_values
from .utils_func import apply_intercalate
from .utils_prog import ProtectedDict, cli_decor, getenv_namespaced

log = getLogger(__name__)
module_ext = dict((t, s) for s, m, t in get_suffixes())[PY_SOURCE]

here = dirname(abspath(__file__))

EXTPLUGINS = tuple(e if isabs(e) else join(here, e) for e in
    map(str.strip, getenv_namespaced(
        'EXTPLUGINS', pathsep.join(('ext-plugins', EXTPLUGINS_SHARED))
    ).rstrip(pathsep).split(pathsep))
)


class MetaPlugin(object):
    """For use in the internal meta-hierarchy as "do not register me" mark"""


class PluginRegistry(type):
    """Core of simple plugin framework

    This ``superclass'' serves two roles:

    (1) metaclass for plugins (and its class hierarchy)
        - only a tiny wrapper on top of `type`

    (2) base class for particular registries

    Both roles are combined due to a very tight connection.

    Inspired by http://eli.thegreenplace.net/2012/08/07/ (Fundamental...).
    """
    _registries = set()  # dynamic tracking of specific registries

    #
    # these are relevant for use case (1)
    #

    # non-API

    def __new__(registry, name, bases, attrs):
        assert '_probes' not in attrs, "sabotage of the meta level detected"
        attrs['_probes'] = 0
        if '__metaclass__' not in attrs and MetaPlugin not in bases:
            # alleged end-use plugin
            ret = registry.probe(name, bases, attrs)
        else:
            if registry not in PluginRegistry._registries:
                log.debug("Registering `{0}' as registry"
                            .format(registry.registry))
                # specific registry not yet tracked
                # (e.g., specific plugin was imported natively)
                registry.setup()
                PluginRegistry._registries.add(registry)
                # rely on sys being always present (tautology) -> failing test
                if (registry.namespace or 'sys') not in modules:
                    # XXX hack to prevent RuntimeWarning due to missing parent
                    #     module (e.g., some tests in the test suite)
                    __import__(registry.namespace)

            ret = super(PluginRegistry, registry).__new__(registry, name,
                                                          bases, attrs)

        ret._probes += 1
        return ret

    #
    # these are relevant for both (1) + (2)
    #

    @classmethod
    def probe(registry, name, bases, attrs=None):
        """Meta-magic to register plugin"""
        assert '-' not in name, "name cannot contain a dash"
        dname = cli_decor(name)
        attrs = attrs or {}
        try:
            ret = registry._plugins[dname]
            log.info("Probe `{0}' plugin under `{1}' registry: already tracked"
                     .format(dname, registry.registry))
        except KeyError:
            log.debug("Probe `{0}' plugin under `{1}' registry: yet untracked"
                      .format(dname, registry.registry))
            namespaced = registry.namespaced(dname.split('-', 1)[0])
            if namespaced in modules and hasattr(modules[namespaced], name):
                # XXX can be used even for "preload"
                ret = getattr(modules[namespaced], name)
            else:  # bases arg of type has to be tuplist, final plugin otherwise
                ret = bases if not tuplist(bases) else \
                      super(PluginRegistry, registry).__new__(registry, dname,
                                                              bases, attrs)
            # XXX init plugin here?
            registry._plugins[dname] = ret

        if registry._path_context is not None:
            registry._path_mapping[registry._path_context].add(dname)
        if tuplist(bases) and ret.__metaclass__.__module__ == ret.__module__:
            ret.__metaclass__._native_plugins[cli_decor(ret.name)] = ret

        return ret

    @hybridproperty
    def name(this):
        """Nicer access to __name__"""
        return this.__name__

    @classproperty
    def registry(registry):
        """Registry identifier"""
        return registry.__name__

    @classproperty
    def namespace(registry):
        """Absolute namespace possessed by the particular plugin registry

        For a plugin, this denotes to which registry/namespace it belongs.
        """
        try:
            return registry._namespace
        except AttributeError:
            registry._namespace = '.'.join((__package__, registry.__name__))
            return registry._namespace

    @classmethod
    def namespaced(registry, symbol, *symbols):
        return '.'.join(args2tuple(registry.namespace, symbol, *symbols))

    @classproperty
    def plugins(registry):
        return registry._plugins_ro

    @classproperty
    def native_plugins(registry):
        return registry._native_plugins_ro

    #
    # these are relevant for use case (2)
    #

    # non-API

    @classmethod
    @contextmanager
    def _path(registry, path):
        """Temporary path context setup enabling safe sideways use"""
        assert registry._path_context is None
        registry._path_context = path
        yield path, registry._path_mapping.setdefault(path, set())
        assert registry._path_context is not None
        registry._path_context = None

    @classmethod
    def _context(registry, paths):
        """Iterate through the paths yielding context along

        Context is a pair `(path, list_of_per_path_tracked_plugins_so_far)`.
        """
        paths = args2sgpl(paths)
        if paths and paths[0] is None:  # injection of implicit path prevented
            paths = paths[1:]
        else:  # injection happens
            paths = args2tuple(dirname(abspath(__file__)), *paths)
        paths = (p for p in (join(p, registry.__name__) for p in paths)
                 if isdir(p))

        for path in paths:
            with registry._path(path) as context:
                yield context

    # API

    @classmethod
    def setup(registry, reset=False):
        """Implicit setup upon first registry involvement or external reset"""
        ps = {}
        attrs = (('_path_context', None), ('_path_mapping', {}),
                 ('_plugins', ps), ('_plugins_ro', ProtectedDict(ps)))
        if reset:
            foreach_u(lambda a, d: setattr(registry, a, d), attrs)
        else:
            foreach_u(lambda a, d: setattr(registry, a,
                                           getattr(registry, a, d)), attrs)
        registry._native_plugins = np = getattr(registry, '_native_plugins', {})
        registry._native_plugins_ro = ProtectedDict(np)
        if reset:
            PluginRegistry._registries.discard(registry)

    @classmethod
    def discover(registry, paths=(), fname_start='', from_scratch=False):
        """Find relevant plugins available at the specified path(s)

        Keyword arguments:
            fname_start     glob/fnmatch pattern (not RE) used to filter files,
                            can also be a tuplist of strings like this

        Returns `{plugin_name: plugin_cls}` mapping of plugins found.
        """
        ret = {}
        fname_start_use = apply_intercalate(args2sgpl(fname_start or '[!_.]'))
        fp = re_compile('|'.join(
            translate(fs + '*')
            for fs in (pfx.split('-', 1)[0] for pfx in fname_start_use)
        ))
        if from_scratch:
            registry.setup(True)
        for path, path_plugins in registry._context(paths):
            # skip if path already discovered (considered final)
            if not path_plugins:
                # visit *.py files within (and under) the path and probe them
                for root, dirs, files in walk(path):
                    if root != path:
                        break  # ATM we only support flat dir (nested ~ private)
                    #try:
                    #    dirs.remove('__pycache__')  # PY3 (if we ever nest)
                    #except ValueError:
                    #    pass
                    for name, ext in filter_u(
                        lambda name, ext:
                            fp.match(name) and
                            (ext == module_ext or isdir(join(root, name))),
                        (splitext(x) for x in files + dirs)
                    ):
                        try:
                            mfile, mpath, mdesc = find_module(name, [root])
                        except ImportError:
                            log.debug("Omitting `{0}' at `{1}'"
                                      .format(name, root))
                        else:
                            mname = registry.namespaced(name)
                            try:
                                load_module(mname, mfile, mpath, mdesc)
                            except StandardError as e:
                                # non-fatal, just log it and keep going
                                log.error("Module load error: {0}: {1}"
                                          .format(mfile or mpath, str(e)))
                            finally:
                                if mfile:
                                    mfile.close()
                path_plugins = registry._path_mapping[path]
                if fname_start:  # not picking everything -> restart next time
                    registry._path_mapping.pop(path)

            # filled as a side-effect of meta-magic, see `__new__`
            ret.update((n, registry._plugins[n]) for n in path_plugins)

        return ret


class PluginManager(object):
    """Common (abstract) base for *Manager objects"""

    _default_registry = PluginRegistry

    @classmethod
    def lookup(cls, plugins, registry=None, **kwargs):
        ret, to_discover = {}, set()
        registry = cls._default_registry if registry is None else registry
        for plugin in args2sgpl(plugins):
            # XXX we could introspect sys.modules here as well
            try:
                ret[plugin] = registry.plugins[plugin]
            except KeyError:
                to_discover.add(plugin)
        kwargs = filterdict_keep(kwargs, 'paths', 'from_scratch')
        ret.update(registry.discover(fname_start=tuple(to_discover), **kwargs))

        to_discover.difference_update(ret)
        native_plugins = registry.native_plugins
        ret.update(filterdict_remove(to_discover,
                                     _fn_=lambda x: native_plugins[x],
                                     *native_plugins.keys()))
        to_discover = apply_intercalate(tuple(to_discover))
        if to_discover:
            log.debug("Couldn't look up everything: {0}".format(', '.join(
                                                                to_discover)))
        return ret  # if tuplist(plugins) else ret[plugins]

    @classmethod
    def init_lookup(cls, plugin=(), *plugins, **kwargs):
        plugins = args2sgpl(plugin, *plugins)
        ext_plugins = []
        if kwargs.get('ext_plugins', True):
            for e in EXTPLUGINS:
                for root, dirs, _ in walk(e, followlinks=True):
                    ext_plugins.extend(join(root, d) for d in dirs)
                    break
        ext_plugins.extend(
            abspath(d) for d in
            apply_intercalate([d.split(':') for d in
                kwargs.get('ext_plugins_user') or ()
            ])
        )
        if ext_plugins:
            if not isinstance(kwargs.setdefault('paths', []), list):
                kwargs['paths'] = paths = list(kwargs['paths'])
            else:
                paths = kwargs['paths']
            paths.extend(ext_plugins)
        kws_lu = filterdict_pop(kwargs, 'paths')
        return cls(plugins=cls.lookup(plugins, **kws_lu), paths=None, **kwargs)

    def __init__(self, *args, **kwargs):
        registry = kwargs.pop('registry', None) or self._default_registry
        assert registry is not PluginRegistry, \
               "PluginManager subclass should refer to its custom registry"
        self._registry = registry
        plugins = registry.discover(**filterdict_pop(kwargs, 'paths'))
        plugins.update(kwargs.pop('plugins', None)
                       or dict(registry.native_plugins, **registry.plugins))
        self._plugins = ProtectedDict(
            self._init_plugins(plugins, *args, **kwargs),
        )

    @classmethod
    def _init_plugins(cls, plugins, *args, **kwargs):
        log.info("Plugins under `{0}' left intact: {1}".format(cls.__name__,
                                                               plugins))
        return plugins

    @property
    def registry(self):
        return self._registry

    @property
    def plugins(self):
        return self._plugins

    #def __iter__(self):
    #    return iter_values(self._plugins)
