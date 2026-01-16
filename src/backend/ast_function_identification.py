import ast
import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Tuple

TYPE_DONT = "Dont Specify"
TYPE_INT = "Integer"
TYPE_FLOAT = "Float"
TYPE_STRING = "String"
TYPE_BOOL = "Boolean"

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
    param_types = extract_param_type_defaults(fn)

    out = {
        "ok": True,
        "function": {
            "name": name,
            "start_line": sp[0] if sp else None,
            "end_line": sp[1] if sp else None,
            "params": param_types,
        },
    }
    print(json.dumps(out))
    return 0
    
# get file and line where user clicked
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

# get function parameters
def extract_param_type_defaults(fn: ast.AST) -> Dict[str, str]:
    return {
        p.arg: _map_annotation_to_ui_type(p.annotation)
        for p in fn.args.args
    }

def _map_annotation_to_ui_type(ann: Optional[ast.AST]) -> str:
    if ann is None:
        return TYPE_DONT

     # only accept builtins
    if isinstance(ann, ast.Name):
        if ann.id == "int":
            return TYPE_INT
        if ann.id == "float":
            return TYPE_FLOAT
        if ann.id == "str":
            return TYPE_STRING
        if ann.id == "bool":
            return TYPE_BOOL
        return TYPE_DONT

    return TYPE_DONT


if __name__ == "__main__":
    sys.exit(main())


