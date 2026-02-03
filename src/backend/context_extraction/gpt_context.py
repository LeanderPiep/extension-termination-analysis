from __future__ import annotations

import re

try:
    from openai import OpenAI
except ImportError as e:
    raise ImportError(
        "Missing dependency 'openai'. Install with: pip install openai"
    ) from e


DEFAULT_MODEL = "gpt-5.2"

def _sanitize_code_output(text: str) -> str:
    """
    Best-effort cleanup if the model returns fenced code blocks or extra whitespace.
    """
    if not text:
        return ""

    t = text.strip()

    # Remove ```python ... ``` or ``` ... ```
    t = re.sub(r"^```(?:python)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*```$", "", t)

    return t.strip()


def create_context(function_name: str, source_code: str, model: str = DEFAULT_MODEL) -> str:
    """
    Creates context using GPT (OpenAI Responses API).
    Returns Python code: relevant globals + relevant functions in topological order.
    """
    client = OpenAI()

    response = client.responses.create(
        model=model,
        temperature=0.0,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a static program analysis assistant. "
                    "You reason over Python source code precisely and deterministically."
                ),
            },
            {
                "role": "user",
                "content": f"""
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
""",
            },
        ],
    )

    # Official SDK convenience property that aggregates text
    raw_text = getattr(response, "output_text", "") or ""
    return _sanitize_code_output(raw_text)
