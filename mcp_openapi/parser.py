# stdlib
from typing import Dict, List, Optional, Any
import re
import logging
import pickle
import hashlib
from pathlib import Path
import pathlib
from pydantic import BaseModel, Field

# 3p
import aiopenapi3
from aiopenapi3.plugin import Document


log = logging.getLogger(__name__)

# Create cache directory in the user's home directory
CACHE_DIR = Path.home() / ".mcp-openapi" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class Schema(BaseModel):
    name: str
    type: str | list[str]  # Can be a single type or list of types for anyOf
    items: Optional["Schema"] = None
    properties: Optional[List["Schema"]] = None
    description: Optional[str] = None
    default: Optional[Any] = None
    any_of: Optional[List["Schema"]] = None  # For anyOf schemas
    all_of: Optional[List["Schema"]] = None  # For allOf schemas


class Parameter(BaseModel):
    name: str
    in_: str = Field(alias="in")
    required: bool = False
    schema_: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    deprecated: Optional[bool] = None
    allowEmptyValue: Optional[bool] = None
    style: Optional[str] = None
    explode: Optional[bool] = None
    allowReserved: Optional[bool] = None
    type: Optional[str] = None
    enum: Optional[List[Any]] = None
    default: Optional[Any] = None
    items: Optional["Schema"] = None


class Response(BaseModel):
    description: str
    content: Optional[Dict[str, Any]] = None
    schema_: Optional[Schema] = None
    format: str = "text/plain"


class RequestBody(BaseModel):
    description: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    required: bool = False
    schema_: Optional[Schema] = None
    content_type: Optional[str] = None
    encoding: Optional[Dict[str, Dict[str, Any]]] = None


class Operation(BaseModel):
    id: str
    summary: Optional[str] = None
    description: Optional[str] = None
    parameters: List[Parameter] = []
    request_body_: RequestBody | None = None
    responses: Dict[str, Response]


class Path(BaseModel):
    path: str
    get: Optional[Operation] = None
    post: Optional[Operation] = None
    put: Optional[Operation] = None
    delete: Optional[Operation] = None
    patch: Optional[Operation] = None


class FilterPaths(Document):
    def __init__(self, path_patterns: list[str]):
        super().__init__()
        self._path_patterns = [re.compile(pattern) for pattern in path_patterns]

    def parsed(self, ctx: "Document.Context") -> "Document.Context":
        ctx.document["paths"] = {
            k: v
            for k, v in ctx.document["paths"].items()
            if any(pattern.match(k) for pattern in self._path_patterns)
        }
        return ctx


class RemovePaths(Document):
    def parsed(self, ctx: "Document.Context") -> "Document.Context":
        """
        emtpy the paths - not needed
        """
        keys_allowed = [
            "openapi",
            "info",
            "paths",
            "components",
        ]
        for key in list(ctx.document.keys()):
            if key not in keys_allowed:
                del ctx.document[key]
        return ctx


