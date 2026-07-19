import json
import pytest
import tempfile
import yaml
import os
from pathlib import Path

from mcp_openapi.parser import Spec, Schema, RequestBody


@pytest.fixture
def sample_openapi_spec():
    return {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/api/v1/users": {
                "get": {
                    "operationId": "getUsers",
                    "summary": "Get all users",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer"},
                            "description": "Number of users to return",
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "string"},
                                                "name": {"type": "string"},
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                },
                "post": {
                    "operationId": "createUser",
                    "summary": "Create a new user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "User created successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                },
            },
            "/api/v1/users/{userId}": {
                "get": {
                    "operationId": "getUser",
                    "summary": "Get user by ID",
                    "parameters": [
                        {
                            "name": "userId",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
        },
    }


@pytest.fixture
def sample_openapi_spec_with_refs():
    return {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                    },
                },
                "UserInput": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                    },
                },
            },
            "parameters": {
                "userIdParam": {
                    "name": "userId",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
            },
        },
        "paths": {
            "/api/v1/users": {
                "get": {
                    "operationId": "getUsers",
                    "summary": "Get all users",
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/User"},
                                    }
                                }
                            },
                        }
                    },
                },
                "post": {
                    "operationId": "createUser",
                    "summary": "Create a new user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/UserInput"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "User created successfully",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            },
                        }
                    },
                },
            },
            "/api/v1/users/{userId}": {
                "get": {
                    "operationId": "getUser",
                    "summary": "Get user by ID",
                    "parameters": [{"$ref": "#/components/parameters/userIdParam"}],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            },
                        }
                    },
                }
            },
        },
    }


@pytest.fixture
def nasa_apod_spec():
    return {
        "openapi": "3.0.0",
        "servers": [
            {"url": "https://api.nasa.gov/planetary"},
            {"url": "http://api.nasa.gov/planetary"},
        ],
        "info": {
            "contact": {"email": "evan.t.yates@nasa.gov"},
            "description": "This endpoint structures the APOD imagery and associated metadata so that it can be repurposed for other applications. In addition, if the concept_tags parameter is set to True, then keywords derived from the image explanation are returned. These keywords could be used as auto-generated hashtags for twitter or instagram feeds; but generally help with discoverability of relevant imagery",
            "license": {
                "name": "Apache 2.0",
                "url": "http://www.apache.org/licenses/LICENSE-2.0.html",
            },
            "title": "APOD",
            "version": "1.0.0",
            "x-apisguru-categories": ["media", "open_data"],
            "x-origin": [
                {
                    "format": "swagger",
                    "url": "https://raw.githubusercontent.com/nasa/api-docs/gh-pages/assets/json/APOD",
                    "version": "2.0",
                }
            ],
            "x-providerName": "nasa.gov",
            "x-serviceName": "apod",
        },
        "tags": [
            {
                "description": "An example tag",
                "externalDocs": {
                    "description": "Here's a link",
                    "url": "https://example.com",
                },
                "name": "request tag",
            }
        ],
        "paths": {
            "/apod": {
                "get": {
                    "description": "Returns the picture of the day",
                    "parameters": [
                        {
                            "description": "The date of the APOD image to retrieve",
                            "in": "query",
                            "name": "date",
                            "required": False,
                            "schema": {"type": "string"},
                        },
                        {
                            "description": "Retrieve the URL for the high resolution image",
                            "in": "query",
                            "name": "hd",
                            "required": False,
                            "schema": {"type": "boolean"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "items": {"x-thing": "ok"},
                                        "type": "array",
                                    }
                                }
                            },
                            "description": "successful operation",
                        },
                        "400": {
                            "description": "Date must be between Jun 16, 1995 and Mar 28, 2019."
                        },
                    },
                    "security": [{"api_key": []}],
                    "summary": "Returns images",
                    "tags": ["request tag"],
                }
            }
        },
        "components": {
            "securitySchemes": {
                "api_key": {"in": "query", "name": "api_key", "type": "apiKey"}
            }
        },
    }


