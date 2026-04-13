from __future__ import annotations

import json
import re
from typing import Optional, Literal
from urllib import request


DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5-coder:14b"


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


def _run_qwen_prompt(prompt: str, model: str = DEFAULT_MODEL, url: str = DEFAULT_OLLAMA_URL) -> str:
    full_prompt = (
        "You are a rigorous static program analysis assistant. "
        "Be deterministic and do not invent code that is not present in the context.\n\n"
        + prompt
    )
    raw = _ollama_generate(full_prompt, model=model, url=url)
    return _sanitize_text(raw)


def analyze_termination(
    function_name: str,
    context_code: str,
    inputs_summary: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    url: str = DEFAULT_OLLAMA_URL,
) -> str:
    first_prompt = (
        _prompt_with_specs(function_name, context_code, inputs_summary)
        if inputs_summary
        else _prompt_base(function_name, context_code)
    )

    first_analysis = _run_qwen_prompt(first_prompt, model=model, url=url)
    verdict = _extract_verdict(first_analysis)

    if verdict == "NT":
        second_prompt = _counterexample_prompt(
            function_name=function_name,
            context_code=context_code,
        )
        counterexample = _run_qwen_prompt(second_prompt, model=model, url=url)

        return (
            first_analysis
            + "\n\n"
            + "Concrete non-termination example:\n"
            + counterexample
        )

    if verdict == "T":
        return first_analysis

    return (
        first_analysis
        + "\n\n"
        + "[Warning] Could not reliably extract final verdict. "
        + "Expected 'Final verdict: T' or 'Final verdict: NT'."
    )