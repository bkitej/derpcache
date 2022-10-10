from derpcache import _cache
from faker import Faker
from typing import Any
from typing import Dict
from typing import Tuple
from typing import Union
import datetime
import logging
import os
import pytest


faker = Faker()


_RandomValueUnion = Union[str, int, float]
_RandomDepthDict = Dict


@pytest.fixture(autouse=True)
def _auto_clear_cache():
    yield
    _cache.clear_cache()
    _cache.reset_cache_config()


@pytest.fixture(autouse=True)
def _auto_caplog(caplog):
    with caplog.at_level(logging.INFO):
        yield


def _randomize_value() -> _RandomValueUnion:
    return faker.random_element((faker.lexify, faker.pyint, faker.pyfloat))()


def _randomize_args() -> Tuple[_RandomValueUnion, ...]:
    return tuple(_randomize_value() for _ in range(faker.pyint(2, 4)))


def _randomize_kwargs(depth: int = 1) -> _RandomDepthDict:
    max_nested_dict_depth = 3
    if depth == 1:
        k = faker.lexify()
    else:
        k = _randomize_value()
    if faker.pybool() and not depth > max_nested_dict_depth:
        v = _randomize_kwargs(depth=depth + 1)
    else:
        # mypy has trouble with random recursive dict creation
        v = _randomize_value()  # type: ignore
    return {k: v for _ in range(faker.pyint(1, 3))}


def test__sort_nested_dicts():
    from collections import OrderedDict  # order matters for comparison

    d = OrderedDict(
        {
            'b': OrderedDict(
                {
                    'e': 1,
                    'f': [1, 2, [], {}],
                    'd': [
                        OrderedDict({3: 'i', 1: 'g', 2: 'h'}),
                        1,
                        OrderedDict({'k': 2, 'j': [1, 2]}),
                    ],
                }
            ),
            'a': OrderedDict(
                {
                    'm': [1, OrderedDict({'p': [1, 2], 'o': {}})],
                    'l': 1,
                    'n': OrderedDict({'r': 2, 'q': 1}),
                }
            ),
        }
    )
    expected_d = OrderedDict(
        {
            'a': OrderedDict(
                {
                    'l': 1,
                    'm': (1, OrderedDict({'o': {}, 'p': (1, 2)})),
                    'n': OrderedDict({'q': 1, 'r': 2}),
                }
            ),
            'b': OrderedDict(
                {
                    'd': (
                        OrderedDict({1: 'g', 2: 'h', 3: 'i'}),
                        1,
                        OrderedDict({'j': (1, 2), 'k': 2}),
                    ),
                    'e': 1,
                    'f': (1, 2, (), {}),
                }
            ),
        }
    )
    actual_d = _cache._sort_nested_dicts(d)
    assert actual_d == expected_d


class Test__make_hash:
    @pytest.mark.parametrize('args', [(), _randomize_args()])
    @pytest.mark.parametrize('kwargs', [{}, _randomize_kwargs()])
    def test__make_hash__different_orders(self, args, kwargs):
        def _reverse_nested_dicts(
            value: Union[dict, list, Any]
        ) -> Union[dict, list, Any]:
            if isinstance(value, dict):
                value = {
                    k: _reverse_nested_dicts(v) for k, v in reversed(value.items())
                }
            elif _cache._is_non_str_iterable(value):
                value = [_reverse_nested_dicts(x) for x in value]
            return value

        args1, kwargs1 = args, kwargs
        args2 = args
        kwargs2 = _reverse_nested_dicts(kwargs)

        hash1 = _cache._hash_args(*args1, **kwargs1)
        hash2 = _cache._hash_args(*args2, **kwargs2)

        assert hash1 == hash2

    @pytest.mark.parametrize(
        'differing_args',
        [
            ('args'),
            ('kwargs'),
            ('args', 'kwargs'),
        ],
    )
    def test__make_hash__different_args(self, differing_args):
        args1 = _randomize_args()
        args2 = _randomize_args() if 'args' in differing_args else (args1)
        kwargs1 = _randomize_kwargs()
        kwargs2 = _randomize_kwargs() if 'kwargs' in differing_args else kwargs1
        hash1 = _cache._hash_args(*args1, **kwargs1)
        hash2 = _cache._hash_args(*args2, **kwargs2)
        assert hash1 != hash2


