from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Union
import datetime
import functools
import hashlib
import json
import logging
import os
import pickle
import shutil


# TODO: use stricter structure
_EntryDict = Dict
_IndexDict = Dict[str, _EntryDict]


_CACHE_INDEX_FILE = 'index.json'
_DEFAULT_CACHE_DIR = '.derpcache/'
_CACHE_CONFIG_DEFAULTS = {
    'cache_dir': _DEFAULT_CACHE_DIR,
}


logger = logging.getLogger(__name__)


__cache_config = _CACHE_CONFIG_DEFAULTS.copy()


def update_cache_config(**config) -> dict:
    """Update cache config settings.

    Args:

        config (:obj:`dict`): Dictionary of configuration settings.

            Currently supported keys:

                "cache_dir": (path to) the desired cache directory.

    Returns:

        dict: The current configuration settings.
    """

    __cache_config.update(config)
    return __cache_config


def reset_cache_config() -> dict:
    """Resets config settings to package defaults.

    Returns:

        dict: The default configuration settings.
    """

    for k in list(__cache_config.keys()):
        __cache_config.pop(k)
    return update_cache_config(**_CACHE_CONFIG_DEFAULTS)


def _get_cache_dir() -> str:
    return __cache_config['cache_dir']


def _get_cache_path(filename: str = '') -> str:
    return os.path.join(_get_cache_dir(), filename)


def _get_index_path() -> str:
    return _get_cache_path(_CACHE_INDEX_FILE)


def _is_non_str_iterable(x: Any) -> bool:
    return hasattr(x, '__iter__') and not isinstance(x, str)


def _sort_nested_dicts(value: Union[dict, list, Any]) -> Union[dict, list, Any]:
    """Sort nested dicts by keys so casting it will produce a deterministic string.

    Warning: Thar be edge cases."""

    if isinstance(value, dict):
        value = {k: _sort_nested_dicts(v) for k, v in sorted(value.items(), key=str)}
    elif _is_non_str_iterable(value):
        value = tuple(_sort_nested_dicts(x) for x in value)
    return value


def _to_string(arg: Any) -> str:
    arg = _sort_nested_dicts(arg)
    return str(arg)


def _hash_args(*args, **kwargs) -> str:
    args_string = _to_string(args) + _to_string(kwargs)
    return hashlib.sha256(args_string.encode()).hexdigest()[:8]


def _read_index() -> _IndexDict:
    with open(_get_index_path(), 'r') as f:
        index = json.load(f)
    return index


def _write_index(index: _IndexDict) -> None:
    with open(_get_index_path(), 'w') as f:
        json.dump(index, f)


def _write_entry_to_index(
    index: _IndexDict,
    hash: str,
    entry: _EntryDict,
) -> _IndexDict:
    index[hash] = entry
    _write_index(index)
    return index


def get_by_hash(hash: str) -> Any:
    """Retrieve the function call's return value by its hash.

    Args:

        hash (:obj:`str`): The hash of the function call.

    Returns:

        Any: The return value of the function call.
    """

    with open(_get_cache_path(hash), 'rb') as f:
        value = pickle.load(f)
    return value


def _write_object_by_hash(hash: str, value: Any) -> None:
    with open(_get_cache_path(hash), 'wb') as f:
        pickle.dump(value, f)


def _remove_objects(to_remove: List[str]) -> None:
    for hash in to_remove:
        os.remove(_get_cache_path(hash))


def _remove_entries(index: _IndexDict, to_remove: List[str]) -> _IndexDict:
    index = {k: v for k, v in index.items() if k not in to_remove}
    _write_index(index)
    return index


def _is_expired(entry: _EntryDict) -> bool:
    expires_after = entry.get('expires_after')
    if expires_after:
        called_at = datetime.datetime.fromisoformat(entry['called_at'])
        expires_after = datetime.timedelta(seconds=expires_after)
        now = datetime.datetime.utcnow()
        expired = called_at + expires_after < now
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


