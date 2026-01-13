import ast
import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Tuple

TYPE_DONT = "Dont Specify"
TYPE_INT = "Integer"
TYPE_FLOAT = "Float"
TYPE_STRING = "String"

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

# get function parameters
def extract_param_type_defaults(fn: ast.AST) -> Dict[str, str]:
    a = fn.args
    params: List[ast.arg] = []
    params += list(getattr(a, "posonlyargs", []))
    params += list(a.args)
    params += list(a.kwonlyargs)

    out: Dict[str, str] = {}
    for p in params:
        out[p.arg] = _map_annotation_to_ui_type(p.annotation)
    return out

def _map_annotation_to_ui_type(ann: Optional[ast.AST]) -> str:
    if ann is None:
        return TYPE_DONT

    # Try to unparse; if that fails, fall back
    try:
        s = ast.unparse(ann)
    except Exception:
        return TYPE_DONT

    # Normalize a bit
    t = s.strip()

    # Handle quoted forward refs: "int"
    if (t.startswith("'") and t.endswith("'")) or (t.startswith('"') and t.endswith('"')):
        t = t[1:-1].strip()

    # Very conservative mapping: only obvious ones
    # Accept builtins and common typing wrappers
    # Examples: int, Optional[int], Union[int, None], Annotated[int, ...]
    if "int" == t or t.endswith("[int]") or "int," in t or t.endswith("(int)"):
        # this is too broad; better do structured parsing below
        pass

    # Better: check AST shape instead of string contains
    # We'll match: Name(id="int"/"float"/"str") and Subscript(base=Name("Optional"/"Annotated"/"Union"), ...)
    def base_name(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            # typing.Optional etc.
            return node.attr
        return None

    def is_named(node: ast.AST, name: str) -> bool:
        return base_name(node) == name

    def classify(node: ast.AST) -> str:
        # direct: int/float/str
        if is_named(node, "int"):
            return TYPE_INT
        if is_named(node, "float"):
            return TYPE_FLOAT
        if is_named(node, "str"):
            return TYPE_STRING

        # Optional[T], Annotated[T, ...], Union[T, None]
        if isinstance(node, ast.Subscript):
            bn = base_name(node.value)
            if bn in {"Optional", "Annotated"}:
                inner = node.slice
                # slice can be Tuple or single
                if isinstance(inner, ast.Tuple) and inner.elts:
                    return classify(inner.elts[0])
                return classify(inner)

            if bn == "Union":
                inner = node.slice
                if isinstance(inner, ast.Tuple):
                    # if any elt is int/float/str, pick that (still conservative)
                    mapped = [classify(e) for e in inner.elts]
                    for pref in (TYPE_INT, TYPE_FLOAT, TYPE_STRING):
                        if pref in mapped:
                            return pref
        return TYPE_DONT

    try:
        return classify(ann)
    except Exception:
        return TYPE_DONT


if __name__ == "__main__":
    sys.exit(main())


