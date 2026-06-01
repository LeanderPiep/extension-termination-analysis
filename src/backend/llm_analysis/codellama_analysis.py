from __future__ import annotations

import json
import re
from urllib import request
from typing import Optional, Literal


DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "codellama:13b"


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

    with request.urlopen(req, timeout=180) as response:
        raw = json.loads(response.read()).get("response", "")

    return raw.replace("\\n", "\n").strip()


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


def _run_codellama_prompt(prompt: str, url: str = DEFAULT_OLLAMA_URL) -> str:
    full_prompt = (
        "You are an expert code analyzer specializing in Python program termination analysis. "
        "You will be given a Python source code and a Target function.\n\n"
        + prompt
    )
    raw = _ollama_generate(full_prompt, url=url)
    return _sanitize_text(raw)


def analyze_termination(
    function_name: str,
    context_code: str,
    inputs_summary: Optional[str] = None,
    url: str = DEFAULT_OLLAMA_URL,
) -> str:
    
    if inputs_summary:
        first_prompt = _prompt_with_specs(function_name, context_code, inputs_summary)
    else:
        first_prompt = _prompt_base(function_name,context_code)

    first_analysis = _run_codellama_prompt(first_prompt, url=url)
    verdict = _extract_verdict(first_analysis)

    if verdict == "NT":
        second_prompt = _counterexample_prompt(
            function_name=function_name,
            context_code=context_code,
        )
        counterexample = _run_codellama_prompt(second_prompt, url=url)

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