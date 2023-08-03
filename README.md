# some web framework

yes

## TODO

- Cors
- Finish Removing starlette as a dep
  - Form Parsing
- Custom Convertors
- Use `BaseRoute._match` to reduce duplicated code in `Route._match` and `WebSocketRoute._match`
- BaseRoute.clean_path
- Rewrite path params to work via callback args
- add the repr dunder to the objects (along with other dunder methods like `__eq__`)
- make msgspec a optional dependency (maybe via moving openapi stuff to `openapi.py`)
- jinja2 templating