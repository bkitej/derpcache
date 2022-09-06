# derpcache

`derpcache` is a simple pickle-based caching utility.

It's made for people who love nuking their Jupyter kernels.

```python
from derpcache import cache
import requests

countries = [
    'Afghanistan',
    'Albania',
    # ...
    'Zambia',
    'Zimbabwe'
]

pages = []
for country in countries:
    url = f'https://en.wikipedia.org/wiki/{country}'
    annotation = f'Wikipedia page for {country}'
    page = cache(requests.get, url, _annotation=country)
    pages.append(page)
```

### Why should I use `derpcache`?

- You want a cache that will persist between kernel restarts.
- You want a simple functional interface—no IPython magics needed.
- You want a reasonable amount of visibility into what's in your cache.
- You want the ability to set expiration rules.

### Expiration

```doctest
>>> import time
>>> def long_running_func(*args, **kwargs):
...     time.sleep(1200)
...     print('running...')
...     return 'done'
...
>>> expires_after = 300
>>> cache(long_running_func, _expires_after=expires_after)
running...
done
>>> cache(long_running_func)
done
>>> time.sleep(expires_after)
>>> cache(long_running_func)
running...
done
```

### Viewing cached entries

```python
from derpcache import get_index
from pprint import pprint

pprint(get_index(), sort_dicts=False)  # or, pandas.DataFrame.from_records
```

```json
{"5e39b292": {"callable": "__main__.long_running_func",
              "called_at": "2022-09-06T05:19:14.614796"},
 "b37ab1af": {"callable": "requests.api.get",
              "called_at": "2022-09-06T05:21:35.157183",
              "annotation": "Afghanistan"},
 "f0103017": {"callable": "requests.api.get",
              "called_at": "2022-09-06T05:21:35.814452",
              "annotation": "Albania"},
 "8861f226": {"callable": "requests.api.get",
              "called_at": "2022-09-06T05:21:36.084777",
              "annotation": "Zambia"},
 "19754ec0": {"callable": "requests.api.get",
              "called_at": "2022-09-06T05:21:36.341655",
              "annotation": "Zimbabwe"}}
```
