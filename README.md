# derpcache

`derpcache` is a rock-stupid pickle-based caching utility.  

It's designed for people who love restarting their Jupyter kernels.

```python
def appreciate_masterpiece(*args, **kwargs):
    time.sleep(273)
    return 'John Cage is the best composer of all time.'

cultured_opinion = derpcache.cache(appreciate_masterpiece, *args, **kwargs)
```

### Why should I use `derpcache`?

- You want a cache that will persist between kernels.
- You want a simple functional interface that can be nestled deep in your code—no magicks.
- You want a reasonable amount of visibility into what's in your cache. 
- You want the ability to set expiration and archival rules. (TBD)

```python
def make_http_request(arg1, arg2, arg3):
    url = '/'.join([BASE_URL, arg1, arg2, arg3])
    response = requests.get(url)
    return response.json()  # result must be serializable


responses = []
for arg1 in args1:
    for arg2 in args2:
        for arg3 in args3:
            args = (arg1, arg2, arg3)
            response = derpcache.cache(make_http_request, *args)
            responses.append(response)
            
            
df = pandas.DataFrame(responses)


#  what if I .fillna() with an entirely different emoji? ESC + 0 + 0
```

### "Centipedes? In my cache?"

Jupyter's interactive.  Sometimes it helps to do some manual inspection of whatever horrors you've just unknowingly scraped.

```python
centipede_families = {
    'Pselliodidae',
    'Scutigerinidae',
    'Lithobiidae'
}
centi_dfs = [
    derpcache.cache(
        pandas.read_html,
        f'https://en.wikipedia.org/wiki/{family}',
        _annotation=f'Centipede family: {family}'
    )
    for family
    in centipede_families
]

derpcache.get_index()
```

```json
{"e16279fc50cb3a841ed191a8465e05094a1a3975ff6322558c47b44723724d66": {"function": "read_html",
  "annotation": "Centipede family: Scutigerinidae",
  "annotation_hashed": False,
  "called_at": "2022-09-02T07:43:19.665615",
  "expires_after": None},
 "5175088049cd6e6efa743c281065ca7c96dd9d81036b5a817a6cc3d0fe66415f": {"function": "read_html",
  "annotation": "Centipede family: Pselliodidae",
  "annotation_hashed": False,
  "called_at": "2022-09-02T07:43:20.188296",
  "expires_after": None},
 "0a92439f9a9d515001e880c7fbbbf202f1400b9bb07c582c14b3c27e9dc425b3": {"function": "read_html",
  "annotation": "Centipede family: Lithobiidae",
  "annotation_hashed": False,
  "called_at": "2022-09-02T07:43:20.776659",
  "expires_after": None}}
```

"Lithobiidae" sounds nice...

```python
centipede_in_cache = derpcache.get_by_signature(
    '0a92439f9a9d515001e880c7fbbbf202f1400b9bb07c582c14b3c27e9dc425b3'
)
```

Gross!

```python
derpcache.clear_cache()
```

### Why "derp" cache?

It's built for quick and ~~dirty~~ derpy EDAs.

Plus, if I call it something dumb, you're less likely to use it in production.
