import argparse
import json
import sys
import os
from typing import Any, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONTEXT_DIR = os.path.join(BASE_DIR, "context_extraction")
ANALYSIS_DIR = os.path.join(BASE_DIR, "llm_analysis")

for p in (CONTEXT_DIR, ANALYSIS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

def main() -> int:
    a = parse_args()

    try:
        with open(a.file, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Failed to read file: {e}"}))
        return 0

    fn = a.function.strip()
    context_setting = a.context_backend.strip()
    analysis_setting = a.analysis_backend.strip()

    # parse inputs
    try:
        inputs_obj = json.loads(a.inputs_json) if a.inputs_json not in ("", "null", "None") else None
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Failed to parse inputs-json: {e}"}))
        return 0

    # context setting 
    try:
        if context_setting == "ast":
            from ast_context import create_context as ctx_handler
        elif context_setting == "codellama:13b":
            from codellama_context import create_context as ctx_handler
        elif context_setting == "gpt-5.2":
            from gpt_context import create_context as ctx_handler
        elif context_setting == "claude-sonnet-4-5":
            from claude_context import create_context as ctx_handler
        else:
            print(json.dumps({"ok": False, "error": f"Unknown context backend: {context_setting}"}))
            return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Failed to import context backend '{context_setting}': {e}"}))
        return 0

    try:
        context_str = ctx_handler(fn, source)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Context extraction failed: {e}"}))
        return 0

    # inputs summary
    inputs_summary, has_any_spec = _format_inputs_summary(inputs_obj)

    # log parameters
    if has_any_spec and inputs_summary:
        print("[termination-analysis] Inputs summary:\n" + inputs_summary, file=sys.stderr)
    else:
        print("[termination-analysis] No parameter specifications provided.", file=sys.stderr)

    # analysis setting
    try:
        if analysis_setting == "gpt-5.2":
            from gpt_analysis import analyze_termination as analyze
        elif analysis_setting == "codellama:13b":
            from codellama_analysis import analyze_termination as analyze
        elif analysis_setting == "claude-sonnet-4-5":
            from claude_analysis import analyze_termination as analyze
        else:
            print(json.dumps({"ok": False, "error": f"Analysis backend not implemented: {analysis_setting}"}))
            return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Failed to import analysis backend '{analysis_setting}': {e}"}))
        return 0

    try:
        analysis_text = analyze(fn, context_str, inputs_summary if has_any_spec else None)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Analysis failed: {e}"}))
        return 0

    print(
        json.dumps(
            {
                "ok": True,
                "context": context_str,
                "analysis": analysis_text,
                "meta": {
                    "context_backend": context_setting,
                    "analysis_backend": analysis_setting,
                    "function": fn,
                    "used_param_spec_prompt": bool(has_any_spec),
                },
            }
        )
    )
    return 0


# get settings for context extraction and analysis
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--context-backend", required=True)
    p.add_argument("--analysis-backend", required=True)
    p.add_argument("--function", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--inputs-json", default="null")
    return p.parse_args()


def _format_inputs_summary(inputs_obj: Any) -> Tuple[Optional[str], bool]:

    if inputs_obj is None:
        return None, False
    if not isinstance(inputs_obj, dict):
        return None, False

    lines = []
    has_any = False

    for name, spec in inputs_obj.items():
        if spec is None or not isinstance(spec, dict):
            continue

        t = str(spec.get("type", "")).strip()
        if not t:
            continue

        has_any = True

        if t == "String":
            v = spec.get("value", None)
            if v is None:
                lines.append(f"String ({name}): <unspecified>")
            else:
                lines.append(f'String ({name}): "{v}"')

        elif t in ("Integer", "Float"):
            frm = spec.get("from", None)
            to = spec.get("to", None)

            if frm is None and to is None:
                lines.append(f"{t} ({name}): <unspecified range>")
            elif frm is None:
                lines.append(f"{t} ({name}): up to {to}")
            elif to is None:
                lines.append(f"{t} ({name}): from {frm}")
            else:
                lines.append(f"{t} ({name}): from {frm} to {to}")

        elif t == "Boolean":
            v = spec.get("value", None)
            if v is None:
                lines.append(f"Boolean ({name}): <unspecified>")
            else:
                lines.append(f"Boolean ({name}): {bool(v)}")

        else:
            lines.append(f"{t} ({name}): <specified>")

    summary = "\n".join(lines).strip()
    return (summary if summary else None), has_any


if __name__ == "__main__":
    sys.exit(main())
