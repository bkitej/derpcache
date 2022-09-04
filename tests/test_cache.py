from collections import OrderedDict
from derpcache import _cache
from faker import Faker
from typing import Tuple
from typing import Union
import datetime
import logging
import pytest


faker = Faker()


_RandomValueUnion = Union[str, int, float]
_RandomDepthDict = dict


@pytest.fixture(autouse=True)
def _autoclear_cache():
    yield
    _cache.clear_cache()


@pytest.fixture(autouse=True)
def _auto_caplog(caplog):
    with caplog.at_level(logging.INFO):
        yield


def _randomize_value() -> _RandomValueUnion:
    return faker.random_element((faker.lexify, faker.pyint, faker.pyfloat))()


def _randomize_args() -> Tuple[_RandomValueUnion, ...]:
    return tuple(_randomize_value() for _ in range(faker.pyint(2, 4)))


def _randomize_kwargs(depth: int = 1) -> _RandomDepthDict:
    randomize_key = lambda: faker.lexify() if depth == 1 else _randomize_value()  # noqa
    randomize_value = (
        lambda: _randomize_kwargs(depth=depth + 1)
        if faker.pybool() and not depth > 3
        else _randomize_value()
    )
    return {randomize_key(): randomize_value() for _ in range(faker.pyint(1, 3))}


def test__order_dict_tree():
    d = {
        'b': {
            'b': 1,
            'c': 2,
            'a': 3,
        },
        'a': {
            'b': 1,
            'a': 2,
            'c': {
                'b': 1,
                'a': 2,
            },
        },
    }
    expected_d = OrderedDict(
        [
            (
                'a',
                OrderedDict(
                    [
                        ('a', 2),
                        ('b', 1),
                        (
                            'c',
                            OrderedDict(
                                [
                                    ('a', 2),
                                    ('b', 1),
                                ]
                            ),
                        ),
                    ]
                ),
            ),
            (
                'b',
                OrderedDict(
                    [
                        ('a', 3),
                        ('b', 1),
                        ('c', 2),
                    ]
                ),
            ),
        ]
    )
    actual_d = _cache._order_dict_tree(d)
    assert actual_d == expected_d


