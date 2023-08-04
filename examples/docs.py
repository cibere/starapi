from starapi import Application, OpenAPI

# Setup the docs using the default openapi generator
docs = OpenAPI(
    title="My API Docs", version="1.0.0"
)  # there are more kwargs that can be passed for futher customization

app = Application(docs=docs)

# Unless you have a route that overrides it, going to `/openapi.json` will return the docs
# in a openapi schema.

app.run()
