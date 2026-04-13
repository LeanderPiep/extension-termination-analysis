from __future__ import annotations

import re
from typing import Optional, Literal

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
    t = re.sub(r"^```(?:text)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _extract_verdict(text: str) -> Literal["T", "NT", "UNKNOWN"]:
    if not text:
        return "UNKNOWN"

    m = re.search(r"Final verdict:\s*(T|NT)\b", text, flags=re.IGNORECASE)
    if not m:
        return "UNKNOWN"

    verdict = m.group(1).upper()
    if verdict == "T":
        return "T"
    if verdict == "NT":
        return "NT"
    return "UNKNOWN"


def _prompt_base(function_name: str, context_code: str) -> str:
    return f"""
You are a termination analysis assistant for Python specialized in termination analysis.

Given the following source code:
{context_code}

Target function: {function_name}

Task:
Determine whether the target function terminates for all possible inputs.

Definitions:
- "Terminates (T)" means: for every possible input, the function eventually stops.
- "Does not terminate (NT)" means: there exists at least one input for which the function does not terminate.

Instructions:
- Do not state the final verdict at the beginning.
- Analyze control flow carefully: loops, recursion, and conditions.
- If termination depends on input conditions, make those conditions explicit and reason about them.
- Base your reasoning only on the given code. Do not assume behavior that is not present.
- Be precise and avoid vague statements.

Output format (plain text):

1) Key observations
- Identify loops, recursion, and critical control-flow structures
- Mention variables influencing termination

2) Termination or non-termination argument
- Either construct a proof of termination (e.g., decreasing measure)
- Or explain why such a proof fails and where infinite behavior can occur

3) Relevant conditions on inputs (if any)
- State conditions under which the reasoning holds

4) Final verdict: T | NT
""".strip()


def _prompt_with_specs(function_name: str, context_code: str, inputs_summary: str) -> str:
    return f"""
You are a termination analysis assistant for Python specialized in termination analysis.

Given the following source code:
{context_code}

Target function: {function_name}

User-provided parameter specifications:
{inputs_summary}

Task:
Determine whether the target function terminates for all inputs that satisfy the given parameter specifications.

Definitions:
- "Terminates (T)" means: for every input satisfying the specifications, the function eventually stops.
- "Does not terminate (NT)" means: there exists at least one input satisfying the specifications for which the function does not terminate.

Instructions:
- Do not state the final verdict at the beginning.
- Analyze control flow carefully: loops, recursion, and conditions.
- Use the parameter specifications explicitly in your reasoning.
- Treat the specifications as constraints on the input space.
- If termination depends on input conditions, relate them explicitly to the given specifications.
- Base your reasoning only on the given code. Do not assume behavior that is not present.
- Be precise and avoid vague statements.

Output format (plain text):

1) Key observations
- Identify loops, recursion, and critical control-flow structures
- Mention variables influencing termination

2) Termination or non-termination argument
- Either construct a proof of termination for all inputs within the specifications
- Or explain why such a proof fails and where infinite behavior can occur within the specifications

3) Relevant conditions on inputs (if any)
- State conditions under which the reasoning holds and how they relate to the specifications

4) Final verdict: T | NT
""".strip()


def _counterexample_prompt(
    function_name: str,
    context_code: str,
) -> str:
    return f"""
You are a termination analysis assistant for Python specialized in termination analysis.

Given the following source code:
{context_code}

Target function: {function_name}

Fact:
The target function does not terminate for at least one input.

Task:
Provide a concrete input for which the function does not terminate.

Instructions:
- Use only information that is justified by the given code.
- Explain the execution path step by step.
- Identify the loop, recursive cycle, or control-flow pattern that repeats forever.
- Make clear why execution never reaches a return statement or program end.
- Focus only on constructing and justifying a non-terminating input.

Output format (plain text):

Counterexample input:
concrete input

Why it does not terminate:
short step-by-step explanation
""".strip()


def _run_openai_prompt(client: OpenAI, model: str, user_prompt: str) -> str:
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


def analyze_termination(
    function_name: str,
    context_code: str,
    inputs_summary: Optional[str] = None,
    model: str = DEFAULT_MODEL,
) -> str:
    client = OpenAI()

    first_prompt = (
        _prompt_with_specs(function_name, context_code, inputs_summary)
        if inputs_summary
        else _prompt_base(function_name, context_code)
    )

    first_analysis = _run_openai_prompt(client, model, first_prompt)
    verdict = _extract_verdict(first_analysis)

    if verdict == "NT":
        second_prompt = _counterexample_prompt(
            function_name=function_name,
            context_code=context_code,
        )
        counterexample = _run_openai_prompt(client, model, second_prompt)

        return (
            first_analysis
            + "\n\n"
            + "Concrete non-termination example:\n"
            + counterexample
        )

    if verdict == "T":
        return first_analysis

    # Fallback: falls das Modell das Format verletzt
    return (
        first_analysis
        + "\n\n"
        + "[Warning] Could not reliably extract final verdict. "
        + "Expected 'Final verdict: T' or 'Final verdict: NT'."
    )