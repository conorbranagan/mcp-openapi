# MCP-OpenAPI Server

MCP-OpenAPI Server is a bridge that enables AI agents to discover and interact with your existing API endpoints through the [Model Context Protocol (MCP)](https://www.anthropic.com/news/model-context-protocol). By exposing OpenAPI-defined services as MCP tools with proper typing, authentication, and selective endpoint exposure, it simplifies integration between cloud-based AI agents and external services without requiring custom tool development.

While many MCP implementations rely on stdiofor local integrations and command-line tools, this project focuses on SSE transport to enable a multi-tenant server-side architecture.

## Who is This For?

- **API Providers**: Easily expose your OpenAPI services to AI agents without rebuilding APIs or creating custom MCP tools. Perfect for SaaS companies wanting to enable AI integration with their platform.

- **AI Agent Developers**: Connect your server-side agents to multiple external services with properly typed arguments. Ideal for building assistants that can seamlessly interact with systems like Zendesk, Stripe, and other APIs.

- **Enterprise Integration Teams**: Create standardized access patterns for AI agents to interact with your internal systems while maintaining proper authentication and permissions.

- **Prototype Developers**: Quickly test AI-API interactions before investing in a dedicated MCP implementation, helping identify improvements to your API structure and documentation.

## Key Features

- **SSE Transport**: This server leverages the SSE transport for MCP (rather than Stdio) so it works well for multiple agent clients.
  - Each OpenAPI server is available at a separate route `<host>/<namespace>/sse` (e.g., `https://my-mcp-server/stripe/sse`).
- **Selective Route Exposure**: Expose only the routes/tools you want for your agents to be aware of, using a regex on the route.
- **Authentication Forwarding**: Share the same MCP tools across multiple users by forwarding the appropriate authorization headers and/or query parameters.
- **Type Safety**: Tools are generated with typed arguments based on the OpenAPI schema.
  - JSON bodies and parameters are converted appropriately with supported for nested objects and more complex schemas.

## Running

### Start the Server

Define your servers in `servers.yaml` following the structure in [servers.yaml.example](servers.yaml.example) and:

```yaml
servers:
  - namespace: stripe
    # Forward the Authorization header to the Stripe API
    forward_headers:
      - Authorization
    name: Stripe API
    url: https://raw.githubusercontent.com/stripe/openapi/refs/heads/master/openapi/spec3.yaml
    base_url: https://api.stripe.com
    # Select which API paths to expose over MCP. Each matching path will become a tool with arguments
    # from the query parameters or the JSON body.
    # For example, we're only exposing the endpoints to GET/POST a customer.
    paths:
      - /v1/customers$

  - namespace: zendesk
    # Forward the Authorization header to the Zendesk API
    forward_headers:
      - Authorization
    # This is the name as it appears to the LLM
    name: Zendesk API
    url: https://developer.zendesk.com/zendesk/oas.yaml
    # Change the subdomain to match your Zendesk instance
    base_url: https://{subdomain}.zendesk.com
    # Select which API paths to expose over MCP
    paths:
      - /api/v2/tickets$

  - namespace: weather
    name: Open Weather API
    url: https://gist.githubusercontent.com/mor10/6fb15f2270f8ac1d8b99aa66f9b63410/raw/0e2c4ed43eb4c126ec2284bc7c069de488b53d99/openweatherAPI.json
    base_url: https://api.openweathermap.org
    paths:
      - /data/2.5/weather
    # Forward the x-open-weather-app-id header to the apiid query parameter.
    forward_query_params:
      - x-open-weather-app-id: appid
    timeout: 0.5
```

_⚠️ Note: For large (multi-megabyte) OpenAPI specs you might find the initial cold start slow as it processes the whole file. After the first time we will cache the parsed schemas on disk, so subsequent server restarts will be fast. To mitigate the slow cold start, you can try the the `slim-openapi` tool described below⚠️_

Then you can run your server:

**Locally (requires [uv](https://github.com/astral-sh/uv))**

```bash
uv run main.py
```

**Via Docker**

```bash
docker build -t mcp-openapi .
docker run -p 8000:8000 -v $(pwd)/servers.yaml:/app/servers.yaml mcp-openapi
```

The `-v` flag mounts your local `servers.yaml` file into the container. You can also use environment variables to configure the service:

- `PORT`: The port to run the server on (default: 8000)
- `CONFIG`: Path to the servers configuration file (default: servers.yaml)

Example with environment variables:

```bash
docker run -p 8000:8000 \
  -v $(pwd)/servers.yaml:/app/servers.yaml \
  -e PORT=8000 \
  -e CONFIG=servers.yaml \
  mcp-openapi
```

### Access from MCP clients

The project includes two example clients that demonstrate different ways to interact with the MCP-OpenAPI server. Both examples use the same server configuration and demonstrate header forwarding for authentication. The low-level client is particularly useful for custom integrations or when you need more direct control over the MCP client.

- **[Low-Level Client](client-examples/low_level_client.py)**: This example demonstrates direct usage of the MCP client with SSE transport using the low level client.
- **[LangChain Integration](client-examples/langchain_client.py)**: This example shows how to integrate the MCP-OpenAPI server with LangChain (using the [langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters)), allowing AI agents to use these APIs through LangChain's tool system.

## Limitations

- **Handling of complex schemas**: This do our best to parse more complex schemas with type nesting but there are some limits in the current implementation. If you run against issues here let me know the spec and I can update accordingly.

- **Context Window Usage**: Endpoints with many parameters may consume significant space in the AI model's context window. Be selective about which endpoints you expose to balance functionality and efficiency.

## Tool Inspection

You can use the tool provided at [scripts/cli.py](scripts/cli.py) to inspect the tool definitions generated from a schema.

For example:

```
# View the tree of schemas parsed from a spec file
uv run scripts/cli.py tools --url https://developer.zendesk.com/zendesk/oas.yaml --routes "/api/v2/tickets$"

# View the tool functions with typing based on a spec file.
uv run scripts/cli.py tools --url https://developer.zendesk.com/zendesk/oas.yaml --routes "/api/v2/tickets$"
```

The server also exposes a couple HTTP endpoints for inspection.

- `/tools/` and `/tools/{namespace}` will show the tools and parameters they have exposed.

```bash
curl -s localhost:8000/tools | jq '.'
{
  "stripe": [
    {
      "name": "get_customers",
      "description": "List all customers",
      "parameters": [
        {
          "name": "limit",
          "type": "int",
          "default": null,
          "description": "A limit on the number of objects to be returned. Limit can range between 1 and 100, and the default is 10."
        },
        {
          "name": "email",
          "type": "str",
          "default": null,
          "description": "A case-sensitive filter on the list based on the customer's `email` field. The value must be a string."
        },
        {
          "name": "created",
          "type": "str",
          "default": null,
          "description": "Only return customers that were created during the given date interval."
        },
        ...
      ]
    },
    {
      "name": "post_customers",
      "description": "Create a customer",
      "parameters": [
        {
          "name": "address",
          "type": "Union[Any, str]",
          "default": "None",
          "description": "The customer's address., one of: (Object with properties: city, country, line1, line2, postal_code, state) OR (string)"
        },
        {
          "name": "balance",
          "type": "int",
          "default": "None",
          "description": "An integer amount in cents (or local equivalent) that represents the customer's current balance, which affect the customer's future invoices. A negative amount represents a credit that decreases the amount due on an invoice; a positive amount increases the amount due on an invoice."
        },
        {
          "name": "description",
          "type": "str",
          "default": "None",
          "description": "An arbitrary string that you can attach to a customer object. It is displayed alongside the customer in the dashboard."
        },
        {
          "name": "email",
          "type": "str",
          "default": "None",
          "description": "Customer's email address. It's displayed alongside the customer in your dashboard and can be useful for searching and tracking. This may be up to *512 characters*."
        },
        ...
      ]
    }
  ],
  "zendesk": [
    {
      "name": "list_tickets",
      "description": "List Tickets",
      "parameters": [
        {
          "name": "external_id",
          "type": "str",
          "default": null,
          "description": "Lists tickets by external id. External ids don't have to be unique for each ticket. As a result, the request may return multiple tickets with the same external id."
        }
      ]
    },
    {
      "name": "create_ticket",
      "description": "Create Ticket",
      "parameters": [
        {
          "name": "ticket_additional_collaborators",
          "type": "str",
          "default": "None",
          "description": "An array of numeric IDs, emails, or objects containing name and email properties. See [Setting Collaborators](/api-reference/ticketing/tickets/tickets/#setting-collaborators). An email notification is sent to them when the ticket is updated"
        },
        {
          "name": "ticket_assignee_email",
          "type": "str",
          "default": "None",
          "description": "The email address of the agent to assign the ticket to"
        },
        {
          "name": "ticket_assignee_id",
          "type": "int",
          "default": "None",
          "description": "The agent currently assigned to the ticket"
        },
        ...
      ]
    }
  ],
  "weather": [
    {
      "name": "get_weather_data",
      "description": "Retrieve current weather, hourly forecast, and daily forecast based on latitude and longitude.",
      "parameters": [
        {
          "name": "lon",
          "type": "float",
          "default": null,
          "description": "Longitude of the location."
        },
        {
          "name": "lat",
          "type": "float",
          "default": null,
          "description": "Latitude of the location."
        },
        {
          "name": "appid",
          "type": "str",
          "default": null,
          "description": "API key for authentication."
        }
      ]
    }
  ],
  "httpbin": [
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
    ...
  ]
}
```

Finally, you can use the [MCP inspector](https://github.com/modelcontextprotocol/inspector) to seeing what's available.

![mcp-inspector](images/mcp-inspector-httpbin.png)

## Slimming down large spec files with `slim-openapi`

For large (multi-megabyte) OpenAPI specs you might find the initial cold start slow as it processes the whole file.

Some SaaS tools (e.g. Stripe, Zendesk) have multi-megabyte spec YAML files which are processed somewhat inefficiently today. Using the `slim-openapi` tool you can shorten these to just the spec needed for your routes. All references will be resolved appropriately so it can still parse.

```bash
uv run scripts/slim-openapi \
    -u https://raw.githubusercontent.com/stripe/openapi/refs/heads/master/openapi/spec3.yaml \
    --routes "/v1/customers$" \
    -o stripe-slim.yaml
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

This project uses [aiopenapi3](https://github.com/commonism/aiopenapi3) for OpenAPI specification parsing and validation. Many thanks to the maintainers and contributors of that project for their excellent work.
bot credential check
