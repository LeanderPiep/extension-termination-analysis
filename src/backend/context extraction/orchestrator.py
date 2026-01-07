import argparse
import json
import sys
from typing import Callable, Dict


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--mode",
        required=True,
        help="ast | codellama:13b | gpt-5.2 | claude-sonnet-4-5",
    )
    p.add_argument("--function", required=True, help="Function name to analyze")
    p.add_argument("--file", required=True, help="Path to python file")
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
    # must match dropdown values exactly
    "ast": _load_ast,
    "codellama:13b": _load_codellama,
    "gpt-5.2": _load_gpt,
    "claude-sonnet-4-5": _load_claude,
}


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

    loader = STRATEGIES.get(mode)
    if loader is None:
        print(json.dumps({"ok": False, "error": f"Unknown mode: {mode}"}))
        return 0

    try:
        handler = loader()  # import happens here (only for the selected mode)
    except Exception as e:
        # This will catch missing openai/anthropic deps, missing API keys, etc.
        print(json.dumps({"ok": False, "error": f"Failed to load mode '{mode}': {e}"}))
        return 0

    try:
        context_str = handler(fn, source)
        print(
            json.dumps(
                {
                    "ok": True,
                    "context": context_str,
                    "meta": {"mode": mode, "function": fn},
                }
            )
        )
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 0


if __name__ == "__main__":
    sys.exit(main())
