# MCP OpenAPI Server

Run an MCP server which creates tools for a subset of API endpoints based on OpenAPI routes.

Supports:

- JSON and YAML local or remote OpenAPI schemas.
- Exposing a subset of routes based on regular expressions.
- Providing strictly typed arguments to tools based on the schemas.

## Quick Start

Install the necessary dependencies using [uv](https://github.com/astral-sh/uv).

```bash
uv sync
```

Define your servers following the structure of `services.yaml.example`:

```
servers:
  - namespace: httpbin
    name: httpbin
    url: file://apis/httpbin.yaml
    base_url: https://httpbin.org/
    paths:
      - /get$
      - /ip$
      - /headers$
      # Will match /status/{code} endpoint
      - /status


  - namespace: zendesk
    name: Zendesk API
    url: file://apis/zendesk-oas.yaml
    base_url: https://api.zendesk.com
    paths:
      - /api/v2/tickets$
      - /api/v2/users$
```

- You can point to either a remote URL or local file (using `file://`).
- In `paths` you define Regular Expressions which will match the paths you want to expose.

Then you can run your server to expose it:

```bash
uv run main.py
```

## Inspecting

Alongside the MCP servers, the server exposes a couple HTTP endpoints for inspection.

- `/tools/` and `/tools/{namespace}` will show the tools that are exposed.

```bash
{
  "httpbin": [
    {
      "name": "get_request",
      "description": "Returns GET data",
      "parameters": [
        {
          "name": "freeform",
          "type": "str",
          "default": "None",
          "description": "Any query parameters you want to test with"
        }
      ]
    },
    {
      "name": "status_code",
      "description": "Returns specified status code",
      "parameters": [
        {
          "name": "code",
          "type": "int",
          "default": null,
          "description": "HTTP status code to return"
        }
      ]
    },
    {
      "name": "get_ip",
      "description": "Returns origin IP",
      "parameters": []
    },
    {
      "name": "get_headers",
      "description": "Returns headers",
      "parameters": []
    },
    {
      "name": "get_user_agent",
      "description": "Returns user-agent",
      "parameters": []
    }
  ]
}
```

The MCP inspector is also useful for seeing what's available.

![mcp-inspector](images/mcp-inspector-httpbin.png)
