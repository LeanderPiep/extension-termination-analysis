from __future__ import annotations

import json
import re
from urllib import request

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5-coder:14b"


def _sanitize_code_output(text: str) -> str:
    """
    Best-effort cleanup if the model returns fenced code blocks or extra whitespace.
    Removes ```python ... ``` or ``` ... ``` fences if they wrap the whole output.
    """
    if not text:
        return ""

    t = text.strip()

    # Remove opening fence like ```python or ``` (at start)
    t = re.sub(r"^\s*```(?:python)?\s*\n?", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\n?\s*```\s*$", "", t)

    return t.strip()


def _ollama_generate(prompt: str, model: str = DEFAULT_MODEL, url: str = DEFAULT_OLLAMA_URL) -> str:
    payload = {
        "model": model,
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


def create_context(
    function_name: str,
    source_code: str,
    model: str = DEFAULT_MODEL,
    url: str = DEFAULT_OLLAMA_URL,
) -> str:
    """
    Creates context using Qwen via Ollama.
    Returns Python code: relevant globals + relevant functions in topological order.
    Prompt is intentionally identical (same content) to gpt_cotnext.py.
    """
    prompt = f"""
    Full source code:
    {source_code}

    Target function:
    {function_name}

    Task:
    1. Identify ALL functions that are directly or indirectly called by the target function.
    2. Identify ALL global variables used by those functions.
    3. Extract ONLY:
    - the definitions of those global variables
    - the definitions of those functions
    - the definition of the target function itself
    4. Sort the extracted functions topologically:
    - callees first
    - callers after callees

    Rules:
    - Output valid Python code.
    - Do NOT include unused functions or globals.
    - Do NOT include comments, explanations, or markdown.
    - Preserve exact Python syntax and indentation.
    """

    full_prompt = (
        "You are a static program analysis assistant. "
        "You reason over Python source code precisely and deterministically.\n\n"
        + prompt
    )

    raw_text = _ollama_generate(full_prompt, model=model, url=url)
    return _sanitize_code_output(raw_text)
