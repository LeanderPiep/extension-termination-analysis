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

The Target function might either terminate for all inputs or diverges for at least one input.

Task:
Determine whether the target function terminates for all or diverges for atleast one input.
If you come to the conclusion that the function terminates for all inputs, then answer "Final verdict: T".
If you come to the conclusion that there exists atleast one input for which the function diverges, then answer "Final verdict: NT".

Instructions:
- Do not state the final verdict at the beginning.
- Analyze the control flow carefully: loops, recursion, and conditions.
- If termination depends on input conditions, make those conditions explicit and reason about them.

Output format:

1) Termination or non-termination argument
- Identify loops, recursion, and critical control-flow structures
- Mention variables influencing termination

2) Relevant conditions on inputs
- State conditions under which the reasoning holds

3) Final verdict

Target function: {function_name}

Python source code:
{context_code}
""".strip()


def _prompt_with_specs(function_name: str, context_code: str, inputs_summary: str) -> str:
    return f"""
    
Task:
Determine whether the target function terminates for th User-provided parameter specifications.
If you come to the conclusion that the function terminates, then answer "Final verdict: T".
If you come to the conclusion that the function diverges, then answer "Final verdict: NT".

Instructions:
- Do not state the final verdict at the beginning.
- Analyze control flow carefully: loops, recursion, and conditions.
- Use the parameter specifications explicitly in your reasoning.
- Treat the specifications as constraints on the input space.

Output format (plain text):

1) Key observations
- Identify loops, recursion, and critical control-flow structures
- Mention variables influencing termination

2) Relevant conditions on inputs 
- State conditions under which the reasoning holds and how they relate to the specifications

3) Final verdict

Target function: {function_name}

User-provided parameter specifications: {inputs_summary}

Python source code: {context_code}
""".strip()


def _counterexample_prompt(
    function_name: str,
    context_code: str,
) -> str:
    return f"""

The target function does not terminate for at least one input.

Task:
Provide a concrete input for which the function does not terminate.

Instructions:
- Explain the execution path step by step.
- Identify the loop, recursive cycle, or control-flow pattern that repeats forever.
- Make clear why execution never reaches a return statement or program end.
- Focus only on constructing and justifying a non-terminating input.

Output format:

Counterexample input:
concrete input

Why it does not terminate:
short step-by-step explanation

Target function: {function_name}

Python source code: {context_code}
""".strip()


def _run_openai_prompt(client: OpenAI, model: str, user_prompt: str) -> str:
    response = client.responses.create(
        model=model,
        temperature=0.0,
        input=[
            {
                "role": "system",
                "content": (
                    "You are an expert code analyzer specializing in Python program termination analysis. "
                    "You will be given a Python source code and a Target function."
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

    if inputs_summary:
        first_prompt = _prompt_with_specs(function_name, context_code, inputs_summary)
    else:
        first_prompt = _prompt_base(function_name,context_code)
    
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