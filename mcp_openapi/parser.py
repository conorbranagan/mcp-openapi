# stdlib
from typing import Dict, List, Optional, Any
import re
import logging
import pickle
import hashlib
from pathlib import Path

# 3p
import aiopenapi3
from aiopenapi3.plugin import Init, Document

import pathlib
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Create cache directory in the user's home directory
CACHE_DIR = Path.home() / ".mcp-openapi" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class SchemaProperty(BaseModel):
    name: str
    type: str | list[str]  # Can be a single type or list of types for anyOf
    items: Optional["SchemaProperty"] = None
    properties: Optional[List["SchemaProperty"]] = None
    description: Optional[str] = None
    any_of: Optional[List["SchemaProperty"]] = None  # For anyOf schemas
    all_of: Optional[List["SchemaProperty"]] = None  # For allOf schemas


class Schema(BaseModel):
    name: str
    properties: Optional[List[SchemaProperty]] = None


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


class SchemaSelector(Init):
    """
    remove the schemas we do not need models for
    """

    def __init__(self, *schemas):
        super().__init__()
        self._schemas = schemas

    def schemas(self, ctx: "Init.Context") -> "Init.Context":
        ctx.schemas = {
            k: ctx.schemas[k] for k in (set(self._schemas) & set(ctx.schemas.keys()))
        }
        return ctx


class RemovePaths(Document):
    def parsed(self, ctx: "Document.Context") -> "Document.Context":
        """
        emtpy the paths - not needed
        """
        ctx.document["paths"] = {}
        return ctx


