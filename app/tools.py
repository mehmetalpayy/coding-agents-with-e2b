import json
from typing import Callable
from e2b_code_interpreter import Execution, Sandbox


CODE_TOOLS = {"execute_code", "execute_bash"}
WEB_TOOLS = {
    "list_directory",
    "read_file",
    "write_file",
    "replace_in_file",
    "search_file_content",
    "glob",
}


def execute_code(sbx: Sandbox, code: str, language: str = "python") -> tuple:
    execution = sbx.run_code(code, language)
    metadata = {}
    for result in execution.results:
        if result.png:
            metadata["images"] = [result.png]
            result.png = None
            result.chart = None
    return execution.to_json(), metadata


tools = {
    "execute_code": execute_code,
    "execute_bash": lambda **a: execute_code(**a, language="bash"),
    "list_directory": lambda **a: execute_code(
        a["sbx"],
        f"list_directory(secure_path({repr(a.get('path', '.'))}), {repr(a.get('ignore'))}, {a.get('offset', 0)}, {a.get('limit', 16)})",
    ),
    "read_file": lambda **a: execute_code(
        a["sbx"],
        f"read_file(secure_path({repr(a.get('file_path', ''))}), {a.get('limit')}, {a.get('offset', 0)})",
    ),
    "write_file": lambda **a: execute_code(
        a["sbx"],
        f"write_file({repr(a.get('content', ''))}, secure_path({repr(a.get('file_path', ''))}))",
    ),
    "replace_in_file": lambda **a: execute_code(
        a["sbx"],
        f"replace_in_file(secure_path({repr(a.get('file_path', ''))}), {repr(a.get('old_string', ''))}, {repr(a.get('new_string', ''))}, {a.get('expected_replacements', 1)})",
    ),
    "search_file_content": lambda **a: execute_code(
        a["sbx"],
        f"search_file_content({repr(a.get('pattern', ''))}, {repr(a.get('include'))}, secure_path({repr(a.get('path', '.'))}), {a.get('use_regex', False)}, {a.get('fuzzy_threshold')}, {a.get('offset', 0)}, {a.get('limit', 16)})",
    ),
    "glob": lambda **a: execute_code(
        a["sbx"],
        f"glob({repr(a.get('pattern', ''))}, secure_path({repr(a.get('path', '.'))}), {repr(a.get('ignore'))}, {a.get('offset', 0)}, {a.get('limit', 16)})",
    ),
}


def execute_tool(
    name: str,
    args: str,
    tool_fns: dict[str, Callable],
    code_sbx: Sandbox,
    web_sbx: Sandbox,
) -> tuple:
    metadata = {}
    sbx = code_sbx if name in CODE_TOOLS else web_sbx
    try:
        parsed = json.loads(args)
        if name not in tool_fns:
            return {"error": f"Tool {name} doesn't exist."}, metadata
        result, metadata = tool_fns[name](**parsed, sbx=sbx)
    except json.JSONDecodeError as e:
        result = {"error": f"{name} failed to parse arguments: {str(e)}"}
    except KeyError as e:
        result = {"error": f"Missing key in arguments: {str(e)}"}
    except Exception as e:
        result = {"error": str(e)}
    return result, metadata