@pytest.fixture
def weather_api_spec():
    return {
        "openapi": "3.0.0",
        "info": {"title": "Weather API", "version": "1.0.0"},
        "paths": {
            "/v1/forecast": {
                "get": {
                    "operationId": "getForecast",
                    "summary": "Get weather forecast",
                    "parameters": [
                        {
                            "name": "temperature_unit",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "default": "celsius",
                                "enum": ["celsius", "fahrenheit"],
                            },
                            "description": "Temperature unit",
                        },
                        {
                            "name": "wind_speed_unit",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "default": "kmh",
                                "enum": ["kmh", "ms", "mph", "kn"],
                            },
                            "description": "Wind speed unit",
                        },
                        {
                            "name": "timeformat",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "default": "iso8601",
                                "enum": ["iso8601", "unixtime"],
                            },
                            "description": "Time format",
                        },
                        {
                            "name": "include_current",
                            "in": "query",
                            "schema": {"type": "boolean", "default": False},
                            "description": "Include current conditions",
                        },
                        {
                            "name": "offset_days",
                            "in": "query",
                            "schema": {"type": "integer", "default": 0},
                            "description": "Forecast offset in days",
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "temperature": {"type": "number"},
                                            "wind_speed": {"type": "number"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }


@pytest.fixture
def form_encoded_spec():
    return {
        "openapi": "3.0.0",
        "info": {"title": "Form API", "version": "1.0.0"},
        "paths": {
            "/v1/customers": {
                "post": {
                    "operationId": "createCustomer",
                    "summary": "Create a customer",
                    "requestBody": {
                        "content": {
                            "application/x-www-form-urlencoded": {
                                "encoding": {
                                    "address": {"explode": True, "style": "deepObject"},
                                    "metadata": {
                                        "explode": True,
                                        "style": "deepObject",
                                    },
                                },
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                            "maxLength": 256,
                                            "description": "The customer's full name or business name.",
                                        },
                                        "email": {
                                            "type": "string",
                                            "maxLength": 512,
                                            "description": "Customer's email address",
                                        },
                                        "address": {
                                            "anyOf": [
                                                {
                                                    "type": "object",
                                                    "properties": {
                                                        "line1": {
                                                            "type": "string",
                                                            "maxLength": 5000,
                                                        },
                                                        "city": {
                                                            "type": "string",
                                                            "maxLength": 5000,
                                                        },
                                                        "country": {
                                                            "type": "string",
                                                            "maxLength": 5000,
                                                        },
                                                    },
                                                },
                                                {"type": "string", "enum": [""]},
                                            ],
                                            "description": "The customer's address",
                                        },
                                        "metadata": {
                                            "anyOf": [
                                                {
                                                    "type": "object",
                                                    "additionalProperties": {
                                                        "type": "string"
                                                    },
                                                },
                                                {"type": "string", "enum": [""]},
                                            ],
                                            "description": "Set of key-value pairs",
                                        },
                                        "invoice_settings": {
                                            "type": "object",
                                            "properties": {
                                                "custom_fields": {
                                                    "anyOf": [
                                                        {
                                                            "type": "array",
                                                            "items": {
                                                                "type": "object",
                                                                "properties": {
                                                                    "name": {
                                                                        "type": "string",
                                                                        "maxLength": 40,
                                                                    },
                                                                    "value": {
                                                                        "type": "string",
                                                                        "maxLength": 140,
                                                                    },
                                                                },
                                                                "required": [
                                                                    "name",
                                                                    "value",
                                                                ],
                                                            },
                                                        },
                                                        {
                                                            "type": "string",
                                                            "enum": [""],
                                                        },
                                                    ]
                                                }
                                            },
                                        },
                                    },
                                },
                            }
                        },
                        "required": True,
                    },
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }


@pytest.fixture
def anyof_allof_spec():
    return {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/test": {
                "post": {
                    "operationId": "testEndpoint",
                    "summary": "Test endpoint with anyOf and allOf",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "any_of_field": {
                                            "anyOf": [
                                                {"type": "string"},
                                                {"type": "integer"},
                                                {"type": "number"},
                                                {"type": "boolean"},
                                            ],
                                            "description": "Field that can be multiple types",
                                        },
                                        "all_of_field": {
                                            "allOf": [
                                                {
                                                    "type": "object",
                                                    "properties": {
                                                        "name": {"type": "string"},
                                                        "age": {"type": "integer"},
                                                    },
                                                },
                                                {
                                                    "type": "object",
                                                    "properties": {
                                                        "email": {"type": "string"},
                                                        "active": {"type": "boolean"},
                                                    },
                                                },
                                            ],
                                            "description": "Field that must satisfy all schemas",
                                        },
                                        "nested_any_of": {
                                            "type": "object",
                                            "properties": {
                                                "status": {
                                                    "anyOf": [
                                                        {
                                                            "type": "string",
                                                            "enum": [
                                                                "active",
                                                                "inactive",
                                                            ],
                                                        },
                                                        {
                                                            "type": "integer",
                                                            "enum": [1, 0],
                                                        },
                                                    ]
                                                }
                                            },
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "id": {"type": "string"},
                                                    "created_at": {"type": "string"},
                                                },
                                            },
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "status": {"type": "string"},
                                                    "type": {"type": "string"},
                                                },
                                            },
                                        ]
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }


