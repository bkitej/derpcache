from ._cache import cache
from ._cache import cache_wrapper
from ._cache import clear_cache
from ._cache import get_by_hash
from ._cache import get_index as _get_index


def get_index(clear_expired=True):
    return _get_index(clear_expired=clear_expired)


"""
derpcache

'A simple pickle-based caching utility.'
"""


__version__ = '1.0.0'
__author__ = 'Ben Johnson'
__credits__ = 'Silver Zinc Beetle'
__all__ = [
    'cache',
    'cache_wrapper',
    'clear_cache',
    'get_index',
    'get_by_hash',
]
