import json
from urllib import request
from typing import Any, Dict, List, Optional


DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "codellama:13b"


def _ollama_generate(prompt: str, url: str = DEFAULT_OLLAMA_URL) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "top_p": 1.0,
        },
    }

    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with request.urlopen(req, timeout=120) as response:
        raw = json.loads(response.read()).get("response", "")

    # normalize newlines (robust against escaped \\n)
    return raw.replace("\\n", "\n").strip()


def _parse_json_array_of_strings(s: str, what: str) -> List[str]:
    """
    Expects a JSON array of strings, e.g. ["foo", "bar"].
    Raises ValueError if invalid.
    """
    try:
        obj = json.loads(s)
    except Exception as e:
        raise ValueError(f"{what}: Expected JSON array, got invalid JSON.\nRaw:\n{s}\nError: {e}")

    if not isinstance(obj, list) or not all(isinstance(x, str) for x in obj):
        raise ValueError(f"{what}: Expected JSON array of strings.\nRaw:\n{s}")

    # strip whitespace just in case
    return [x.strip() for x in obj if x.strip()]


def find_called_functions_names(full_code: str, target_fn: str, url: str = DEFAULT_OLLAMA_URL) -> List[str]:
    prompt = f"""You are a static program analysis assistant.

Full source code:
{full_code}

Target function:
{target_fn}

Task:
- Create a list containing the 'Target function' and all functions that are directly or indirectly called by the 'Target function'.
- Do NOT include functions that are not directly or indirectly called by the 'Target function'.

Rules:
- Output ONLY a JSON array of function names that you identified in the Task, e.g. ["func1", "helper2"]
- No explanations, no extra text.
"""
    raw = _ollama_generate(prompt, url=url)
    return _parse_json_array_of_strings(raw, "find_called_functions_names")


def find_all_global_variables(full_code: str, url: str = DEFAULT_OLLAMA_URL) -> List[str]:
    prompt = f"""You are a static program analysis assistant.

Full source code:
{full_code}

Task:
- Identify all global variables that are defined in the 'Full source code'.

Rules:
- Output ONLY a JSON array of variable names, e.g. ["a", "b"]
- No explanations, no extra text.
"""
    raw = _ollama_generate(prompt, url=url)
    return _parse_json_array_of_strings(raw, "find_all_global_variables")


def summarize_called_functions(full_code: str, called_functions: List[str], url: str = DEFAULT_OLLAMA_URL) -> str:
    prompt = f"""You are a static program analysis assistant.

Full source code:
{full_code}

Relevant Functions:
{json.dumps(called_functions)}

Task:
- Identify only the definitions of the functions listed in 'Relevant Functions' and summarize them into one String.
- Do not include functions that are not listed in 'Relevant Functions'.
- Do NOT include any global variables.

Rules:
- Output valid Python code.
- Preserve indentation and line breaks.
- No explanations, no comments, no extra text.
- Do not add comments, explanations, or language identifiers.
"""
    return _ollama_generate(prompt, url=url)


def topologically_sort_functions(called_functions_summary: str, url: str = DEFAULT_OLLAMA_URL) -> str:
    prompt = f"""You are a static program analysis assistant.

Task:
- You are given a set of Python function definitions:
{called_functions_summary}

- Sort these functions in topological order based on their dependencies:
    * Functions that do not call any other functions from this set should appear at the top.
    * Functions that call other functions should appear after the ones they call.
- Keep the function definitions exactly as they are, preserve indentation and line breaks.
- Output only the sorted Python code.
- Do NOT include any functions that are not in the input.
- No explanations, no comments, no extra text, no Markdown formatting.
"""
    return _ollama_generate(prompt, url=url)


def find_all_variable_dependencies(called_functions_summary: str, global_variables: List[str], url: str = DEFAULT_OLLAMA_URL) -> List[str]:
    prompt = f"""You are a static program analysis assistant.

Sourcecode:
{called_functions_summary}

Global Variables:
{json.dumps(global_variables)}

Task:
- Look at every function in 'Sourcecode' and identify the variables that are being used, that are also in 'Global Variables'.

Rules:
- Output ONLY a JSON array of variable names, e.g. ["var_a", "var_b"]
- Do NOT include the function names in the JSON array.
- No explanations, no extra text.
"""
    raw = _ollama_generate(prompt, url=url)
    return _parse_json_array_of_strings(raw, "find_all_variable_dependencies")


def summarize_called_global_variables(full_code: str, called_global_variables: List[str], url: str = DEFAULT_OLLAMA_URL) -> str:
    prompt = f"""You are a static program analysis assistant.

Sourcecode:
{full_code}

Global Variables:
{json.dumps(called_global_variables)}

Task:
- Identify the definitions of the variables listed in 'Global Variables' and combine them into one String.
- Do not include functions.

Rules:
- Output valid Python code.
- Preserve indentation and line breaks.
- No explanations, no comments, no extra text.
- Do not add comments, explanations, or language identifiers.
"""
    return _ollama_generate(prompt, url=url)


def create_context(function_name: str, source_code: str, url: str = DEFAULT_OLLAMA_URL) -> str:
    """
    Public API (matches ast_context.py):
    Returns a Python code string consisting of:
      - relevant global variable definitions
      - relevant helper function definitions (topologically sorted)
    """
    # 1) which functions are relevant (target + direct/indirect calls)
    called_functions = find_called_functions_names(source_code, function_name, url=url)

    # 2) all globals in file
    global_variables = find_all_global_variables(source_code, url=url)

    # 3) extract only relevant function defs
    called_functions_summary = summarize_called_functions(source_code, called_functions, url=url)

    # 4) order them so dependencies appear first
    called_functions_summary_sorted = topologically_sort_functions(called_functions_summary, url=url)

    # 5) find used globals among those functions
    called_global_variables = find_all_variable_dependencies(called_functions_summary, global_variables, url=url)

    # 6) extract those global definitions
    called_global_variables_summary = summarize_called_global_variables(source_code, called_global_variables, url=url)

    # final context
    parts = []
    if called_global_variables_summary.strip():
        parts.append(called_global_variables_summary.strip())
    if called_functions_summary_sorted.strip():
        parts.append(called_functions_summary_sorted.strip())

    return "\n\n".join(parts)
