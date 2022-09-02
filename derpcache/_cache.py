from collections import OrderedDict
from datetime import datetime
from typing import Any
from typing import Callable
from typing import Union
import functools
import hashlib
import json
import logging
import os
import pickle
import shutil


_AnnotationUnion = Union[None, str, dict]


_CACHE_DIR = '.derpcache'
_CACHE_INDEX_FILE = 'index.json'


logger = logging.getLogger(__name__)


def _get_root_dir() -> str:
    return os.environ.get('DERPCACHE_ROOT_DIR', '.')


def _get_index_path() -> str:
    return os.path.join(_get_root_dir(), _CACHE_DIR, _CACHE_INDEX_FILE)


def _get_cache_path(s='') -> str:
    return os.path.join(_get_root_dir(), _CACHE_DIR, s)


def _init_cache() -> None:
    if _CACHE_DIR not in os.listdir(_get_root_dir()):
        os.mkdir(_CACHE_DIR)
        with open(_get_index_path(), 'w') as f:
            json.dump({}, f)


def clear_cache() -> None:
    try:
        shutil.rmtree(_get_cache_path())
    except FileNotFoundError:
        pass


def _order_dict_tree(d: dict) -> OrderedDict:
    """Load any (nested) :obj:`dict`s into key-alphabetized
    :obj:`collections.OrderedDict`s, so kwargs passed in any order are hashed the same.
    """

    new = OrderedDict()
    for k, v in sorted(d.items(), key=str):
        if isinstance(v, dict):
            v = _order_dict_tree(v)
        new[k] = v
    return new


def _describe_function(f: Callable) -> str:
    """Some callables are missing a :attr:`__qualname__`, so it helps to at least have
    some info about what they were."""

    mod = f.__module__
    name = getattr(f, '__qualname__', str(type(f)))
    return f'{mod}.{name}'


def _to_string(arg: Any) -> str:
    if isinstance(arg, dict):
        arg = _order_dict_tree(arg)
    return str(arg)


def _hash_args(*args, **kwargs) -> str:
    args_str = str(sorted(_to_string(x) for x in args))
    kwargs_str = _to_string(kwargs)
    string_hash = args_str + kwargs_str
    return hashlib.sha256(string_hash.encode()).hexdigest()[:8]


def get_index() -> dict:
    with open(_get_index_path(), 'r') as f:
        index = json.load(f)
    return index


def _update_index(d: dict) -> None:
    index = get_index()
    index.update(d)
    with open(_get_index_path(), 'w') as f:
        json.dump(index, f)


def get_by_hash(hash: str) -> Any:
    with open(_get_cache_path(hash), 'rb') as f:
        value = pickle.load(f)
    return value


def _write_by_hash(hash: str, value: Any) -> None:
    with open(_get_cache_path(hash), 'wb') as f:
        pickle.dump(value, f)


def cache(
    f: Callable,
    *args,
    _annotation: Union[None, str, dict] = None,
    _hash_annotation: bool = False,
    **kwargs,
) -> Any:
    _init_cache()
    hash = _hash_args(
        # lazy, but keeps :meth:`_hash_args` dumb
        _describe_function(f),
        _annotation if _hash_annotation else None,
        *args,
        **kwargs,
    )
    index = get_index()
    if hash in index:
        value = get_by_hash(hash)
        logger.debug('cache hit')
    else:
        logger.debug('caching...')
        called_at = datetime.utcnow().isoformat()
        value = f(*args, **kwargs)
        _write_by_hash(hash, value)
        _update_index(
            {
                hash: {
                    'function': _describe_function(f),
                    'annotation': _annotation,
                    'annotation_hashed': _hash_annotation,
                    'called_at': called_at,
                    'expires_after': None,  # TODO
                }
            }
        )
        logger.debug('caching successful.')
    return value


def cache_wrapper(
    _annotation: _AnnotationUnion = None,
    _hash_annotation: bool = False,
) -> Callable:
    """TODO: support wrapping bound methods."""

    def decorator(f) -> Callable:
        @functools.wraps(f)
        def wrapped(*args, **kwargs) -> Any:
            return cache(
                f,
                *args,
                **kwargs,
                _annotation=_annotation,
                _hash_annotation=_hash_annotation,
            )

        return wrapped

    return decorator