@pytest.fixture
def mock_operation():
    """Create a mock operation with various parameter types"""
    # Create request body schema with nested properties
    request_body_schema = Schema(
        name="TestRequestBody",
        type="object",
        properties=[
            Schema(
                name="body_string", type="string", description="A body string parameter"
            ),
            Schema(
                name="body_object",
                type="object",
                description="A body object parameter",
                properties=[
                    Schema(
                        name="nested_string",
                        type="string",
                        description="A nested string parameter",
                    ),
                    Schema(
                        name="nested_int",
                        type="integer",
                        description="A nested integer parameter",
                    ),
                ],
            ),
            Schema(
                name="anyof_object_or_string",
                description="A union parameter that can be object or string",
                type=["object", "string"],
                any_of=[
                    Schema(
                        name="ObjectSchema",
                        type="object",
                        properties=[
                            Schema(
                                name="anyof_nested_string",
                                type="string",
                                description="A nested string parameter",
                            ),
                            Schema(
                                name="anyof_nested_int",
                                type="integer",
                                description="A nested integer parameter",
                            ),
                        ],
                    ),
                    Schema(
                        name="anyof_string",
                        type="string",
                        description="A string parameter",
                    ),
                ],
            ),
        ],
    )

    # Create request body
    _ = RequestBody(description="Test request body", schema_=request_body_schema)


def test_path_pattern_matching(tmp_path, sample_openapi_spec):
    # Create a temporary OpenAPI spec file
    spec_file = tmp_path / "openapi.json"
    with open(spec_file, "w") as f:
        json.dump(sample_openapi_spec, f)

    # Test exact path matching
    spec = Spec.from_file(str(spec_file), ["/api/v1/users$"], base_path=tmp_path)
    assert len(spec.paths) == 1
    assert spec.paths[0].path == "/api/v1/users"

    # Verify GET operation details
    get_op = spec.paths[0].get
    assert get_op.id == "getUsers"
    assert get_op.summary == "Get all users"
    assert len(get_op.parameters) == 1
    assert get_op.parameters[0].name == "limit"
    assert get_op.parameters[0].in_ == "query"
    assert get_op.parameters[0].type == "integer"

    # Test regex pattern matching for path parameters
    spec = Spec.from_file(str(spec_file), [r"/api/v1/users/\{.*\}"], base_path=tmp_path)
    assert len(spec.paths) == 1
    assert spec.paths[0].path == "/api/v1/users/{userId}"

    # Verify path parameter operation
    get_op = spec.paths[0].get
    assert get_op.id == "getUser"
    assert get_op.parameters[0].name == "userId"
    assert get_op.parameters[0].in_ == "path"
    assert get_op.parameters[0].required is True


