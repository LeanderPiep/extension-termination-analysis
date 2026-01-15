import json
from urllib import request
from typing import Optional


DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "codellama:13b"


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
    return f"""You are a termination analysis assistant for Python.

Given this extracted context (relevant code only):
{context_code}

Target function: {function_name}

Task:
Analyze whether the target function terminates for all inputs.

Requirements:
- If you believe it always terminates, explain why (high-level proof idea).
- If you believe it may not terminate, provide a concrete non-terminating execution scenario and explain conditions.
- If unsure, say what information is missing and what would be needed.

Output format (plain text):
1) Verdict: Terminates | May not terminate | Unclear
2) Reasoning (structured, concise)
3) If May not terminate: one concrete example input / path

Rules:
- Output ONLY the text described above.
- No markdown, no code fences.
""".strip()


def _prompt_with_specs(function_name: str, context_code: str, inputs_summary: str) -> str:
    return f"""You are a termination analysis assistant for Python.

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

Rules:
- Output ONLY the text described above.
- No markdown, no code fences.
""".strip()


def analyze_termination(
    function_name: str,
    context_code: str,
    inputs_summary: Optional[str] = None,
    url: str = DEFAULT_OLLAMA_URL,
) -> str:
    prompt = (
        _prompt_with_specs(function_name, context_code, inputs_summary)
        if inputs_summary
        else _prompt_base(function_name, context_code)
    )
    return _ollama_generate(prompt, url=url)
