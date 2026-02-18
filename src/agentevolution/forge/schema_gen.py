"""Schema Generator — Auto-generate MCP-compatible JSON schemas from Python code."""

from __future__ import annotations

import ast
import textwrap
from typing import Any


# Python type → JSON schema type mapping
TYPE_MAP: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "None": "null",
    "any": "string",
}


def extract_function_info(code: str) -> dict[str, Any]:
    """Extract function name, parameters, docstring, and return type from Python code.

    Returns a dict with:
        - name: function name
        - description: docstring or empty string
        - parameters: list of {name, type, default, description}
        - return_type: return type annotation string
    """
    try:
        tree = ast.parse(textwrap.dedent(code))
    except SyntaxError:
        return {"name": "", "description": "", "parameters": [], "return_type": "any"}

    # Find the first function definition
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return _extract_from_funcdef(node)

    return {"name": "", "description": "", "parameters": [], "return_type": "any"}


def _extract_from_funcdef(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    """Extract info from a function definition AST node."""
    name = node.name
    docstring = ast.get_docstring(node) or ""

    # Extract parameters
    parameters = []
    args = node.args

    # Calculate defaults alignment (defaults are right-aligned)
    num_defaults = len(args.defaults)
    num_args = len(args.args)
    default_offset = num_args - num_defaults

    for i, arg in enumerate(args.args):
        if arg.arg == "self":
            continue

        param: dict[str, Any] = {"name": arg.arg}

        # Type annotation
        if arg.annotation:
            param["type"] = _annotation_to_str(arg.annotation)
        else:
            param["type"] = "any"

        # Default value
        default_index = i - default_offset
        if default_index >= 0 and default_index < len(args.defaults):
            param["default"] = _const_to_value(args.defaults[default_index])
            param["required"] = False
        else:
            param["required"] = True

        # Try to extract param description from docstring
        param["description"] = _extract_param_doc(docstring, arg.arg)

        parameters.append(param)

    # Return type
    return_type = "any"
    if node.returns:
        return_type = _annotation_to_str(node.returns)

    return {
        "name": name,
        "description": docstring.split("\n")[0] if docstring else "",
        "parameters": parameters,
        "return_type": return_type,
    }


def generate_input_schema(code: str) -> dict[str, Any]:
    """Generate an MCP-compatible JSON input schema from Python code.

    Returns a JSON Schema compatible dict.
    """
    info = extract_function_info(code)

    if not info["parameters"]:
        return {"type": "object", "properties": {}, "required": []}

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param in info["parameters"]:
        json_type = TYPE_MAP.get(param["type"], "string")
        prop: dict[str, Any] = {"type": json_type}

        if param.get("description"):
            prop["description"] = param["description"]
        if "default" in param:
            prop["default"] = param["default"]
        if param.get("required", True):
            required.append(param["name"])

        properties[param["name"]] = prop

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _annotation_to_str(node: ast.expr) -> str:
    """Convert an AST annotation node to a string."""
    if isinstance(node, ast.Constant):
        return str(node.value)
    elif isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_annotation_to_str(node.value)}.{node.attr}"
    elif isinstance(node, ast.Subscript):
        return f"{_annotation_to_str(node.value)}[{_annotation_to_str(node.slice)}]"
    return "any"


def _const_to_value(node: ast.expr) -> Any:
    """Convert an AST constant node to a Python value."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.List):
        return [_const_to_value(e) for e in node.elts]
    elif isinstance(node, ast.Dict):
        return {}
    elif isinstance(node, ast.Name) and node.id == "None":
        return None
    return None


def _extract_param_doc(docstring: str, param_name: str) -> str:
    """Try to extract parameter documentation from docstring."""
    if not docstring:
        return ""

    # Look for common docstring formats
    for line in docstring.split("\n"):
        stripped = line.strip()
        # Google style: param_name: description
        # numpy style: param_name : type
        # sphinx style: :param param_name: description
        if param_name in stripped:
            if stripped.startswith(f":param {param_name}:"):
                return stripped.split(":", 3)[-1].strip()
            elif stripped.startswith(f"{param_name}:"):
                return stripped.split(":", 1)[-1].strip()
            elif stripped.startswith(f"{param_name} :"):
                return stripped.split(":", 1)[-1].strip()

    return ""