class Spec:
    @classmethod
    def from_file(
        cls,
        file_path: str,
        path_patterns: list[str],
        base_path=pathlib.Path("").absolute(),
        use_cache=True,
    ) -> "Spec":
        cache_key = hashlib.md5(
            f"{file_path}:{','.join(sorted(path_patterns))}".encode()
        ).hexdigest()
        cache_file = CACHE_DIR / f"{cache_key}.pickle"

        # Create cache key from file path and patterns
        if use_cache and cache_file.exists():
            log.info(f"Loading cached OpenAPI spec from {cache_file}")
            with open(cache_file, "rb") as f:
                return pickle.load(f)

        log.info(f"Loading OpenAPI spec from {file_path}")

        api = aiopenapi3.OpenAPI.load_file(
            file_path,
            file_path,
            loader=aiopenapi3.FileSystemLoader(base_path),
            plugins=[RemovePaths(), FilterPaths(path_patterns)],
        )
        spec = cls._from_api(api, path_patterns)

        # Cache the result
        with open(cache_file, "wb") as f:
            pickle.dump(spec, f)

        return spec

    @classmethod
    def from_url(cls, url: str, path_patterns: list[str], use_cache=True) -> "Spec":
        cache_key = hashlib.md5(
            f"{url}:{','.join(sorted(path_patterns))}".encode()
        ).hexdigest()
        cache_file = CACHE_DIR / f"{cache_key}.pickle"

        if use_cache and cache_file.exists():
            log.info(f"Loading cached OpenAPI spec from {cache_file}")
            with open(cache_file, "rb") as f:
                return pickle.load(f)

        log.info(f"Cold loading OpenAPI spec from {url}")
        api = aiopenapi3.OpenAPI.load_sync(
            url,
            loader=aiopenapi3.FileSystemLoader(pathlib.Path("")),
            plugins=[RemovePaths(), FilterPaths(path_patterns)],
        )
        spec = cls._from_api(api, path_patterns)

        # Cache the result
        with open(cache_file, "wb") as f:
            pickle.dump(spec, f)

        return spec

    @classmethod
    def _from_api(cls, api: aiopenapi3.OpenAPI, path_patterns: list[str]) -> "Spec":
        paths = []

        compiled_patterns = [re.compile(pattern) for pattern in path_patterns]
        for path, path_item in api.paths.paths.items():
            # Check if path matches any of the patterns
            if not any(pattern.match(path) for pattern in compiled_patterns):
                continue

            processed_path = Path(path=path)
            if path_item.get:
                processed_path.get = cls._process_operation(path, path_item.get, api)
            if path_item.post:
                processed_path.post = cls._process_operation(path, path_item.post, api)
            if path_item.put:
                processed_path.put = cls._process_operation(path, path_item.put, api)
            if path_item.delete:
                processed_path.delete = cls._process_operation(
                    path, path_item.delete, api
                )
            if path_item.patch:
                processed_path.patch = cls._process_operation(
                    path, path_item.patch, api
                )
            paths.append(processed_path)

        return cls(paths=paths)

    def __init__(self, paths: List[Path]) -> None:
        self.paths = paths

    @classmethod
    def handle_any_of(
        cls, schemas, api, depth=0, max_depth=10, visited=None
    ) -> List[Schema]:
        """Helper function to process anyOf schemas"""
        any_of_schemas = []
        for sub_schema in schemas:
            result = cls._process_schema(sub_schema, api, depth + 1, max_depth, visited)
            if result:
                any_of_schemas.append(
                    Schema(
                        name=result.name,
                        type=sub_schema.type or "object",
                        properties=result.properties,
                        description=sub_schema.description,
                    )
                )
        return any_of_schemas

    @classmethod
    def handle_all_of(
        cls, schemas, api, depth=0, max_depth=10, visited=None
    ) -> List[Schema]:
        """Helper function to process allOf schemas"""
        all_schemas = []
        for sub_schema in schemas:
            result = cls._process_schema(sub_schema, api, depth + 1, max_depth, visited)
            if result:
                all_schemas.append(
                    Schema(
                        name=result.name,
                        type="object",
                        properties=result.properties,
                        description=sub_schema.description,
                    )
                )
        return all_schemas

    @classmethod
    def _process_array_items(
        cls, item_schema, api, depth, max_depth, visited
    ) -> Schema:
        """Helper method to process array items"""
        if hasattr(item_schema, "ref") and item_schema.ref:
            item_name = item_schema.ref.split("/")[-1]
            resolved_item_schema = api.components.schemas[item_name]
            if resolved_item_schema.type == "object":
                item_properties = []
                for (
                    item_prop_name,
                    item_prop_schema,
                ) in resolved_item_schema.properties.items():
                    item_prop_type = item_prop_schema.type or "object"
                    item_prop = Schema(
                        name=item_prop_name,
                        type=item_prop_type,
                        description=item_prop_schema.description,
                    )
                    if item_prop_type == "object":
                        nested_schema = cls._process_schema(
                            item_prop_schema, api, depth + 1, max_depth, visited
                        )
                        if nested_schema:
                            item_prop.properties = nested_schema.properties
                    item_properties.append(item_prop)
                return Schema(
                    name=item_name,
                    type="object",
                    properties=item_properties,
                    description=item_schema.description,
                )

        return Schema(
            name="item",
            type=item_schema.type or "object",
            description=item_schema.description,
        )

    @classmethod
    def _process_schema(
        cls, schema, api, depth=0, max_depth=10, visited=None
    ) -> Optional[Schema]:
        """Process schema and return a Schema model."""
        # Initialize visited set if None
        if visited is None:
            visited = set()

        # Check depth limit
        if depth >= max_depth:
            log.debug(f"Max depth {max_depth} reached, stopping recursion")
            return None

        # Handle circular references
        if hasattr(schema, "ref") and schema.ref:
            schema_ref = schema.ref
            if schema_ref in visited:
                log.debug(f"Circular reference detected for schema {schema_ref}")
                return None
            visited.add(schema_ref)

        # Resolve schema
        if hasattr(schema, "ref") and schema.ref:
            schema_name = schema.ref.split("/")[-1]
            resolved_schema = api.components.schemas[schema_name]
        else:
            schema_name = "inline"
            resolved_schema = schema

        properties = []

        # Handle composite schemas (allOf/anyOf)
        if resolved_schema.allOf:
            all_schemas = cls.handle_all_of(
                resolved_schema.allOf, api, depth, max_depth, visited
            )
            return Schema(
                name=schema_name,
                type="object",
                properties=[
                    Schema(
                        name="all_of",
                        type="object",
                        properties=[prop for p in all_schemas for prop in p.properties],
                        description=resolved_schema.description,
                        all_of=all_schemas,
                    )
                ],
            )

        elif resolved_schema.anyOf:
            any_of_schemas = cls.handle_any_of(
                resolved_schema.anyOf, api, depth, max_depth, visited
            )
            return Schema(
                name=schema_name,
                type="object",
                properties=[
                    Schema(
                        name="any_of",
                        type=[p.type for p in any_of_schemas],
                        description=resolved_schema.description,
                        any_of=any_of_schemas if any_of_schemas else None,
                    )
                ],
            )

        # Handle array type
        elif resolved_schema.type == "array":
            if not resolved_schema.items:
                return Schema(name=schema_name, type="array", properties=[], default=[])

            processed_items = cls._process_schema(
                resolved_schema.items, api, depth + 1, max_depth, visited
            )
            if not processed_items:
                return Schema(name=schema_name, type="array", properties=[], default=[])

            properties.append(
                Schema(
                    name="inline",
                    type="array",
                    description=resolved_schema.description,
                    default=[],
                    items=Schema(
                        name="item",
                        type=resolved_schema.items.type or "object",
                        properties=processed_items.properties,
                        description=resolved_schema.items.description,
                    ),
                )
            )

        # Handle regular object properties
        elif resolved_schema.properties:
            for prop_name, prop_schema in resolved_schema.properties.items():
                prop_type = prop_schema.type or "object"
                prop = Schema(
                    name=prop_name, type=prop_type, description=prop_schema.description
                )
                if prop_type == "array" and prop_schema.items:
                    prop.items = cls._process_array_items(
                        prop_schema.items, api, depth, max_depth, visited
                    )
                    prop.default = []
                elif prop_type == "object":
                    if (
                        prop_schema.anyOf
                        or prop_schema.allOf
                        or (hasattr(prop_schema, "ref") and prop_schema.ref)
                    ):
                        # For allOf/anyOf/ref we want to inline the properties
                        nested_schema = cls._process_schema(
                            prop_schema, api, depth, max_depth, visited
                        )
                        if nested_schema and nested_schema.properties:
                            prop = Schema(
                                name=prop_name,
                                type=nested_schema.properties[0].type,
                                description=prop_schema.description,
                                properties=[nested_schema.properties[0]],
                                any_of=nested_schema.properties[0].any_of,
                                all_of=nested_schema.properties[0].all_of,
                            )
                    elif prop_schema.properties:
                        prop.properties = cls._process_schema(
                            prop_schema, api, depth, max_depth, visited
                        ).properties

                properties.append(prop)

        return Schema(
            name=schema_name,
            type="object",
            properties=properties,
        )

    @classmethod
    def _process_operation(cls, path_name, operation, api) -> Operation:
        """Process operation and return an Operation model."""
        processed_params = []
        for param in operation.parameters:
            param_dict = {
                "name": param.name,
                "in": param.in_,
                "required": bool(getattr(param, "required", False)),
                "description": getattr(param, "description", None),
                "deprecated": getattr(param, "deprecated", None),
                "allowEmptyValue": getattr(param, "allowEmptyValue", None),
                "style": getattr(param, "style", None),
                "explode": getattr(param, "explode", None),
                "allowReserved": getattr(param, "allowReserved", None),
                "type": param.schema_.type,
            }

            # Add enum and default if they exist in the schema
            if param.schema_.enum:
                param_dict["enum"] = param.schema_.enum
            if param.schema_.default is not None:
                param_dict["default"] = param.schema_.default

            # Add array sub-type information if needed.
            # FIXME: May need support for nested types.
            if hasattr(param.schema_, "items") and param.schema_.items:
                param_dict["items"] = Schema(
                    name="item",
                    type=param.schema_.items.type or "object",
                )
                param_dict["default"] = []

            processed_params.append(Parameter(**param_dict))

        processed_responses = {}
        for status_code, response in operation.responses.items():
            schema = None
            format = "text/plain"
            if response.content and "application/json" in response.content:
                schema = cls._process_schema(
                    response.content["application/json"].schema_, api
                )
                format = "application/json"
            processed_responses[status_code] = Response(
                description=response.description,
                content=response.content,
                schema_=schema,
                format=format,
            )

        # Process request body if present
        request_body = None
        if operation.requestBody:
            schema = None
            encoding = None
            content_type = None

            # Handle form-encoded content
            if (
                operation.requestBody.content
                and "application/x-www-form-urlencoded" in operation.requestBody.content
            ):
                content = operation.requestBody.content[
                    "application/x-www-form-urlencoded"
                ]
                content_type = "application/x-www-form-urlencoded"
                if content.schema_:
                    schema = cls._process_schema(content.schema_, api)
                if content.encoding:
                    # Convert encoding object to dictionary
                    encoding = {}
                    for field_name, encoding_obj in content.encoding.items():
                        encoding[field_name] = {
                            "explode": getattr(encoding_obj, "explode", None),
                            "style": getattr(encoding_obj, "style", None),
                            "allowReserved": getattr(
                                encoding_obj, "allowReserved", None
                            ),
                            "contentType": getattr(encoding_obj, "contentType", None),
                        }
            # Handle JSON content
            elif (
                operation.requestBody.content
                and "application/json" in operation.requestBody.content
            ):
                content_schema = operation.requestBody.content[
                    "application/json"
                ].schema_
                schema = cls._process_schema(content_schema, api)
                content_type = "application/json"

            request_body = RequestBody(
                description=getattr(operation.requestBody, "description", None),
                content=operation.requestBody.content,
                required=bool(getattr(operation.requestBody, "required", False)),
                schema_=schema,
                encoding=encoding,
                content_type=content_type,
            )

        return Operation(
            id=operation.operationId or path_name,
            summary=operation.summary,
            description=operation.description,
            parameters=processed_params,
            request_body_=request_body,
            responses=processed_responses,
        )

    def __repr__(self) -> str:
        output = []

        def _repr_schema(schema: Schema, indent: str = "") -> str:
            """Helper function to format schema details recursively."""
            output = []
            # Handle regular properties
            output.append(f"{indent}Properties:")
            for prop in schema.properties:
                output.append(f"{indent}  - {prop.name}: {prop.type}")
                if prop.all_of:
                    output.append(f"{indent}{" " * 4}All of:")
                    for sub_schema in prop.all_of:
                        output.append(f"{indent}{" " * 6}- Type: {sub_schema.type}")
                        if sub_schema.properties:
                            output.append(f"{indent}{" " * 8}Properties:")
                            for prop in sub_schema.properties:
                                output.append(
                                    f"{indent}{" " * 10}- {prop.name}: {prop.type}"
                                )
                                if prop.items:
                                    output.append(
                                        f"{indent}{" " * 12}Items: {prop.items.name}"
                                    )
                                    if prop.items.properties:
                                        output.append(f"{indent}{" " * 14}Properties:")
                                        for item_prop in prop.items.properties:
                                            output.append(
                                                f"{indent}{" " * 16}- {item_prop.name}: {item_prop.type}"
                                            )
                        elif prop.properties:
                            output.append(f"{indent}{" " * 12}Properties:")
                            for nested_prop in prop.properties:
                                output.append(
                                    f"{indent}{" " * 14}- {nested_prop.name}: {nested_prop.type}"
                                )
                elif prop.any_of:
                    output.append(f"{indent}{" " * 4}Any of:")
                    for sub_schema in prop.any_of:
                        output.append(f"{indent}{" " * 6}- Type: {sub_schema.type}")
                        if sub_schema.properties:
                            output.append(f"{indent}{" " * 8}Properties:")
                            for prop in sub_schema.properties:
                                output.append(
                                    f"{indent}{" " * 10}- {prop.name}: {prop.type}"
                                )
                                if prop.items:
                                    output.append(
                                        f"{indent}{" " * 12}Items: {prop.items.name}"
                                    )
                                    if prop.items.properties:
                                        output.append(f"{indent}{" " * 14}Properties:")
                                        for item_prop in prop.items.properties:
                                            output.append(
                                                f"{indent}{" " * 16}- {item_prop.name}: {item_prop.type}"
                                            )
                        elif prop.properties:
                            output.append(f"{indent}{" " * 12}Properties:")
                            for nested_prop in prop.properties:
                                output.append(
                                    f"{indent}{" " * 14}- {nested_prop.name}: {nested_prop.type}"
                                )
                elif prop.items:
                    output.append(f"{indent}{" " * 4}Items: {prop.items.name}")
                    if prop.items.properties:
                        output.append(f"{indent}{" " * 4}Properties:")
                        for item_prop in prop.items.properties:
                            output.append(
                                f"{indent}{" " * 6}- {item_prop.name}: {item_prop.type}"
                            )
                elif prop.properties:
                    output.append(f"{indent}{" " * 4}Properties:")
                    for nested_prop in prop.properties:
                        output.append(
                            f"{indent}{" " * 6}- {nested_prop.name}: {nested_prop.type}"
                        )

            return "\n".join(output)

        for path in self.paths:
            if path.get:
                output.append(f"GET: {path.get.summary}")
                output.append("Parameters:")
                for param in path.get.parameters:
                    output.append(f"  - {param.name} ({param.in_})")
                output.append("Responses:")
                for status_code, response in path.get.responses.items():
                    output.append(f"  - {status_code}: {response.description}")
                    if response.schema_:
                        output.append(f"    Schema: {response.schema_.name}")
                        output.append(_repr_schema(response.schema_, "    "))

            for method, operation in [
                ("POST", path.post),
                ("PUT", path.put),
                ("DELETE", path.delete),
                ("PATCH", path.patch),
            ]:
                if operation:
                    output.append(f"{method}: {operation.summary}")
                    if operation.request_body_:
                        output.append("Request body:")
                        if operation.request_body_.schema_:
                            output.append(
                                f"  Schema: {operation.request_body_.schema_.name}"
                            )
                            output.append(
                                _repr_schema(operation.request_body_.schema_, "  ")
                            )
                    output.append("Responses:")
                    for status_code, response in operation.responses.items():
                        output.append(f"  - {status_code}: {response.description}")
                        if response.schema_:
                            output.append(f"    Schema: {response.schema_.name}")
                            output.append(_repr_schema(response.schema_, "    "))

        return "\n".join(output)
