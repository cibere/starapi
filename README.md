# some web framework

yes

## TODO

- Cors
- Finish Removing starlette as a dep
  - Form Parsing
- Rewrite path params to work via callback args
- jinja2 templating
- builtin auth support
- Finish openapi integration
  - Security/auth
  - Webhooks
  - Servers
  - WebSocket Route Support
- status handlers
- response formatter ex:

```python
from starapi import Application, Response, Request, ResponseFormatter
import json

class Formatter(ResponseFormatter):
  def format_200(self, response: Response) -> Response:
    body = {
      "message": response.body.decode()
    }
    data = json.dumps(body)
    response.body = data.encode()
    return response

app = Application()

@app.route('/')
async def index(request: Request):
  return Response.ok("Hello")
```

Here the index page would actually return

```json
{
  "message": "Hello"
}
```
