import argparse
import json
import sys
import os
from typing import Any, Callable, Dict, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONTEXT_DIR = os.path.join(BASE_DIR, "context_extraction")
ANALYSIS_DIR = os.path.join(BASE_DIR, "llm_analysis")

for p in (CONTEXT_DIR, ANALYSIS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--mode",
        required=True,
        help="ast | codellama:13b | gpt-5.2 | claude-sonnet-4-5",
    )
    p.add_argument("--analysis-model", required=True, help="codellama:13b | gpt-5.2 | claude-sonnet-4-5")
    p.add_argument("--function", required=True, help="Function name to analyze")
    p.add_argument("--file", required=True, help="Path to python file")
    p.add_argument(
        "--inputs-json",
        default="null",
        help="JSON object of parameter inputs from UI (or null).",
    )
    return p.parse_args()


# --- Lazy strategy loaders (avoid importing optional deps unless needed) ---

def _load_ast() -> Callable[[str, str], str]:
    from ast_context import create_context as create_context_ast
    return create_context_ast


def _load_codellama() -> Callable[[str, str], str]:
    from codellama_context import create_context as create_context_codellama
    return create_context_codellama


def _load_gpt() -> Callable[[str, str], str]:
    from gpt_context import create_context as create_context_gpt
    return create_context_gpt


def _load_claude() -> Callable[[str, str], str]:
    from claude_context import create_context as create_context_claude
    return create_context_claude


STRATEGIES: Dict[str, Callable[[], Callable[[str, str], str]]] = {
    "ast": _load_ast,
    "codellama:13b": _load_codellama,
    "gpt-5.2": _load_gpt,
    "claude-sonnet-4-5": _load_claude,
}


# --- Analysis loaders ---

def _load_codellama_analysis() -> Callable[[str, str, Optional[str]], str]:
    from codellama_analysis import analyze_termination as analyze
    return analyze

def _load_gpt_analysis() -> Callable[[str, str, Optional[str]], str]:
    from gpt_analysis import analyze_termination as analyze
    return analyze

def _load_claude_analysis() -> Callable[[str, str, Optional[str]], str]:
    from claude_analysis import analyze_termination as analyze
    return analyze


ANALYSIS_STRATEGIES: Dict[str, Callable[[], Callable[[str, str, Optional[str]], str]]] = {
    "gpt-5.2": _load_gpt_analysis,
    "codellama:13b": _load_codellama_analysis,
    "claude-sonnet-4-5": _load_claude_analysis,
}


def _format_inputs_summary(inputs_obj: Any) -> Tuple[Optional[str], bool]:
    """
    inputs_obj is what the webview sends as settings.inputs:
      {
        "x": null,
        "s": {"type":"String","value":"abc"},
        "n": {"type":"Integer","from":-10,"to":10},
        "flag": {"type":"Boolean","value":true}
      }

    Returns (summary_string_or_none, has_any_spec).
    """
    if inputs_obj is None:
        return None, False
    if not isinstance(inputs_obj, dict):
        return None, False

    lines = []
    has_any = False

    for name, spec in inputs_obj.items():
        if spec is None:
            continue
        if not isinstance(spec, dict):
            continue

        t = str(spec.get("type", "")).strip()
        if not t:
            continue

        has_any = True

        if t == "String":
            v = spec.get("value", None)
            if v is None:
                lines.append(f'String ({name}): <unspecified>')
            else:
                lines.append(f'String ({name}): "{v}"')

        elif t in ("Integer", "Float"):
            frm = spec.get("from", None)
            to = spec.get("to", None)

            # Keep it readable even if user didn't enter bounds
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
            # Unknown type, still include
            lines.append(f"{t} ({name}): <specified>")

    summary = "\n".join(lines).strip()
    return (summary if summary else None), has_any


def main() -> int:
    a = parse_args()

    try:
        with open(a.file, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Failed to read file: {e}"}))
        return 0

    mode = a.mode.strip()
    fn = a.function.strip()
    analysis_model = a.analysis_model.strip()

    # Parse inputs JSON (safe: logs to stderr, never stdout)
    try:
        inputs_obj = json.loads(a.inputs_json) if a.inputs_json not in ("", "null", "None") else None
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Failed to parse inputs-json: {e}"}))
        return 0

    # --- Context extraction ---
    loader = STRATEGIES.get(mode)
    if loader is None:
        print(json.dumps({"ok": False, "error": f"Unknown mode: {mode}"}))
        return 0

    try:
        ctx_handler = loader()
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Failed to load mode '{mode}': {e}"}))
        return 0

    try:
        context_str = ctx_handler(fn, source)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Context extraction failed: {e}"}))
        return 0

    # --- Inputs summary + log ---
    inputs_summary, has_any_spec = _format_inputs_summary(inputs_obj)

    # LOG (IMPORTANT): must go to stderr, not stdout, or JSON parsing breaks.
    if has_any_spec and inputs_summary:
        print("[termination-analysis] Inputs summary:\n" + inputs_summary, file=sys.stderr)
    else:
        print("[termination-analysis] No parameter specifications provided.", file=sys.stderr)

    # --- Analysis ---
    analysis_loader = ANALYSIS_STRATEGIES.get(analysis_model)
    if analysis_loader is None:
        print(json.dumps({"ok": False, "error": f"Analysis model not implemented: {analysis_model}"}))
        return 0

    try:
        analyze = analysis_loader()
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Failed to load analysis model '{analysis_model}': {e}"}))
        return 0

    try:
        analysis_text = analyze(fn, context_str, inputs_summary if has_any_spec else None)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Analysis failed: {e}"}))
        return 0

    # One JSON output to stdout for the extension to parse.
    print(
        json.dumps(
            {
                "ok": True,
                "context": context_str,
                "analysis": analysis_text,
                "meta": {
                    "mode": mode,
                    "analysis_model": analysis_model,
                    "function": fn,
                    "used_param_spec_prompt": bool(has_any_spec),
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
