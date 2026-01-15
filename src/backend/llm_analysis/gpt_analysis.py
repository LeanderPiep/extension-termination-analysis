from __future__ import annotations

import re
from typing import Optional

try:
    from openai import OpenAI
except ImportError as e:
    raise ImportError(
        "Missing dependency 'openai'. Install with: pip install openai"
    ) from e


DEFAULT_MODEL = "gpt-5.2"


def _sanitize_text(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    # remove fenced code blocks if model wraps output
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


def analyze_termination(function_name: str, context_code: str, inputs_summary: Optional[str] = None, model: str = DEFAULT_MODEL) -> str:
    client = OpenAI()

    user_prompt = (
        _prompt_with_specs(function_name, context_code, inputs_summary)
        if inputs_summary
        else _prompt_base(function_name, context_code)
    )

    response = client.responses.create(
        model=model,
        temperature=0.0,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a rigorous static program analysis assistant. "
                    "Be deterministic and do not invent code that is not present in the context."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = getattr(response, "output_text", "") or ""
    return _sanitize_text(raw)
