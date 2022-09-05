from collections import OrderedDict
from typing import Any
from typing import Callable
from typing import Dict
from typing import Union
import datetime
import functools
import hashlib
import json
import logging
import os
import pickle
import shutil


_AnnotationUnion = Union[None, str, dict]
_EntryDict = Dict[str, Union[str, int, bool]]
_IndexDict = Dict[str, _EntryDict]


_CACHE_DIR = '.derpcache'
_CACHE_INDEX_FILE = 'index.json'


logger = logging.getLogger(__name__)


def _get_root_dir() -> str:
    return os.environ.get('DERPCACHE_ROOT_DIR', '.')


def _get_index_path() -> str:
    return os.path.join(_get_root_dir(), _CACHE_DIR, _CACHE_INDEX_FILE)


def _get_cache_path(s: str = '') -> str:
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
    for k, v in sorted(d.items(), key=str):  # TODO: sort _after_
        if isinstance(v, dict):
            v = _order_dict_tree(v)
        new[k] = v
    return new


def _describe_callable(f: Callable) -> str:
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
    string = args_str + kwargs_str
    return hashlib.sha256(string.encode()).hexdigest()[:8]


def _read_index() -> _IndexDict:
    with open(_get_index_path(), 'r') as f:
        index = json.load(f)
    return index


def _write_index(index: _IndexDict) -> None:
    with open(_get_index_path(), 'w') as f:
        json.dump(index, f)


def _add_index_entry(index: _IndexDict, hash: str, entry: _EntryDict) -> None:
    index[hash] = entry
    _write_index(index)


def get_by_hash(hash: str) -> Any:
    with open(_get_cache_path(hash), 'rb') as f:
        value = pickle.load(f)
    return value


def _write_object_by_hash(hash: str, value: Any) -> None:
    with open(_get_cache_path(hash), 'wb') as f:
        pickle.dump(value, f)


def _remove_objects(to_remove: list[str]) -> None:
    for hash in to_remove:
        os.remove(_get_cache_path(hash))


def _remove_entries(index, to_remove: list[str]) -> None:
    index = {k: v for k, v in index.items() if k not in to_remove}
    _write_index(index)
    return index


def _is_expired(entry: _EntryDict) -> bool:
    expires_after = entry.get('expires_after')
    if expires_after:
        called_at = datetime.datetime.fromisoformat(entry['called_at'])
        expires_after = datetime.timedelta(seconds=expires_after)
        now = datetime.datetime.utcnow()
        expired = called_at + expires_after >= now
    else:
        expired = False
    return expired


def _remove_expired_items(index: _IndexDict) -> _IndexDict:
    to_remove = []
    for hash, entry in index.items():
        if _is_expired(entry):
            to_remove.append(hash)
    index = _remove_entries(index, to_remove)
    _remove_objects(to_remove)
    return index


def _sort_index(index: _IndexDict) -> _IndexDict:
    index = {k: v for k, v in sorted(index.items(), key=lambda x: x[1]['called_at'])}
    return index


def get_index(clear_expired: bool = False) -> _IndexDict:
    index = _read_index()
    if clear_expired:
        index = _remove_expired_items(index)
    index = _sort_index(index)
    return index


def _expires_after_to_int(expires_after: Union[int, datetime.timedelta]) -> int:
    if isinstance(expires_after, datetime.timedelta):
        expires_after = expires_after.total_seconds()
    return expires_after


def _format_entry(
    f: Callable,
    called_at: str,
    expires_after: Union[int, datetime.timedelta],
    annotation: str,
    hash_annotation: bool,
) -> _EntryDict:
    entry = {
        'callable': _describe_callable(f),
        'called_at': called_at,
    }
    if expires_after:
        entry['expires_after'] = _expires_after_to_int(expires_after)
    if annotation:
        entry['annotation'] = annotation
        entry['hash_annotation'] = hash_annotation
    return entry


def cache(
    f: Callable,
    *args,
    _expires_after: Union[int, datetime.timedelta] = None,
    _annotation: str = None,
    _hash_annotation: bool = False,
    **kwargs,
) -> Any:
    _init_cache()
    hash = _hash_args(
        # lazy, but keeps :meth:`_hash_args` dumb
        _describe_callable(f),
        _expires_after,
        _annotation if _hash_annotation else '',
        *args,
        **kwargs,
    )
    index = get_index(clear_expired=True)
    if hash in index:
        value = get_by_hash(hash)
        logger.debug('cache hit')
    else:
        logger.debug('caching...')
        called_at = datetime.datetime.utcnow().isoformat()
        value = f(*args, **kwargs)
        _write_object_by_hash(hash, value)
        _add_index_entry(
            index,
            hash,
            _format_entry(f, called_at, _expires_after, _annotation, _hash_annotation),
        )
        logger.debug('caching successful.')
    return value


def cache_wrapper(
    _expires_after: Union[None, str, datetime.timedelta] = None,
    _annotation: _AnnotationUnion = None,
    _hash_annotation: bool = False,
) -> Callable:
    """TODO: support wrapping bound methods."""

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapped(*args, **kwargs) -> Any:
            return cache(
                f,
                *args,
                **kwargs,
                _expires_after=_expires_after,
                _annotation=_annotation,
                _hash_annotation=_hash_annotation,
            )

        return wrapped

    return decorator
