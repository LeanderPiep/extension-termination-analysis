from __future__ import annotations

import json
import re
from urllib import request
from typing import List


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

    with request.urlopen(req, timeout=180) as response:
        raw = json.loads(response.read()).get("response", "")

    return raw.replace("\\n", "\n").strip()


def _sanitize_code_output(text: str) -> str:
    """
    Best-effort cleanup if the model returns fenced code blocks.
    """
    if not text:
        return ""
    t = text.strip()

    # Remove ```python ... ``` or ``` ... ``` if they wrap the whole output
    t = re.sub(r"^\s*```(?:python)?\s*\n?", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\n?\s*```\s*$", "", t)

    return t.strip()


def _extract_json_from_text(s: str) -> str:
    """
    Best-effort extraction of the first JSON value (object or array) from a string.
    Handles common LLM annoyances (leading/trailing text, code fences).
    Returns the JSON substring if found, otherwise returns the original string.
    """
    text = s.strip()

    # Strip code fences if present
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            candidate = parts[1]
            candidate = re.sub(r"^\s*[a-zA-Z0-9_+-]+\s*\n", "", candidate)
            text = candidate.strip()

    start_candidates = []
    for ch in ("{", "["):
        idx = text.find(ch)
        if idx != -1:
            start_candidates.append(idx)
    if not start_candidates:
        return s

    start = min(start_candidates)

    for i in range(start, len(text)):
        if text[i] not in "{[":
            continue
        try:
            _, end = json.JSONDecoder().raw_decode(text[i:])
            return text[i : i + end]
        except Exception:
            continue

    return s


def _parse_json_array_of_strings(s: str, what: str, key: str | None = None) -> List[str]:
    """
    Accepts either:
      - JSON array of strings: ["foo", "bar"]
      - JSON object with a list under `key`: {"called_functions": ["foo", "bar"]}
    Also tolerates extra text around JSON and code fences.
    Raises ValueError if invalid.
    """
    raw = _extract_json_from_text(s)

    try:
        obj = json.loads(raw)
    except Exception as e:
        raise ValueError(f"{what}: Expected JSON, got invalid JSON.\nRaw:\n{s}\nError: {e}")

    if isinstance(obj, dict):
        if key is None:
            # If no key specified, try to find the first list[str] value
            list_candidates = [
                v for v in obj.values()
                if isinstance(v, list) and all(isinstance(x, str) for x in v)
            ]
            if len(list_candidates) == 1:
                obj = list_candidates[0]
            else:
                raise ValueError(
                    f"{what}: Expected JSON array of strings or JSON object containing one list[str].\nRaw:\n{s}"
                )
        else:
            if key not in obj:
                raise ValueError(f"{what}: JSON object missing key '{key}'.\nRaw:\n{s}")
            obj = obj[key]

    if not isinstance(obj, list) or not all(isinstance(x, str) for x in obj):
        raise ValueError(f"{what}: Expected JSON array of strings.\nRaw:\n{s}")

    return [x.strip() for x in obj if x.strip()]


# =========================
# PIPELINE 
# =========================

def find_called_functions_names(full_code: str, target_fn: str, url: str = DEFAULT_OLLAMA_URL) -> List[str]:
    prompt = f"""
    You are a static program analysis assistant.
    You reason over Python source code precisely and deterministically.
    You will be given a Python source code and a Target function.

    Task:
    Determine the set of functions that are directly or indirectly called by the target function.

    Output requirements:
    - Return ONLY a JSON object with this exact schema: "called_functions": ["..."]
    - The list MUST include the target function itself.
    - Use function names exactly as defined in the source code.
    - Output ONLY JSON. No markdown, no code fences, no extra text.

    Target function:
    {target_fn}

    Python source code:
    {full_code}
    """
    raw = _ollama_generate(prompt, url=url)
    return _parse_json_array_of_strings(raw, "find_called_functions_names", key="called_functions")


def summarize_called_functions(full_code: str, called_functions: str, url: str = DEFAULT_OLLAMA_URL) -> str:
    prompt = f"""
    You are a static program analysis assistant.
    You reason over Python source code precisely and deterministically.
    You will be given a Python source code and a JSON list 'Relevant Functions'.

    Task:
    - Extract ONLY the function definitions from the Python source code whose names are in 'Relevant Functions'
    - Return them concatenated as plain Python code
    - Output ONLY Python code. No markdown. No explanations. No comments.
    - Do NOT include any function definitions, imports, or any other statements.
    - Include each function exactly once.
    - Preserve the original indentation and line breaks exactly.

    Output requirements:
    - The first non-whitespace characters of your output MUST be 'def' or 'async def'.
    - Do NOT include ```python blocks

    Relevant Functions:
    {called_functions}
    
    Python source code:
    {full_code}
    """
    raw = _ollama_generate(prompt, url=url)
    return _sanitize_code_output(raw)


def topologically_sort_functions(called_functions_summary: str, url: str = DEFAULT_OLLAMA_URL) -> str:
    prompt = f"""
    You are a static program analysis assistant.
    You reason over Python source code precisely and deterministically.
    You will be given a Python source code containing function definitions.

    Task:
    Sort these functions in topological order based on their dependencies:
    - Functions that do not call any other functions from this set should appear at the top.
    - Functions that call other functions should appear after the ones they call.
    - Keep the function definitions exactly as they are, preserve indentation and line breaks.

    Output requirements:
    - Output ONLY Python code. No markdown. No explanations. No comments.
    - Do NOT include ```python blocks

    Python source code:
    {called_functions_summary}
    """
    raw = _ollama_generate(prompt, url=url)
    return _sanitize_code_output(raw)


def find_all_variable_dependencies(called_functions_summary: str, url: str = DEFAULT_OLLAMA_URL) -> List[str]:
    prompt = f"""
    You are a static program analysis assistant.
    You reason over Python source code precisely and deterministically.
    You will be given a Python source code containing function definitions.

    Task:
    Identify all global variables that are being used in the given source code. 
    A global variable is a variable that is being used in the code but not defined within a function. 
    Function parameters are NOT global variables.

    Output requirements:
    - Return ONLY a JSON object with this exact schema: "called_global_variables": ["..."]
    - Output ONLY JSON. No markdown, no code fences, no extra text.

    Python source code:
    {called_functions_summary}
    """
    raw = _ollama_generate(prompt, url=url)
    return _parse_json_array_of_strings(raw, "find_all_variable_dependencies", key=None)


def summarize_called_global_variables(full_code: str, called_global_variables: str, url: str = DEFAULT_OLLAMA_URL) -> str:
    prompt = f"""
    You are a static program analysis assistant.
    You reason over Python source code precisely and deterministically.
    You will be given a Python source code and a JSON list 'Global Variables'.

    Task:
    - Extract ONLY the variable definitions whose names are in 'Global Variables'
    - Return them concatenated as plain Python code
    - Output ONLY Python code. No markdown. No backticks. No explanations. No comments.
    - Do NOT include any global variables, imports, or any other statements.
    - Include each global variable exactly once.
    - Preserve the original indentation and line breaks exactly.

    Output requirements:
    - Output valid Python code.
    - No explanations, no comments, no extra text.
    - Do NOT include ```python blocks

    Global Variables:
    {called_global_variables}

    Python source code:
    {full_code}
    """
    raw = _ollama_generate(prompt, url=url)
    return _sanitize_code_output(raw)


def create_context(function_name: str, source_code: str, url: str = DEFAULT_OLLAMA_URL) -> str:
    """
    New pipeline:
    1) called functions
    2) extract those function definitions
    3) topologically sort them
    4) find global variables used inside those functions (heuristic prompt)
    5) extract those global variable definitions
    6) return globals + functions
    """
    called_functions = find_called_functions_names(source_code, function_name, url=url)

    called_functions_json = json.dumps(called_functions)

    called_functions_summary = summarize_called_functions(source_code, called_functions_json, url=url)
    called_functions_summary_sorted = topologically_sort_functions(called_functions_summary, url=url)

    called_global_variables = find_all_variable_dependencies(called_functions_summary, url=url)
    called_global_variables_json = json.dumps(called_global_variables)

    called_global_variables_summary = summarize_called_global_variables(source_code, called_global_variables_json, url=url)

    parts = []
    if called_global_variables_summary.strip():
        parts.append(called_global_variables_summary.strip())
    if called_functions_summary_sorted.strip():
        parts.append(called_functions_summary_sorted.strip())

    return "\n\n".join(parts)
