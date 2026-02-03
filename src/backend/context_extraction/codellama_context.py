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

    with request.urlopen(req, timeout=120) as response:
        raw = json.loads(response.read()).get("response", "")

    return raw.replace("\\n", "\n").strip()


def _extract_json_from_text(s: str) -> str:
    """
    Best-effort extraction of the first JSON value (object or array) from a string.
    Handles common LLM annoyances (leading/trailing text, code fences).
    Returns the JSON substring if found, otherwise returns the original string.
    """
    text = s.strip()

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
            obj, end = json.JSONDecoder().raw_decode(text[i:])
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
            list_candidates = [v for v in obj.values() if isinstance(v, list) and all(isinstance(x, str) for x in v)]
            if len(list_candidates) == 1:
                obj = list_candidates[0]
            else:
                raise ValueError(f"{what}: Expected JSON array of strings or JSON object containing one list[str].\nRaw:\n{s}")
        else:
            if key not in obj:
                raise ValueError(f"{what}: JSON object missing key '{key}'.\nRaw:\n{s}")
            obj = obj[key]

    if not isinstance(obj, list) or not all(isinstance(x, str) for x in obj):
        raise ValueError(f"{what}: Expected JSON array of strings.\nRaw:\n{s}")

    return [x.strip() for x in obj if x.strip()]


def find_called_functions_names(full_code: str, target_fn: str, url: str = DEFAULT_OLLAMA_URL) -> List[str]:
    prompt = f"""You are a deterministic Python code extractor.

    Full source code:
    {full_code}

    Task:
    - Return ONLY a JSON object with this exact schema: "called_functions": ["..."]
    - Include {target_fn}.
    - Include only functions that are directly or indirectly called by {target_fn}.

    Rules:
    - Use function names exactly as defined.
    - Output ONLY JSON. No markdown, no code fences, no extra text.
    """
    raw = _ollama_generate(prompt, url=url)
    return _parse_json_array_of_strings(raw, "find_called_functions_names", key="called_functions")


def find_all_global_variables(full_code: str, url: str = DEFAULT_OLLAMA_URL) -> List[str]:
    prompt = f"""You are a deterministic Python code extractor.

    Full source code:
    {full_code}

    Task:
    - Return ONLY a JSON object with this exact schema: "all_variables": ["..."]
    - Identify all global variables that are defined in the 'Full source code'.

    Rules:
    - Use variable names exactly as defined.
    - Output ONLY JSON. No markdown, no code fences, no extra text.
    """
    raw = _ollama_generate(prompt, url=url)
    return _parse_json_array_of_strings(raw, "find_all_global_variables", key="all_variables")


def summarize_called_functions(full_code: str, called_functions: List[str], url: str = DEFAULT_OLLAMA_URL) -> str:
    prompt = f"""You are a deterministic Python code extractor.

    Full source code:
    {full_code}

    Relevant Functions:
    {json.dumps(called_functions)}

    Task:
    - Extract ONLY the function definitions whose names are in "Relevant function names"
    - Return them concatenated as plain Python code

    Hard rules:
    - Output ONLY Python code. No markdown. No backticks. No explanations. No comments.
    - Do NOT include any global variables, imports, or any other statements.
    - Include each function exactly once.
    - Preserve the original indentation and line breaks exactly.

    Output format constraint:
    - The first non-whitespace characters of your output MUST be 'def' or 'async def'.
    - If you cannot comply exactly, output ONLY this single word: ERROR
    """
    return _ollama_generate(prompt, url=url)


def topologically_sort_functions(called_functions_summary: str, url: str = DEFAULT_OLLAMA_URL) -> str:
    prompt = f"""You are a deterministic Python code extractor.

    Task:
    - You are given a set of Python function definitions:
    {called_functions_summary}

    - Sort these functions in topological order based on their dependencies:
        * Functions that do not call any other functions from this set should appear at the top.
        * Functions that call other functions should appear after the ones they call.
    - Keep the function definitions exactly as they are, preserve indentation and line breaks.

    Rules:
    - Output ONLY Python code. No markdown. No backticks. No explanations. No comments.
    - Do NOT include any functions that are not in the input.
    - Preserve indentation and line breaks.
    """
    return _ollama_generate(prompt, url=url)


def find_all_variable_dependencies(
    called_functions_summary: str, global_variables: List[str], url: str = DEFAULT_OLLAMA_URL
) -> List[str]:
    prompt = f"""You are a deterministic Python code extractor.

    Global Variables:
    {json.dumps(global_variables)}

    Full source code:
    {called_functions_summary}

    Task:
    - Look at every function in 'Sourcecode' and identify the variables that are being used, that are also in 'Global Variables'.

    Rules:
    - Output ONLY a JSON array of variable names, e.g. ["var_a", "var_b"]
    - Do NOT include the function names in the JSON array.
    - No explanations, no extra text.
    """
    raw = _ollama_generate(prompt, url=url)
    return _parse_json_array_of_strings(raw, "find_all_variable_dependencies")


def summarize_called_global_variables(
    full_code: str, called_global_variables: List[str], url: str = DEFAULT_OLLAMA_URL
) -> str:
    prompt = f"""You are a deterministic Python code extractor.

    Full source code:
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
    called_functions = find_called_functions_names(source_code, function_name, url=url)
    global_variables = find_all_global_variables(source_code, url=url)

    called_functions_summary = summarize_called_functions(source_code, called_functions, url=url)
    called_functions_summary_sorted = topologically_sort_functions(called_functions_summary, url=url)

    called_global_variables = find_all_variable_dependencies(called_functions_summary, global_variables, url=url)
    called_global_variables_summary = summarize_called_global_variables(source_code, called_global_variables, url=url)

    parts = []
    if called_global_variables_summary.strip():
        parts.append(called_global_variables_summary.strip())
    if called_functions_summary_sorted.strip():
        parts.append(called_functions_summary_sorted.strip())

    return "\n\n".join(parts)