class Test__make_hash:
    @pytest.mark.parametrize('args', [(), _randomize_args()])
    @pytest.mark.parametrize('kwargs', [{}, _randomize_kwargs()])
    def test__make_hash__different_orders(self, args, kwargs):
        def reverse_nested_dicts(d):
            new = {}
            for k, v in reversed(d.items()):
                if isinstance(v, dict):
                    v = reverse_nested_dicts(v)
                new[k] = v
            return new

        args1, kwargs1 = args, kwargs
        args2 = reversed(args)
        kwargs2 = reverse_nested_dicts(kwargs)

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
        assert entry['annotation'] is None
        assert entry['annotation_hashed'] is False
        assert entry['called_at'] == dt.isoformat()
        assert entry['function'] == _cache._describe_function(_func1)

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
        (index_entry, _) = sorted(index.values(), key=lambda x: x['called_at'])
        assert index_entry['annotation'] == annotation
        assert len(caplog.messages) == 2

    def test__cache__with_annotation__hashed_annotation(self, caplog):
        args, kwargs = _randomize_args(), _randomize_kwargs()
        annotation1 = faker.lexify()
        annotation2 = faker.lexify()

        result1_ann1 = _cache.cache(
            _func1,
            *args,
            **kwargs,
            _annotation=annotation1,
            _hash_annotation=True,
        )
        result2_ann1 = _cache.cache(
            _func1,
            *args,
            **kwargs,
            _annotation=annotation1,
            _hash_annotation=True,
        )
        result3_ann2 = _cache.cache(
            _func1,
            *args,
            **kwargs,
            _annotation=annotation2,
            _hash_annotation=True,
        )

        assert result1_ann1 == result2_ann1
        assert result3_ann2 != result1_ann1
        index = _cache.get_index()
        assert len(index) == 2
        entry_ann1, entry_ann2 = sorted(index.values(), key=lambda x: x['called_at'])
        assert entry_ann1['annotation'] == annotation1
        assert entry_ann1['annotation_hashed'] is True
        assert entry_ann2['annotation'] == annotation2
        assert entry_ann2['annotation_hashed'] is True
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

    @pytest.mark.parametrize(
        'scenario',
        [
            {
                'name': 'default cache kwargs',
                'cache_kwargs': {},
            },
            {
                'name': 'unhashed annotation',
                'cache_kwargs': {
                    '_annotation': faker.lexify(),
                },
            },
            {
                'name': 'hashed annotation',
                'cache_kwargs': {
                    '_annotation': faker.lexify(),
                    '_hash_annotation': True,
                },
            },
        ],
        ids=lambda x: x['name'],
    )
    def test__get_by_hash(self, caplog, freezer, scenario):
        dt = faker.date_time()
        freezer.move_to(dt)
        cache_kwargs = scenario['cache_kwargs']
        annotation1 = cache_kwargs.get('_annotation')
        hash_annotation = cache_kwargs.get('_hash_annotation', False)

        result1 = _cache.cache(
            _func1,
            *_randomize_args(),
            **_randomize_kwargs(),
            **cache_kwargs,
        )

        index1 = _cache.get_index()
        assert len(index1) == 1
        ((hash1, entry1),) = index1.items()
        assert entry1['annotation'] == annotation1
        assert entry1['annotation_hashed'] == hash_annotation
        assert entry1['called_at'] == dt.isoformat()
        assert entry1['function'] == _cache._describe_function(_func1)
        assert _cache.get_by_hash(hash1) == result1
        assert len(caplog.messages) == 1

        later = dt + datetime.timedelta.resolution
        freezer.move_to(later)
        result2 = _cache.cache(_func2, *_randomize_args(), **_randomize_kwargs())

        assert result2 != result1
        index2 = _cache.get_index()
        assert len(index2) == 2
        hash2, entry2 = next((k, v) for k, v in index2.items() if k != hash1)
        assert hash2 != hash1
        assert entry2['annotation'] is None
        assert entry2['annotation_hashed'] is False
        assert entry2['called_at'] == later.isoformat()
        assert entry2['function'] == _cache._describe_function(_func2)
        assert _cache.get_by_hash(hash2) == result2
        assert len(caplog.messages) == 2


def test__cache_wrapper():
    pass


@pytest.mark.xfail
class Test__expiration:
    @pytest.mark.parametrize(
        'expires_after_type', (
            int,
            datetime.timedelta
        )
    )
    def test__expires_after__clear_expired(self, caplog, freezer, expires_after_type):
        dt_called = faker.date_time()
        freezer.move_to(dt_called)
        args, kwargs = _randomize_args(), _randomize_kwargs()
        expires_after_int = faker.pyint(1, 3600)
        expires_after_delta = datetime.timedelta(seconds=expires_after_int)
        expires_after = (
            expires_after_int
            if expires_after_type == int
            else expires_after_delta
        )

        result1 = _cache.cache(_func1, *args, **kwargs, _expires_after=None)
        result2 = _cache.cache(_func1, *args, **kwargs, _expires_after=expires_after)

        index1 = _cache.get_index()
        assert len(index1) == 2
        assert len(caplog.messages) == 2

        index1 = _cache.get_index()
        (hash_valid, entry_valid), (hash_expired, entry_expired), = index1.items()
        assert entry_valid['called_at'] == dt_called.isoformat()
        assert entry_valid['expires_after'] is None
        assert entry_expired['called_at'] == dt_called.isoformat()
        assert entry_expired['expires_after'] == expires_after_int

        dt_expired = dt_called + expires_after_delta + datetime.timedelta.resolution
        freezer.move_to(dt_expired)

        index2 = _cache.get_index()
        assert len(index2) == 1
        assert len(caplog.messages) == 2
        assert hash_expired not in index2
        assert index2 == {hash_valid: entry_valid}


class Test__archival:
    pass