def test_request_response_processing(tmp_path, sample_openapi_spec):
    spec_file = tmp_path / "openapi.json"
    with open(spec_file, "w") as f:
        json.dump(sample_openapi_spec, f)

    spec = Spec.from_file(str(spec_file), ["/api/v1/users"], base_path=tmp_path)
    assert len(spec.paths) == 2
    path = spec.paths[0]

    # Test GET response schema
    get_response = path.get.responses["200"]
    assert get_response.format == "application/json"
    assert get_response.description == "Successful response"
    schema = get_response.schema_
    assert schema.properties[0].type == "array"
    assert schema.properties[0].items.type == "object"
    assert len(schema.properties[0].items.properties) == 2

    # Test POST request and response
    post_op = path.post
    assert post_op.request_body_.required is True
    request_schema = post_op.request_body_.schema_
    assert len(request_schema.properties) == 2
    assert {p.name for p in request_schema.properties} == {"name", "email"}
    assert all(p.type == "string" for p in request_schema.properties)

    # Test POST response
    post_response = post_op.responses["201"]
    assert post_response.format == "application/json"
    assert post_response.description == "User created successfully"
    response_schema = post_response.schema_
    assert len(response_schema.properties) == 2
    assert {p.name for p in response_schema.properties} == {"id", "name"}


def test_xquik_search_openapi_31_fixture(tmp_path):
    xquik_spec = {
        "openapi": "3.1.0",
        "info": {
            "title": "Xquik API",
            "version": "1.0",
            "description": 'Xquik is an independent third-party service. Not affiliated with X Corp. "Twitter" and "X" are trademarks of X Corp.',
        },
        "servers": [{"url": "https://xquik.com"}],
        "paths": {
            "/api/v1/x/tweets/search": {
                "get": {
                    "operationId": "searchTweets",
                    "summary": "Search tweets by query, Tweet ID, X status URL, or account date window",
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "queryType",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "enum": ["Latest", "Top"],
                                "default": "Latest",
                            },
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {
                                "type": "integer",
                                "default": 20,
                                "maximum": 200,
                            },
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Search results",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "tweets": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "id": {"type": "string"},
                                                        "text": {"type": "string"},
                                                    },
                                                },
                                            },
                                            "has_next_page": {"type": "boolean"},
                                            "next_cursor": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }

    spec_file = tmp_path / "xquik-openapi.json"
    with open(spec_file, "w") as f:
        json.dump(xquik_spec, f)

    spec = Spec.from_file(
        str(spec_file),
        [r"/api/v1/x/tweets/search$"],
        base_path=tmp_path,
        use_cache=False,
    )

    assert len(spec.paths) == 1
    assert spec.paths[0].path == "/api/v1/x/tweets/search"

    get_op = spec.paths[0].get
    assert get_op.id == "searchTweets"
    assert (
        get_op.summary
        == "Search tweets by query, Tweet ID, X status URL, or account date window"
    )
    assert {p.name for p in get_op.parameters} == {"q", "queryType", "limit"}
    assert next(p for p in get_op.parameters if p.name == "q").required is True
    assert next(p for p in get_op.parameters if p.name == "queryType").enum == [
        "Latest",
        "Top",
    ]
    assert next(p for p in get_op.parameters if p.name == "queryType").required is False
    assert (
        next(p for p in get_op.parameters if p.name == "queryType").default == "Latest"
    )
    assert next(p for p in get_op.parameters if p.name == "limit").default == 20

    response = get_op.responses["200"]
    assert response.format == "application/json"
    assert {p.name for p in response.schema_.properties} == {
        "tweets",
        "has_next_page",
        "next_cursor",
    }