def _func1(*args, **kwargs) -> _RandomValueUnion:
    logging.info(f'test func1 called with args: {args} and kwargs: {kwargs}')
    return _randomize_value()


def _func2(*args, **kwargs) -> _RandomValueUnion:
    logging.info(f'test func2 called with args: {args} and kwargs: {kwargs}')
    return _randomize_value()


class Test__cache:
    def test__cache__get_index(self, caplog, freezer):
        dt = faker.date_time()
        freezer.move_to(dt)
        _cache._init_cache()
        index1 = _cache.get_index()

        assert index1 == {}

        _cache.cache(_func1)
        index2 = _cache.get_index()

        assert len(index2) == 1
        ((_, entry),) = index2.items()
        expected_entry = {
            'callable': _cache._describe_callable(_func1),
            'called_at': dt.isoformat(),
        }
        assert entry == expected_entry

    def test__cache__hit(self, caplog):
        with caplog.at_level(logging.INFO):
            result1 = _func1()
            result2 = _func1()

        assert len(caplog.messages) == 2
        assert result1 != result2

        caplog.clear()

        result3 = _cache.cache(_func1)
        result4 = _cache.cache(_func1)

        assert len(caplog.messages) == 1
        assert result3 == result4

    def test__cache__with_args(self, caplog):
        args1, kwargs1 = _randomize_args(), _randomize_kwargs()
        args2, kwargs2 = _randomize_args(), _randomize_kwargs()

        args1_result1 = _cache.cache(_func1, *args1, **kwargs1)
        args1_result2 = _cache.cache(_func1, *args1, **kwargs1)
        args2_result1 = _cache.cache(_func1, *args2, **kwargs2)

        assert args1_result1 == args1_result2
        assert args1_result1 != args2_result1
        assert len(caplog.messages) == 2

    def test__cache__with_annotation__unhashed_annotation(self, caplog):
        args1, kwargs1 = _randomize_args(), _randomize_kwargs()
        args2, kwargs2 = _randomize_args(), _randomize_kwargs()
        annotation = faker.lexify()

        result1 = _cache.cache(_func1, *args1, **kwargs1, _annotation=annotation)
        result2 = _cache.cache(_func1, *args1, **kwargs1)
        result3 = _cache.cache(_func1, *args2, **kwargs2)

        assert result1 == result2
        assert result1 != result3
        index = _cache.get_index()
        assert len(index) == 2
        (index_entry, _) = index.values()
        assert index_entry['annotation'] == annotation
        assert len(caplog.messages) == 2

    def test__cache__clear_cache(self, caplog):
        result1 = _cache.cache(_func1)
        result2 = _cache.cache(_func1)

        assert result1 == result2
        assert len(caplog.messages) == 1

        _cache.clear_cache()
        caplog.clear()

        result3 = _cache.cache(_func1)
        result4 = _cache.cache(_func1)

        assert result3 == result4
        assert result1 != result3
        assert len(caplog.messages) == 1

    def test__cache__multiple_entries(self, caplog):
        func1_result1 = _cache.cache(_func1)
        func1_result2 = _cache.cache(_func1)
        func2_result1 = _cache.cache(_func2)
        func2_result2 = _cache.cache(_func2)

        assert func1_result1 == func1_result2
        assert func2_result1 == func2_result2
        assert func1_result1 != func2_result1
        index = _cache.get_index()
        assert len(index) == 2
        assert len(caplog.messages) == 2

    def test__get_by_hash(self, caplog, freezer):
        dt = faker.date_time()
        freezer.move_to(dt)
        annotation = faker.lexify()

        result1 = _cache.cache(
            _func1,
            *_randomize_args(),
            **_randomize_kwargs(),
            _annotation=annotation,
        )

        index1 = _cache.get_index()
        assert len(index1) == 1
        ((hash1, entry1),) = index1.items()
        expected_entry1 = {
            'callable': _cache._describe_callable(_func1),
            'called_at': dt.isoformat(),
            'annotation': annotation,
        }
        assert entry1 == expected_entry1
        assert _cache.get_by_hash(hash1) == result1
        assert len(caplog.messages) == 1

        later = dt + datetime.timedelta.resolution
        freezer.move_to(later)
        result2 = _cache.cache(_func2, *_randomize_args(), **_randomize_kwargs())

        assert result2 != result1
        index2 = _cache.get_index()
        assert len(index2) == 2
        (_, _), (hash2, entry2) = index2.items()
        assert hash2 != hash1
        expected_entry2 = {
            'callable': _cache._describe_callable(_func2),
            'called_at': later.isoformat(),
        }
        assert entry2 == expected_entry2
        assert _cache.get_by_hash(hash2) == result2
        assert len(caplog.messages) == 2

    @pytest.mark.parametrize(
        'cache_dir',
        [
            faker.lexify('????/'),
            faker.lexify('????/????/'),
        ],
    )
    def test__cache__set_cache_dir(self, caplog, cache_dir):
        config = _cache.update_cache_config(cache_dir=cache_dir)
        assert config == {'cache_dir': cache_dir}

        with caplog.at_level(logging.INFO):
            result1 = _cache.cache(_func1)
            result2 = _cache.cache(_func1)

        assert len(caplog.messages) == 1
        assert result1 == result2

        assert _cache._DEFAULT_CACHE_DIR.rstrip('/') not in os.listdir('.')
        cache_contents = os.listdir(cache_dir)
        assert len(cache_contents) == 2
        index = _cache.get_index()
        assert len(index) == 1

        _cache.clear_cache()
        caplog.clear()
        assert cache_dir.split('/')[0] not in os.listdir('.')

        with caplog.at_level(logging.INFO):
            result3 = _cache.cache(_func1)
            result4 = _cache.cache(_func1)

        assert len(caplog.messages) == 1
        assert result3 == result4
        assert result3 != result1

        assert _cache._DEFAULT_CACHE_DIR.rstrip('/') not in os.listdir('.')
        cache_contents = os.listdir(cache_dir)
        assert len(cache_contents) == 2
        index = _cache.get_index()
        assert len(index) == 1

        _cache.clear_cache()
        caplog.clear()
        assert cache_dir.split('/')[0] not in os.listdir('.')

        config = _cache.reset_cache_config()

        with caplog.at_level(logging.INFO):
            result5 = _cache.cache(_func1)
            result6 = _cache.cache(_func1)

        assert len(caplog.messages) == 1
        assert result5 == result6
        assert result5 != result3

        assert _cache._DEFAULT_CACHE_DIR.rstrip('/') in os.listdir('.')


