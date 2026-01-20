import ast
from typing import Dict, List, Optional, Set, Tuple

class FunctionAnalyzer(ast.NodeVisitor):

    def __init__(self, tree: ast.AST):
        self.tree = tree
        self.global_vars = self._get_global_vars()
        self.function_defs = self._get_function_defs()

    def _get_global_vars(self) -> Dict[str, ast.AST]:
        global_variables: Dict[str, ast.AST] = {}

        for node in getattr(self.tree, "body", []):
            # normal assignment (e.g. x = 5 | can have multiple targets e.g. a = b = c = 5)
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        global_variables[target.id] = node

            # annotated assignment (x: int = 5 | exactly one target)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    global_variables[node.target.id] = node

        return global_variables

    # collect all FunctionDef / AsyncFunctionDef
    def _get_function_defs(self) -> Dict[str, ast.AST]:

        functions: Dict[str, ast.AST] = {}
        duplicates: Set[str] = set()

        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in functions:
                    duplicates.add(node.name)
                functions[node.name] = node

        if duplicates:
            raise ValueError(
                f"Duplicate function names found (must be unique): {sorted(duplicates)}"
            )

        return functions

    # finds all function & global variables called by fn
    def analyze_function(self, fn_name: str, visited: Optional[Set[str]] = None) -> Dict[str, Set[str]]:
        if visited is None:
            visited = set()
        if fn_name in visited:
            return {"functions": set(), "globals": set()}
        visited.add(fn_name)

        node = self.function_defs.get(fn_name)
        if node is None:
            return {"functions": set(), "globals": set()}

        local_called_functions: Set[str] = set()
        local_used_globals: Set[str] = set()

        for child in ast.walk(node):
            # function calls
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                called = child.func.id
                if called in self.function_defs:
                    local_called_functions.add(called)

            # usage of global variables
            if isinstance(child, ast.Name) and child.id in self.global_vars:
                local_used_globals.add(child.id)

        # recursively investigate further functional dependencies
        all_functions = set(local_called_functions)
        all_globals = set(local_used_globals)

        for called_fn in local_called_functions:
            deeper = self.analyze_function(called_fn, visited)
            all_functions.update(deeper["functions"])
            all_globals.update(deeper["globals"])

        return {"functions": all_functions, "globals": all_globals}

    def _node_source(self, source_code: str, node: ast.AST) -> str:
        seg = ast.get_source_segment(source_code, node)

        if seg is None:
            return ""
        return seg

    def get_source_for_function(self, fn_name: str, source_code: str) -> str:
        fn_node = self.function_defs.get(fn_name)
        if fn_node is None:
            return ""
        return self._node_source(source_code, fn_node)

    # creates a context string containing relevant global variables and relevant helper functions
    def create_context(self, fn_name: str, source_code: str) -> str:

        analysis = self.analyze_function(fn_name)
        relevant_functions = analysis["functions"]
        relevant_globals = analysis["globals"]

        context_parts: List[str] = []

        # global variables (sort as in code)
        sorted_globals = sorted(
            ((var, node) for var, node in self.global_vars.items() if var in relevant_globals),
            key=lambda x: getattr(x[1], "lineno", 10**9),
        )
        for _var, node in sorted_globals:
            seg = self._node_source(source_code, node)
            if seg.strip():
                context_parts.append(seg)

        # helper functions (sort by minimum dependencies)
        visited: Set[str] = set()
        ordered_functions: List[str] = []

        def dfs(fn: str):
            if fn in visited or fn == fn_name:
                return
            visited.add(fn)

            fn_node = self.function_defs.get(fn)
            if fn_node is None:
                return

            called: Set[str] = set()
            for child in ast.walk(fn_node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    called_fn = child.func.id
                    if called_fn in self.function_defs and called_fn != fn_name:
                        called.add(called_fn)

            for c in called:
                dfs(c)

            ordered_functions.append(fn)

        for fn in relevant_functions:
            dfs(fn)

        for fn in ordered_functions:
            fn_node = self.function_defs.get(fn)
            if fn_node:
                seg = self._node_source(source_code, fn_node)
                if seg.strip():
                    context_parts.append(seg)

        # 3) main function last (so the LLM sees dependencies first)
        main_src = self.get_source_for_function(fn_name, source_code)
        if main_src.strip():
            context_parts.append(main_src)

        return "\n\n".join(context_parts)


def create_context(function_name: str, source_code: str) -> str:
    """
    Public API used by orchestrator.
    """
    tree = ast.parse(source_code)
    analyzer = FunctionAnalyzer(tree)

    if function_name not in analyzer.function_defs:
        raise ValueError(f"Function '{function_name}' not found.")

    return analyzer.create_context(function_name, source_code)
