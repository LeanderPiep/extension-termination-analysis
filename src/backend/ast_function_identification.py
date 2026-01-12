import ast
import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Tuple


def main():
    a = parse_args()
    source = get_source(a.file)

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        out = {"ok": False, "error": f"SyntaxError: {e.msg} at line {e.lineno}"}
        print(json.dumps(out))
        return 0

    fn = find_enclosing_function(tree, a.line)
    if fn is None:
        print(json.dumps({"ok": True, "function": None}))
        return 0

    name = fn.name  
    sp = node_span(fn)
    params = extract_params(fn)

    out = {
        "ok": True,
        "function": {
            "name": name,
            "start_line": sp[0] if sp else None,
            "end_line": sp[1] if sp else None,
            "params": params,
        },
    }
    print(json.dumps(out))
    return 0
    
# G´get file and line where use clicked
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--file", required=True)
    p.add_argument("--line", type=int, required=True, help="1-based line")
    return p.parse_args()

# get content of file
def get_source(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
    
# find function
def find_enclosing_function(tree: ast.AST, line: int) -> Optional[ast.AST]:
    candidates: List[ast.AST] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sp = node_span(node)
            if sp and inside_span(line, sp):
                candidates.append(node)

    if not candidates:
        return None

    candidates.sort(key=span_len)
    return candidates[0]

# get line-range of function
def node_span(node: ast.AST) -> Optional[Tuple[int, int]]:
    lineno = getattr(node, "lineno", None)
    end_lineno = getattr(node, "end_lineno", None)
    if lineno is None or end_lineno is None:
        return None
    return (lineno, end_lineno)

# check if line is in line-range
def inside_span(line: int, span: Tuple[int, int]) -> bool:
    return span[0] <= line <= span[1]

# get length of range
def span_len(n: ast.AST) -> int:
        sp = node_span(n)
        assert sp is not None
        return sp[1] - sp[0]


def format_arg(arg: ast.arg) -> Dict[str, Any]:
    return {
        "name": arg.arg,
        "annotation": ast.unparse(arg.annotation) if getattr(arg, "annotation", None) is not None else None,
    }

# get function parameters
def extract_params(fn: ast.AST) -> Dict[str, Any]:
    args = fn.args 

    def unparse_or_none(x):
        return ast.unparse(x) if x is not None else None

    posonly = [format_arg(a) for a in getattr(args, "posonlyargs", [])]
    normal = [format_arg(a) for a in args.args]
    kwonly = [format_arg(a) for a in args.kwonlyargs]

    vararg = format_arg(args.vararg) if args.vararg is not None else None
    kwarg = format_arg(args.kwarg) if args.kwarg is not None else None

    all_pos = posonly + normal
    defaults = [unparse_or_none(d) for d in args.defaults]
    defaults_map: Dict[str, Optional[str]] = {a["name"]: None for a in all_pos}
    if defaults:
        for a, d in zip(all_pos[-len(defaults):], defaults):
            defaults_map[a["name"]] = d

    kw_defaults = [unparse_or_none(d) for d in args.kw_defaults]
    kw_defaults_map: Dict[str, Optional[str]] = {a["name"]: None for a in kwonly}
    for a, d in zip(kwonly, kw_defaults):
        kw_defaults_map[a["name"]] = d

    return {
        "posonly": posonly,
        "args": normal,
        "vararg": vararg,
        "kwonly": kwonly,
        "kwarg": kwarg,
        "defaults": defaults_map,
        "kw_defaults": kw_defaults_map,
    }

if __name__ == "__main__":
    sys.exit(main())