def test_multiple_path_patterns(tmp_path, sample_openapi_spec):
    spec_file = tmp_path / "openapi.json"
    with open(spec_file, "w") as f:
        json.dump(sample_openapi_spec, f)

    # Test matching multiple patterns
    spec = Spec.from_file(
        str(spec_file), [r"/api/v1/users", r"/api/v1/users/\{.*\}"], base_path=tmp_path
    )
    assert len(spec.paths) == 2
    paths = {p.path for p in spec.paths}
    assert paths == {"/api/v1/users", "/api/v1/users/{userId}"}

    # Verify all operations are properly loaded
    operations = []
    for path in spec.paths:
        if path.get:
            operations.append(path.get.id)
        if path.post:
            operations.append(path.post.id)

    assert set(operations) == {"getUsers", "createUser", "getUser"}


def test_reference_resolution(tmp_path, sample_openapi_spec_with_refs):
    spec_file = tmp_path / "openapi.json"
    with open(spec_file, "w") as f:
        json.dump(sample_openapi_spec_with_refs, f)

    spec = Spec.from_file(str(spec_file), ["/api/v1/users"], base_path=tmp_path)
    assert len(spec.paths) == 2
    path = spec.paths[0]

    # Test GET response schema with resolved reference
    get_response = path.get.responses["200"]
    schema = get_response.schema_
    assert schema.properties[0].type == "array"
    items = schema.properties[0].items
    assert items.type == "object"
    assert len(items.properties) == 2
    assert {p.name for p in items.properties} == {"id", "name"}

    # Test POST request body with resolved reference
    post_op = path.post
    request_schema = post_op.request_body_.schema_
    assert len(request_schema.properties) == 2
    assert {p.name for p in request_schema.properties} == {"name", "email"}

    # Test POST response with resolved reference
    post_response = post_op.responses["201"]
    response_schema = post_response.schema_
    assert len(response_schema.properties) == 2
    assert {p.name for p in response_schema.properties} == {"id", "name"}


def test_parameter_reference_resolution(tmp_path, sample_openapi_spec_with_refs):
    spec_file = tmp_path / "openapi.json"
    with open(spec_file, "w") as f:
        json.dump(sample_openapi_spec_with_refs, f)

    spec = Spec.from_file(str(spec_file), [r"/api/v1/users/\{.*\}"], base_path=tmp_path)
    assert len(spec.paths) == 1
    path = spec.paths[0]

    # Test resolved parameter reference
    get_op = path.get
    assert len(get_op.parameters) == 1
    param = get_op.parameters[0]
    assert param.name == "userId"
    assert param.in_ == "path"
    assert param.required is True
    assert param.type == "string"


def test_nasa_apod_spec_parsing(tmp_path, nasa_apod_spec):
    # Create a temporary OpenAPI spec file
    spec_file = tmp_path / "nasa_apod.json"
    with open(spec_file, "w") as f:
        json.dump(nasa_apod_spec, f)

    # Parse the spec
    spec = Spec.from_file(str(spec_file), ["/apod"], base_path=tmp_path)

    # Basic validation
    assert len(spec.paths) == 1
    assert spec.paths[0].path == "/apod"

    # Validate GET operation
    get_op = spec.paths[0].get
    assert get_op.id == "/apod"
    assert get_op.summary == "Returns images"
    assert get_op.description == "Returns the picture of the day"

    # Validate parameters
    assert len(get_op.parameters) == 2
    date_param = next(p for p in get_op.parameters if p.name == "date")
    assert date_param.in_ == "query"
    assert date_param.required is False
    assert date_param.type == "string"

    hd_param = next(p for p in get_op.parameters if p.name == "hd")
    assert hd_param.in_ == "query"
    assert hd_param.required is False
    assert hd_param.type == "boolean"

    # Validate responses
    assert "200" in get_op.responses
    assert "400" in get_op.responses
    success_response = get_op.responses["200"]
    assert success_response.format == "application/json"
    assert success_response.description == "successful operation"


