from __future__ import annotations

import json
import re
from typing import Optional
from urllib import request


DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5-coder:14b"


def _sanitize_text(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    # remove fenced code blocks if model wraps output
    t = re.sub(r"^```(?:text)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*```$", "", t)
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


def _prompt_base(function_name: str, context_code: str) -> str:
    return f"""
You are a termination analysis assistant for Python.

Given this extracted context (relevant code only):
{context_code}

Target function: {function_name}

Task:
Analyze whether the target function terminates for all inputs.

Requirements:
- If you believe it always terminates, explain why (high-level proof idea).
- If you believe it may not terminate, provide a concrete non-terminating execution scenario (e.g., a loop/recursion that can run forever) and explain conditions.
- If unsure, say what information is missing and what would be needed.

Output format (plain text):
1) Verdict: Terminates | May not terminate | Unclear
2) Reasoning (structured, concise)
3) If May not terminate: one concrete example input / path
""".strip()


def _prompt_with_specs(function_name: str, context_code: str, inputs_summary: str) -> str:
    return f"""
You are a termination analysis assistant for Python.

Given this extracted context (relevant code only):
{context_code}

Target function: {function_name}

User-provided parameter specifications:
{inputs_summary}

Task:
Analyze termination, taking the parameter specifications into account.
- If specs constrain inputs, analyze termination under those constraints.
- If multiple parameters are specified, analyze the combined constraint.
- If a parameter is specified without a concrete value/range, treat it as "type is known" but value is unconstrained.

Output format (plain text):
1) Verdict (under the given specs): Terminates | May not terminate | Unclear
2) Reasoning (structured, concise)
3) If May not terminate: one concrete example input within the specs (if possible)
""".strip()


def analyze_termination(
    function_name: str,
    context_code: str,
    inputs_summary: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    url: str = DEFAULT_OLLAMA_URL,
) -> str:
    user_prompt = (
        _prompt_with_specs(function_name, context_code, inputs_summary)
        if inputs_summary
        else _prompt_base(function_name, context_code)
    )

    # Equivalent to GPT's system message: inline in a single prompt for Ollama.
    full_prompt = (
        "You are a rigorous static program analysis assistant. "
        "Be deterministic and do not invent code that is not present in the context.\n\n"
        + user_prompt
    )

    raw = _ollama_generate(full_prompt, model=model, url=url)
    return _sanitize_text(raw)
