# stdlib
import logging
import sys
import yaml
from typing import Dict, AsyncIterator
from dataclasses import dataclass
from contextlib import asynccontextmanager

# 3p
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP

# project
from mcp_openapi.parser import Spec
from mcp_openapi.tools import (
    tools_from_spec,
    Tool,
    create_tool_function_exec,
)
from mcp_openapi.proxy import MCPProxy


log = logging.getLogger(__name__)


class ServerManager:
    def __init__(self, config_path: str = "servers.yaml"):
        self.config_path = config_path
        self.servers: Dict[str, FastMCP] = {}
        self.tools: Dict[str, list[Tool]] = {}
        self.routes = []
        self.setup_endpoints()
        self.load_config()

    def setup_endpoints(self):
        """Set up Starlette endpoints"""

        async def get_all_tools(request):
            tools_by_namespace = {}
            for namespace, tools in self.tools.items():
                tools_by_namespace[namespace] = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": [
                            param.model_dump(exclude={"request_body_field"})
                            for param in tool.all_params()
                        ],
                    }
                    for tool in tools
                ]
            return JSONResponse(content=tools_by_namespace)

        async def get_namespace_tools(request):
            namespace = request.path_params["namespace"]
            if namespace not in self.tools:
                return JSONResponse(
                    content={"error": f"Namespace '{namespace}' not found"},
                    status_code=404,
                )
            return JSONResponse(
                content=[
                    {"name": tool.name, "description": tool.description}
                    for tool in self.tools[namespace]
                ]
            )

        self.routes.extend(
            [
                Route("/tools", get_all_tools),
                Route("/tools/{namespace}", get_namespace_tools),
            ]
        )

    def load_config(self):
        """Load and parse the servers configuration file."""
        try:
            with open(self.config_path, "r") as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            log.error(f"Failed to load config file {self.config_path}: {e}")
            sys.exit(1)

    async def start_servers(self):
        """Start all configured servers."""
        for server_config in self.config["servers"]:
            await self.start_server(server_config)

    async def start_server(self, server_config: dict):
        """Start a single server based on its configuration."""
        namespace = server_config["namespace"]
        name = server_config["name"]
        url = server_config["url"]
        base_url = server_config["base_url"]
        paths = server_config["paths"]
        forward_headers = server_config.get("forward_headers", [])
        forward_query_params = server_config.get("forward_query_params", {})

        log.info(f"Starting server for {name} ({namespace})")

        try:
            spec = (
                Spec.from_file(url[7:], paths)
                if url.startswith("file://")
                else Spec.from_url(url, paths)
            )

            @dataclass
            class AppContext:
                base_url: str
                proxy: MCPProxy

            @asynccontextmanager
            async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
                """Manage application lifecycle with type-safe context"""
                try:
                    # Create recorder with namespace-specific cassette directory
                    proxy = MCPProxy(
                        forward_headers=forward_headers,
                        forward_query_params=forward_query_params,
                    )
                    yield AppContext(base_url=base_url, proxy=proxy)
                finally:
                    pass

            mcp = FastMCP(
                name,
                lifespan=app_lifespan,
                sse_path=f"/{namespace}/sse",
                message_path=f"/{namespace}/messages/",
            )

            tools = tools_from_spec(spec, forward_query_params.keys())
            self.tools[namespace] = tools

            for tool in tools:
                fn = create_tool_function_exec(tool)
                mcp.tool(
                    name=tool.name,
                    description=tool.description,
                )(fn)

                log.info(f"{name} - tool: {tool.name} - {tool.description}")

            self.servers[namespace] = mcp

            mcp_app = mcp.sse_app()
            self.routes.extend(mcp_app.routes)

            log.info(f"Started server for {name} at /{namespace}/sse")

        except Exception as e:
            log.exception(f"Failed to start server for {name}: {e}")

    async def stop_servers(self):
        """Stop all running servers."""
        for namespace, server in self.servers.items():
            log.info(f"Stopping server for {namespace}")

        self.servers.clear()
        self.routes = []

    def get_app(self) -> Starlette:
        """Get the Starlette application with all routes."""
        return Starlette(routes=self.routes)