def test_parameter_enums_and_defaults(tmp_path, weather_api_spec):
    spec_file = tmp_path / "weather_api.json"
    with open(spec_file, "w") as f:
        json.dump(weather_api_spec, f)

    spec = Spec.from_file(str(spec_file), ["/v1/forecast"], base_path=tmp_path)
    assert len(spec.paths) == 1
    path = spec.paths[0]

    # Test GET operation parameters
    get_op = path.get
    assert len(get_op.parameters) == 5

    # Test temperature_unit parameter
    temp_param = next(p for p in get_op.parameters if p.name == "temperature_unit")
    assert temp_param.type == "string"
    assert temp_param.enum == ["celsius", "fahrenheit"]
    assert temp_param.default == "celsius"

    # Test wind_speed_unit parameter
    wind_param = next(p for p in get_op.parameters if p.name == "wind_speed_unit")
    assert wind_param.type == "string"
    assert wind_param.enum == ["kmh", "ms", "mph", "kn"]
    assert wind_param.default == "kmh"

    # Test timeformat parameter
    time_param = next(p for p in get_op.parameters if p.name == "timeformat")
    assert time_param.type == "string"
    assert time_param.enum == ["iso8601", "unixtime"]
    assert time_param.default == "iso8601"

    include_current = next(p for p in get_op.parameters if p.name == "include_current")
    assert include_current.required is False
    assert include_current.default is False

    offset_days = next(p for p in get_op.parameters if p.name == "offset_days")
    assert offset_days.required is False
    assert offset_days.default == 0


def test_form_encoded_request_body(tmp_path, form_encoded_spec):
    spec_file = tmp_path / "form_api.json"
    with open(spec_file, "w") as f:
        json.dump(form_encoded_spec, f)

    spec = Spec.from_file(str(spec_file), ["/v1/customers"], base_path=tmp_path)
    assert len(spec.paths) == 1
    path = spec.paths[0]

    # Test POST operation
    post_op = path.post
    assert post_op.id == "createCustomer"
    assert post_op.request_body_.required is True

    # Test request body schema
    request_schema = post_op.request_body_.schema_
    assert len(request_schema.properties) == 5
    assert {p.name for p in request_schema.properties} == {
        "name",
        "email",
        "address",
        "metadata",
        "invoice_settings",
    }

    # Test encoding properties
    encoding = post_op.request_body_.encoding
    assert encoding is not None
    assert "address" in encoding
    assert "metadata" in encoding
    assert encoding["address"]["explode"] is True
    assert encoding["address"]["style"] == "deepObject"
    assert encoding["metadata"]["explode"] is True
    assert encoding["metadata"]["style"] == "deepObject"

    # Test nested schema properties
    address_prop = next(p for p in request_schema.properties if p.name == "address")
    assert address_prop.type == ["object", "string"]  # anyOf types
    assert address_prop.any_of is not None
    assert len(address_prop.any_of) == 2
    assert address_prop.any_of[0].type == "object"
    assert address_prop.any_of[1].type == "string"

    # Test metadata property with additionalProperties
    metadata_prop = next(p for p in request_schema.properties if p.name == "metadata")
    assert metadata_prop.type == ["object", "string"]  # anyOf types
    assert metadata_prop.any_of is not None
    assert len(metadata_prop.any_of) == 2

    # Test invoice_settings with nested anyOf
    invoice_settings = next(
        p for p in request_schema.properties if p.name == "invoice_settings"
    )
    assert invoice_settings.type == "object"
    assert len(invoice_settings.properties) == 1
    custom_fields = invoice_settings.properties[0]
    assert custom_fields.name == "custom_fields"
    assert custom_fields.type == ["array", "string"]  # anyOf types
    assert custom_fields.any_of is not None
    assert len(custom_fields.any_of) == 2
    assert custom_fields.any_of[0].type == "array"
    assert custom_fields.any_of[1].type == "string"

    # Test response schema
    response = post_op.responses["200"]
    assert response.format == "application/json"
    response_schema = response.schema_
    assert len(response_schema.properties) == 2
    assert {p.name for p in response_schema.properties} == {"id", "name"}


