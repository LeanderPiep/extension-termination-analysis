from __future__ import annotations

import re
from typing import Optional

try:
    from anthropic import Anthropic
except ImportError as e:
    raise ImportError(
        "Missing dependency 'anthropic'. Install with: pip install anthropic"
    ) from e


DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def _sanitize_text(text: str) -> str:
    """
    Best-effort cleanup if Claude returns fenced code blocks or extra whitespace.
    """
    if not text:
        return ""

    t = text.strip()

    # Remove ```text ... ``` or ``` ... ```
    t = re.sub(r"^```(?:text)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*```$", "", t)

    return t.strip()


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
) -> str:
    """
    Termination analysis using Claude (Anthropic Messages API).
    If inputs_summary is provided (and non-empty), we use the prompt variant that includes it.
    """
    client = Anthropic()

    user_prompt = (
        _prompt_with_specs(function_name, context_code, inputs_summary)
        if inputs_summary
        else _prompt_base(function_name, context_code)
    )

    message = client.messages.create(
        model=model,
        max_tokens=8000,
        temperature=0.0,
        system=(
            "You are a rigorous static program analysis assistant. "
            "Be deterministic and do not invent code that is not present in the provided context."
        ),
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Concatenate text blocks
    parts = []
    for block in getattr(message, "content", []) or []:
        txt = getattr(block, "text", None)
        if isinstance(txt, str):
            parts.append(txt)

    raw_text = "\n".join(parts).strip()
    return _sanitize_text(raw_text)
