from __future__ import annotations

import re

try:
    from anthropic import Anthropic
except ImportError as e:
    raise ImportError(
        "Missing dependency 'anthropic'. Install with: pip install anthropic"
    ) from e


DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def _sanitize_code_output(text: str) -> str:
    """
    Best-effort cleanup if Claude returns fenced code blocks.
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
    Creates context using Claude (Anthropic Messages API).
    Returns Python code: relevant globals + relevant functions in topological order.
    """
    client = Anthropic()

    message = client.messages.create(
        model=model,
        max_tokens=20000,
        temperature=0.0,
        system=(
            "You are a static program analysis assistant. "
            "You reason over Python source code precisely and deterministically."
        ),
        messages=[
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
- Output ONLY valid Python code
- Do NOT include ```python blocks
- Do NOT include unused functions or globals.
- Do NOT include comments, explanations, or markdown.
- Preserve exact Python syntax and indentation.
""",
            }
        ],
    )

    # Typical: message.content is a list of content blocks (text blocks etc.)
    # We'll concatenate all text blocks to be safe.
    parts = []
    for block in getattr(message, "content", []) or []:
        txt = getattr(block, "text", None)
        if isinstance(txt, str):
            parts.append(txt)

    raw_text = "\n".join(parts).strip()
    return _sanitize_code_output(raw_text)