def test_circular_references():
    """Test handling of circular references in OpenAPI schemas."""
    # Create a test OpenAPI spec with circular references
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/test": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Person"}
                                }
                            },
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "Person": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "spouse": {"$ref": "#/components/schemas/Person"},
                        "children": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Person"},
                        },
                    },
                }
            }
        },
    }

    # Write the spec to a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(spec, f)
        spec_path = f.name

    try:
        # Load the spec
        spec = Spec.from_file(spec_path, ["/test"], base_path=Path(spec_path).parent)

        # Verify that the circular references are handled gracefully
        assert spec.paths is not None
        assert len(spec.paths) == 1
        path = spec.paths[0]
        assert path.get is not None
        assert path.get.responses is not None
        assert "200" in path.get.responses
        response = path.get.responses["200"]
        assert response.schema_ is not None

        # The schema should have properties but not infinite recursion
        schema = response.schema_
        assert schema.properties is not None
        assert len(schema.properties) > 0

        # Find the spouse property
        spouse_prop = next(p for p in schema.properties if p.name == "spouse")
        assert spouse_prop.type == "object"
        # The spouse property should not have infinite nested properties
        assert spouse_prop.properties is None

        # Find the children property
        children_prop = next(p for p in schema.properties if p.name == "children")
        assert children_prop.type == "array"
        assert children_prop.items is not None
        assert children_prop.items.type == "object"
        # The items should not have infinite nested properties
        # assert children_prop.items.properties is None

    finally:
        # Clean up the temporary file
        os.unlink(spec_path)


def test_anyof_allof_schemas(tmp_path, anyof_allof_spec):
    spec_file = tmp_path / "anyof_allof_api.json"
    with open(spec_file, "w") as f:
        json.dump(anyof_allof_spec, f)

    spec = Spec.from_file(str(spec_file), ["/test"], base_path=tmp_path)
    assert len(spec.paths) == 1
    path = spec.paths[0]

    # Test POST operation
    post_op = path.post
    assert post_op.id == "testEndpoint"
    assert post_op.request_body_.required is True

    # Test request body schema
    request_schema = post_op.request_body_.schema_
    assert len(request_schema.properties) == 3
    assert {p.name for p in request_schema.properties} == {
        "any_of_field",
        "all_of_field",
        "nested_any_of",
    }

    # Test anyOf field
    any_of_field = next(
        p for p in request_schema.properties if p.name == "any_of_field"
    )
    assert any_of_field.type == ["string", "integer", "number", "boolean"]
    assert any_of_field.any_of is not None
    assert len(any_of_field.any_of) == 4
    assert any_of_field.description == "Field that can be multiple types"

    # Test allOf field
    all_of_field = next(
        p for p in request_schema.properties if p.name == "all_of_field"
    )
    assert all_of_field.type == "object"
    assert all_of_field.all_of is not None
    assert len(all_of_field.all_of) == 2
    assert all_of_field.description == "Field that must satisfy all schemas"

    # Verify merged properties from allOf
    assert len(all_of_field.properties) == 1
    assert all_of_field.properties[0].name == "all_of"
    assert len(all_of_field.properties[0].properties) == 4
    assert {p.name for p in all_of_field.properties[0].properties} == {
        "name",
        "age",
        "email",
        "active",
    }

    # Test nested anyOf
    nested_any_of = next(
        p for p in request_schema.properties if p.name == "nested_any_of"
    )
    assert nested_any_of.type == "object"
    assert len(nested_any_of.properties) == 1
    status_prop = nested_any_of.properties[0]
    assert status_prop.name == "status"
    assert status_prop.type == ["string", "integer"]
    assert status_prop.any_of is not None
    assert len(status_prop.any_of) == 2

    # Test response schema with allOf
    response = post_op.responses["200"]
    assert response.format == "application/json"
    response_schema = response.schema_
    assert response_schema.properties[0].type == "object"
    assert response_schema.properties[0].all_of is not None
    assert len(response_schema.properties[0].all_of) == 2

    # Verify merged properties from response allOf
    assert len(response_schema.properties[0].properties) == 4
    assert {p.name for p in response_schema.properties[0].properties} == {
        "id",
        "created_at",
        "status",
        "type",
    }