@pytest.mark.parametrize('expires_after_type', (float, datetime.timedelta))
def test__expires_after__clear_expired(caplog, freezer, expires_after_type):
    dt_called = faker.date_time()
    freezer.move_to(dt_called)
    args, kwargs = _randomize_args(), _randomize_kwargs()
    expires_after_float = faker.pyfloat(min_value=1, max_value=3600, right_digits=6)
    expires_after_delta = datetime.timedelta(seconds=expires_after_float)
    if expires_after_type == float:
        expires_after = expires_after_float
    else:
        expires_after = expires_after_delta

    result = _cache.cache(_func1, *args, **kwargs, _expires_after=None)
    result_expires = _cache.cache(_func2, *args, **kwargs, _expires_after=expires_after)

    index1 = _cache.get_index(clear_expired=False)
    assert len(index1) == 2
    assert len(caplog.messages) == 2
    (
        (hash, entry),
        (hash_expires, entry_expires),
    ) = index1.items()
    expected_entry = {
        'callable': _cache._describe_callable(_func1),
        'called_at': dt_called.isoformat(),
    }
    assert entry == expected_entry
    assert result == _cache.get_by_hash(hash)
    expected_entry_expires = {
        'callable': _cache._describe_callable(_func2),
        'called_at': dt_called.isoformat(),
        'expires_after': expires_after_float,
    }
    assert entry_expires == expected_entry_expires
    assert result_expires == _cache.get_by_hash(hash_expires)

    dt_expired = dt_called + expires_after_delta + datetime.timedelta.resolution
    freezer.move_to(dt_expired)
    index2 = _cache.get_index(clear_expired=True)

    assert len(index2) == 1
    assert len(caplog.messages) == 2
    assert index2 == {hash: entry}
    assert hash_expires not in index2


def test__cache_wrapper():
    pass
