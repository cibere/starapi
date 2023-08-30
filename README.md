# some web framework

yes

## TODO

- Cors
- Finish Removing starlette as a dep
  - Form Parsing
- jinja2 templating
- builtin auth support
- Finish openapi integration
  - Security/auth
  - Webhooks
  - Servers
  - WebSocket Route Support
- status handlers
- add global response schemas, and use the route's callback's return annotation for the ok response. Keep the responses kwarg in `Route` for per-route changes.
- websocket path parameter support
- finish middleware support
- WebsocketEndpoint class that can be subclassed. Would be a combination of `WebSocketRoute` and `WebSocket`. Useful for more stateful actions.