class Config:
    @classmethod
    def from_file(
        cls,
        file_path: str,
        path_patterns: list[str],
        base_path=pathlib.Path("").absolute(),
    ):
        # Create cache key from file path and patterns
        cache_key = hashlib.md5(
            f"{file_path}:{','.join(sorted(path_patterns))}".encode()
        ).hexdigest()
        cache_file = CACHE_DIR / f"{cache_key}.pickle"

        if cache_file.exists():
            logger.info(f"Loading cached OpenAPI spec from {cache_file}")
            with open(cache_file, "rb") as f:
                return pickle.load(f)

        logger.info(f"Cold loading OpenAPI spec from {file_path}")
        api = aiopenapi3.OpenAPI.load_file(
            file_path,
            file_path,
            loader=aiopenapi3.FileSystemLoader(base_path),
        )
        config = cls._from_api(api, path_patterns)

        # Cache the result
        with open(cache_file, "wb") as f:
            pickle.dump(config, f)

        return config

    @classmethod
    def from_url(cls, url: str, path_patterns: list[str]):
        # Create cache key from URL and patterns
        cache_key = hashlib.md5(
            f"{url}:{','.join(sorted(path_patterns))}".encode()
        ).hexdigest()
        cache_file = CACHE_DIR / f"{cache_key}.pickle"

        if cache_file.exists():
            logger.info(f"Loading cached OpenAPI spec from {cache_file}")
            with open(cache_file, "rb") as f:
                return pickle.load(f)

        logger.info(f"Cold loading OpenAPI spec from {url}")
        api = aiopenapi3.OpenAPI.load_sync(
            url,
            loader=aiopenapi3.FileSystemLoader(pathlib.Path("")),
        )
        config = cls._from_api(api, path_patterns)

        # Cache the result
        with open(cache_file, "wb") as f:
            pickle.dump(config, f)

        return config

    @classmethod
    def _from_api(cls, api: aiopenapi3.OpenAPI, path_patterns: list[str]):
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

    def __init__(self, paths: List[Path]):
        self.paths = paths

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
            logger.warning(f"Max depth {max_depth} reached, stopping recursion")
            return None

        # Track visited schemas to prevent cycles
        if hasattr(schema, "ref"):
            schema_ref = schema.ref
            if schema_ref in visited:
                logger.warning(f"Circular reference detected for schema {schema_ref}")
                return None
            visited.add(schema_ref)

        properties = []
        if hasattr(schema, "ref"):
            schema_name = schema.ref.split("/")[-1]
            resolved_schema = api.components.schemas[schema_name]
        else:
            schema_name = "inline"
            resolved_schema = schema

        if resolved_schema.allOf:
            # For allOf, merge all schemas into one
            all_properties = []
            all_schemas = []
            for sub_schema in resolved_schema.allOf:
                sub_result = cls._process_schema(
                    sub_schema, api, depth + 1, max_depth, visited
                )
                if sub_result:
                    # Convert Schema to SchemaProperty for all_of
                    all_schemas.append(
                        SchemaProperty(
                            name=sub_result.name,
                            type="object",
                            properties=sub_result.properties,
                            description=sub_schema.description,
                        )
                    )
                    if sub_result.properties:
                        all_properties.extend(sub_result.properties)

            # Create a single property that contains all merged properties
            if all_properties:
                return Schema(
                    name=schema_name,
                    properties=[
                        SchemaProperty(
                            name="merged",
                            type="object",
                            properties=all_properties,
                            description=resolved_schema.description,
                            all_of=all_schemas,
                        )
                    ],
                )
            return None

        elif resolved_schema.anyOf:
            # For anyOf, create a property that can be any of the types
            any_of_properties = []
            types = []
            for sub_schema in resolved_schema.anyOf:
                if sub_schema.type:
                    types.append(sub_schema.type)
                sub_result = cls._process_schema(
                    sub_schema, api, depth + 1, max_depth, visited
                )
                if sub_result and sub_result.properties:
                    any_of_properties.extend(sub_result.properties)

            # Create a property with the union type, even if there are no properties
            return Schema(
                name=schema_name,
                properties=[
                    SchemaProperty(
                        name="any_of",
                        type=types if types else "object",
                        description=resolved_schema.description,
                        any_of=any_of_properties if any_of_properties else None,
                    )
                ],
            )

        elif resolved_schema.properties:
            for prop_name, prop_schema in resolved_schema.properties.items():
                # Get the type from the schema, defaulting to "object" if not specified
                prop_type = prop_schema.type or "object"
                prop = SchemaProperty(
                    name=prop_name, type=prop_type, description=prop_schema.description
                )

                if prop_type == "array" and prop_schema.items:
                    item_schema = prop_schema.items
                    if hasattr(item_schema, "ref"):
                        item_name = item_schema.ref.split("/")[-1]
                        resolved_item_schema = api.components.schemas[item_name]
                        if resolved_item_schema.type == "object":
                            item_properties = []
                            for (
                                item_prop_name,
                                item_prop_schema,
                            ) in resolved_item_schema.properties.items():
                                item_prop_type = item_prop_schema.type or "object"
                                item_prop = SchemaProperty(
                                    name=item_prop_name,
                                    type=item_prop_type,
                                    description=item_prop_schema.description,
                                )
                                if item_prop_type == "object":
                                    nested_schema = cls._process_schema(
                                        item_prop_schema,
                                        api,
                                        depth + 1,
                                        max_depth,
                                        visited,
                                    )
                                    if nested_schema:
                                        item_prop.properties = nested_schema.properties
                                item_properties.append(item_prop)
                            prop.items = SchemaProperty(
                                name=item_name,
                                type="object",
                                properties=item_properties,
                                description=item_schema.description,
                            )
                    else:
                        item_type = item_schema.type or "object"
                        prop.items = SchemaProperty(
                            name="item",
                            type=item_type,
                            description=item_schema.description,
                        )

                elif prop_type == "object":
                    if hasattr(prop_schema, "ref"):
                        nested_schema = cls._process_schema(
                            prop_schema, api, depth + 1, max_depth, visited
                        )
                        if nested_schema:
                            prop.properties = nested_schema.properties
                    elif prop_schema.anyOf:
                        # Handle anyOf in object properties
                        types = []
                        any_of_schemas = []
                        for schema in prop_schema.anyOf:
                            if schema.type:
                                types.append(schema.type)
                            result = cls._process_schema(
                                schema, api, depth + 1, max_depth, visited
                            )
                            if result:
                                # Convert Schema to SchemaProperty for any_of
                                any_of_schemas.append(
                                    SchemaProperty(
                                        name=result.name,
                                        type=schema.type
                                        or "object",  # Use the schema's type
                                        properties=result.properties,
                                        description=schema.description,
                                    )
                                )

                        prop.type = types if types else "object"
                        prop.any_of = any_of_schemas
                        # For anyOf in object properties, we don't merge properties
                        prop.properties = None
                    elif prop_schema.allOf:
                        # Handle allOf in object properties
                        all_properties = []
                        all_schemas = []
                        for schema in prop_schema.allOf:
                            result = cls._process_schema(
                                schema, api, depth + 1, max_depth, visited
                            )
                            if result:
                                # Convert Schema to SchemaProperty for all_of
                                all_schemas.append(
                                    SchemaProperty(
                                        name=result.name,
                                        type="object",
                                        properties=result.properties,
                                        description=schema.description,
                                    )
                                )
                                if result.properties:
                                    all_properties.extend(result.properties)
                        if all_properties:
                            prop.properties = all_properties
                            prop.all_of = all_schemas
                    elif prop_schema.additionalProperties:
                        # For additionalProperties, we don't set properties
                        prop.properties = None
                    else:
                        nested_properties = []
                        for (
                            nested_name,
                            nested_schema,
                        ) in prop_schema.properties.items():
                            if nested_schema.anyOf:
                                # Handle anyOf in nested properties
                                types = []
                                any_of_schemas = []
                                for schema in nested_schema.anyOf:
                                    if schema.type:
                                        types.append(schema.type)
                                    result = cls._process_schema(
                                        schema, api, depth + 1, max_depth, visited
                                    )
                                    if result:
                                        # Convert Schema to SchemaProperty for any_of
                                        any_of_schemas.append(
                                            SchemaProperty(
                                                name=result.name,
                                                type=schema.type
                                                or "object",  # Use the schema's type
                                                properties=result.properties,
                                                description=schema.description,
                                            )
                                        )
                                nested_prop = SchemaProperty(
                                    name=nested_name,
                                    type=types if types else "object",
                                    description=nested_schema.description,
                                    any_of=any_of_schemas,
                                )
                                nested_properties.append(nested_prop)
                            else:
                                nested_schema = cls._process_schema(
                                    nested_schema, api, depth + 1, max_depth, visited
                                )
                                if nested_schema and nested_schema.properties:
                                    nested_prop = nested_schema.properties[0]
                                    nested_prop.name = nested_name
                                    nested_properties.append(nested_prop)

                        prop.properties = nested_properties

                properties.append(prop)
        elif resolved_schema.type == "array":
            # Add null check for items
            if not resolved_schema.items:
                return Schema(name=schema_name, properties=[])

            processed_items = cls._process_schema(
                resolved_schema.items, api, depth + 1, max_depth, visited
            )

            if not processed_items:
                return Schema(name=schema_name, properties=[])

            properties.append(
                SchemaProperty(
                    name="inline",
                    type="array",
                    description=resolved_schema.description,
                    items=SchemaProperty(
                        name="item",
                        type=resolved_schema.items.type or "object",
                        properties=processed_items.properties,
                        description=resolved_schema.items.description,
                    ),
                )
            )
        return Schema(
            name=schema_name,
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
                param_dict["required"] = True
            if param.schema_.default:
                param_dict["default"] = param.schema_.default

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

            # Handle form-encoded content
            if (
                operation.requestBody.content
                and "application/x-www-form-urlencoded" in operation.requestBody.content
            ):
                content = operation.requestBody.content[
                    "application/x-www-form-urlencoded"
                ]
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

            request_body = RequestBody(
                description=getattr(operation.requestBody, "description", None),
                content=operation.requestBody.content,
                required=bool(getattr(operation.requestBody, "required", False)),
                schema_=schema,
                encoding=encoding,
            )

        return Operation(
            id=operation.operationId or path_name,
            summary=operation.summary,
            description=operation.description,
            parameters=processed_params,
            request_body_=request_body,
            responses=processed_responses,
        )

    def __repr__(self):
        output = []

        def _repr_schema(schema: Schema, indent: str = "") -> str:
            """Helper function to format schema details recursively."""
            output = []
            if schema.properties:
                output.append(f"{indent}Properties:")
                for prop in schema.properties:
                    output.append(f"{indent}  - {prop.name}: {prop.type}")
                    if prop.items:
                        output.append(f"{indent}    Items: {prop.items.name}")
                        if prop.items.properties:
                            output.append(f"{indent}    Properties:")
                            for item_prop in prop.items.properties:
                                output.append(
                                    f"{indent}      - {item_prop.name}: {item_prop.type}"
                                )
                    elif prop.properties:
                        output.append(f"{indent}    Properties:")
                        for nested_prop in prop.properties:
                            output.append(
                                f"{indent}      - {nested_prop.name}: {nested_prop.type}"
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