def get_index(clear_expired: bool = True) -> _IndexDict:
    """Retrieve `index.json` metadata dict about cache contents.

    Note: When using `expires_after` expiration rules, expired cache contents will be
        permanently removed upon calling this function (or checking the cache again),
        unless `clear_expired` is set to `False`.

    Args:
        clear_expired (bool): Clear expired cache contents upon call.

    Returns:
        dict: The current state of the cache.
    """

    index = _read_index()
    if clear_expired:
        index = _remove_expired_items(index)
    index = _sort_index(index)
    return index


def _init_cache() -> None:
    try:
        os.makedirs(_get_cache_dir())
        _write_index({})
    except FileExistsError:
        pass


def clear_cache() -> None:
    """Removes cache directory and all files within it.  If configured cache directory
    is a path, remove only the bottom-most empty directories within that path.
    """

    def _remove_bottom_dir(path):
        dirs = path.rstrip('/').split('/')
        new_path = '/'.join(dirs[:-1])
        return new_path

    cache_path = _get_cache_path()
    shutil.rmtree(cache_path, ignore_errors=True)
    cache_path = _remove_bottom_dir(cache_path)
    while cache_path:
        try:
            os.rmdir(cache_path)
            cache_path = _remove_bottom_dir(cache_path)
        except OSError:
            break


def _describe_callable(f: Callable) -> str:
    """Note: Some callables are missing a :attr:`__qualname__`, so including `type()`
    provides at least some information."""

    mod = f.__module__
    name = getattr(f, '__qualname__', str(type(f)))
    return f'{mod}.{name}'


def _expires_after_to_float(expires_after: Union[float, datetime.timedelta]) -> float:
    if isinstance(expires_after, datetime.timedelta):
        expires_after = expires_after.total_seconds()
    return expires_after


def _format_entry(
    f: Callable,
    called_at: str,
    expires_after: Optional[Union[float, datetime.timedelta]],
    annotation: Optional[str],
) -> _EntryDict:
    entry = {
        'callable': _describe_callable(f),
        'called_at': called_at,
    }
    if expires_after:
        # mypy thinks `expires_after` is a string here
        entry['expires_after'] = _expires_after_to_float(expires_after)  # type: ignore
    if annotation:
        entry['annotation'] = annotation
    return entry


def cache(
    f: Callable,
    *args,
    _expires_after: Optional[Union[float, datetime.timedelta]] = None,
    _annotation: Optional[str] = None,
    **kwargs,
) -> Any:
    """
    Calls a function and caches the results.

    Args:

        f (Callable):

            Function whose results are to be cached.

        *args (optional):

            The function call's arguments.

        **kwargs (optional):

            The function call's keyword arguments.

        _expires_after (float, :obj:`datetime.timedelta`, optional):

            Time elapsed after which the cache entry will be cleared.  Numeric values
                are interpreted as seconds.

        _annotation (:obj:`str`, optional):

            Arbitrary string that can be passed to help identify or describe the call.

    Returns:

        value (any):

            The return value of the original function call.
    """

    _init_cache()
    hash = _hash_args(
        _describe_callable(f),  # lazy, but keeps :meth:`_hash_args` dumb
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
        _write_entry_to_index(
            index,
            hash,
            entry=_format_entry(
                f,
                called_at,
                _expires_after,
                _annotation,
            ),
        )
        logger.debug('caching successful.')
    return value


def cache_wrapper(
    _expires_after: Optional[Union[float, datetime.timedelta]] = None,
    _annotation: Optional[str] = None,
) -> Callable:

    # TODO: support wrapping bound methods.

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapped(*args, **kwargs) -> Any:
            return cache(
                f,
                *args,
                **kwargs,
                _expires_after=_expires_after,
                _annotation=_annotation,
            )

        return wrapped

    return decorator
