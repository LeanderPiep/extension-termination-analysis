import argparse
import json
import sys

from ast_context import create_context as create_context_ast


STRATEGIES = {
    # match dropdown values
    "ast": create_context_ast,
    # stubs for later
    "codellama:13b": None,
    "gpt-5.2": None,
    "claude-sonnet-4-5": None,
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", required=True, help="ast | codellama:13b | gpt-5.2 | claude-sonnet-4-5")
    p.add_argument("--function", required=True, help="Function name to analyze")
    p.add_argument("--file", required=True, help="Path to python file")
    return p.parse_args()


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

    if mode not in STRATEGIES:
        print(json.dumps({"ok": False, "error": f"Unknown mode: {mode}"}))
        return 0

    handler = STRATEGIES[mode]
    if handler is None:
        print(json.dumps({"ok": False, "error": f"Mode '{mode}' not implemented yet."}))
        return 0

    try:
        context_str = handler(fn, source)
        print(json.dumps({
            "ok": True,
            "context": context_str,
            "meta": {"mode": mode, "function": fn}
        }))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 0


if __name__ == "__main__":
    sys.exit(main())
