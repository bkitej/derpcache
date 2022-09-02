from collections import OrderedDict
from datetime import datetime
from derpcache import _cache
from faker import Faker
import logging
import pytest


faker = Faker()


@pytest.fixture(autouse=True)
def _autoclear_cache():
    yield
    _cache.clear_cache()


@pytest.fixture()
def now():
    return datetime.utcnow().isoformat()


def _randomize_value():
    return faker.random_element((faker.pyfloat, faker.pyint, faker.lexify))()


def _randomize_args():
    return tuple(_randomize_value() for _ in range(faker.pyint(2, 4)))


def _randomize_kwargs(depth=1):
    randomize_key = lambda: faker.lexify() if depth == 1 else _randomize_value()
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


class Test__make_signature:
    @pytest.mark.parametrize('args', [(), _randomize_args()])
    @pytest.mark.parametrize('kwargs', [{}, _randomize_kwargs()])
    def test__make_signature__different_orders(self, args, kwargs):
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

        signature1 = _cache._make_signature(*args1, **kwargs1)
        signature2 = _cache._make_signature(*args2, **kwargs2)

        assert signature1 == signature2

    @pytest.mark.parametrize(
        'differing_args',
        [
            ('args'),
            ('kwargs'),
            ('args', 'kwargs'),
        ],
    )
    def test__make_signature__different_args(self, differing_args):
        args1 = _randomize_args()
        args2 = _randomize_args() if 'args' in differing_args else args1
        kwargs1 = _randomize_kwargs()
        kwargs2 = _randomize_kwargs() if 'kwargs' in differing_args else kwargs1
        signature1 = _cache._make_signature(*args1, **kwargs1)
        signature2 = _cache._make_signature(*args2, **kwargs2)
        assert signature1 != signature2


def _func1(*args, **kwargs):
    logging.info(f'test func1 called with args: {args} and kwargs: {kwargs}')
    return _randomize_value()


def _func2(*args, **kwargs):
    logging.info(f'test func2 called with args: {args} and kwargs: {kwargs}')
    return _randomize_value()


class Test__cache:
    def test__cache__get_index(self, caplog, freezer, now):
        freezer.move_to(now)
        _cache._init_cache()
        index1 = _cache.get_index()

        assert index1 == {}

        _cache.cache(_func1)
        index2 = _cache.get_index()

        assert len(index2) == 1
        ((_, entry),) = index2.items()
        assert entry['annotation'] == None
        assert entry['annotation_hashed'] == False
        assert entry['called_at'] == now
        assert entry['function'] == _cache._describe_function(_func1)

    def test__cache__hit(self, caplog):
        with caplog.at_level(logging.INFO):
            result1 = _func1()
            result2 = _func1()
            assert len(caplog.messages) == 2
            assert result1 != result2

        caplog.clear()

        with caplog.at_level(logging.INFO):
            result3 = _cache.cache(_func1)
            result4 = _cache.cache(_func1)
            assert len(caplog.messages) == 1
            assert result3 == result4

    def test__cache__with_args(self, caplog):
        args1, kwargs1 = _randomize_args(), _randomize_kwargs()
        args2, kwargs2 = _randomize_args(), _randomize_kwargs()

        with caplog.at_level(logging.INFO):
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

        with caplog.at_level(logging.INFO):
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

        with caplog.at_level(logging.INFO):
            result1_ann1 = _cache.cache(
                _func1, *args, **kwargs, _annotation=annotation1, _hash_annotation=True
            )
            result2_ann1 = _cache.cache(
                _func1, *args, **kwargs, _annotation=annotation1, _hash_annotation=True
            )
            result3_ann2 = _cache.cache(
                _func1, *args, **kwargs, _annotation=annotation2, _hash_annotation=True
            )

        assert result1_ann1 == result2_ann1
        assert result3_ann2 != result1_ann1
        index = _cache.get_index()
        assert len(index) == 2
        entry_ann1, entry_ann2 = sorted(index.values(), key=lambda x: x['called_at'])
        assert entry_ann1['annotation'] == annotation1
        assert entry_ann1['annotation_hashed'] == True
        assert entry_ann2['annotation'] == annotation2
        assert entry_ann2['annotation_hashed'] == True
        assert len(caplog.messages) == 2

    def test__cache__clear_cache(self, caplog):
        with caplog.at_level(logging.INFO):
            result1 = _cache.cache(_func1)
            result2 = _cache.cache(_func1)

        assert result1 == result2
        assert len(caplog.messages) == 1

        _cache.clear_cache()
        caplog.clear()

        with caplog.at_level(logging.INFO):
            result3 = _cache.cache(_func1)
            result4 = _cache.cache(_func1)

        assert result3 == result4
        assert result1 != result3
        assert len(caplog.messages) == 1

    def test__cache__multiple_entries(self, caplog):
        with caplog.at_level(logging.INFO):
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
    def test__get_by_signature(self, caplog, freezer, scenario, now):
        cache_kwargs = scenario['cache_kwargs']
        annotation1 = cache_kwargs.get('_annotation')
        hash_annotation = cache_kwargs.get('_hash_annotation', False)
        freezer.move_to(now)

        with caplog.at_level(logging.INFO):
            result1 = _cache.cache(
                _func1, *_randomize_args(), **_randomize_kwargs(), **cache_kwargs
            )

        index1 = _cache.get_index()
        assert len(index1) == 1
        ((signature1, entry1),) = index1.items()
        assert entry1['annotation'] == annotation1
        assert entry1['annotation_hashed'] == hash_annotation
        assert entry1['called_at'] == now
        assert entry1['function'] == _cache._describe_function(_func1)
        assert _cache.get_by_signature(signature1) == result1
        assert len(caplog.messages) == 1

        with caplog.at_level(logging.INFO):
            result2 = _cache.cache(_func2, *_randomize_args(), **_randomize_kwargs())

        assert result2 != result1
        index2 = _cache.get_index()
        assert len(index2) == 2
        signature2, entry2 = next((k, v) for k, v in index2.items() if k != signature1)
        assert signature2 != signature1
        assert entry2['annotation'] is None
        assert entry2['annotation_hashed'] == False
        assert entry2['called_at'] == now
        assert entry2['function'] == _cache._describe_function(_func2)
        assert _cache.get_by_signature(signature2) == result2
        assert len(caplog.messages) == 2
