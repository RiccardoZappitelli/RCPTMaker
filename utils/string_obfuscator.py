import ast
import random
import sys

class StringObfuscator(ast.NodeTransformer):
    def __init__(self, obfuscate_docstrings=False, debug=False):
        self.pool = []
        self.runtime_key = random.randint(1, 255)
        self.obfuscate_docstrings = obfuscate_docstrings
        self.debug = debug

    def encrypt(self, data: bytes):
        key = random.randint(1, 255)
        encrypted = bytes((b ^ key ^ self.runtime_key) for b in data)
        idx = len(self.pool)
        self.pool.append((list(encrypted), key))
        return idx

    def is_docstring_node(self, node):
        """
        Return True if node is a docstring (Constant or JoinedStr),
        either plain or f-string, at module/function/class level.
        """
        parent = getattr(node, "parent", None)
        if parent is None:
            return False

        # If the string is wrapped in an Expr, unwrap once
        if isinstance(parent, ast.Expr):
            grandparent = getattr(parent, "parent", None)
            if grandparent is None:
                return False
            # the string must be the first statement of the grandparent body
            return grandparent.body and grandparent.body[0] is parent
        else:
            return isinstance(parent, (ast.Module, ast.FunctionDef, ast.ClassDef)) and parent.body and parent.body[0] is node

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            parent_type = type(getattr(node, 'parent', None)).__name__
            is_doc = self.is_docstring_node(node)
            if self.debug:
                print(f"[DEBUG] Constant string: {node.value!r}, parent: {parent_type}, is_docstring: {is_doc}")

            if node.value == "__main__":
                return node
            if not self.obfuscate_docstrings and is_doc:
                if self.debug:
                    print("[DEBUG] Skipping docstring Constant")
                return node
            idx = self.encrypt(node.value.encode("utf-8"))
            if self.debug:
                print(f"[DEBUG] Obfuscating Constant -> pool index {idx}")
            return self.build_loader(idx)
        elif isinstance(node.value, bytes):
            idx = self.encrypt(node.value)
            if self.debug:
                print(f"[DEBUG] Obfuscating bytes -> pool index {idx}")
            return self.build_loader(idx, is_bytes=True)
        return node

    def visit_JoinedStr(self, node):
        parent_type = type(getattr(node, 'parent', None)).__name__
        is_doc = self.is_docstring_node(node)
        if self.debug:
            print(f"[DEBUG] JoinedStr f-string, parent: {parent_type}, is_docstring: {is_doc}")

        if not self.obfuscate_docstrings and is_doc:
            if self.debug:
                print("[DEBUG] Skipping docstring JoinedStr")
            return node

        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                if v.value == "__main__":
                    parts.append(v)
                else:
                    idx = self.encrypt(v.value.encode("utf-8"))
                    if self.debug:
                        print(f"[DEBUG] Obfuscating f-string part Constant -> pool index {idx}")
                    parts.append(self.build_loader(idx))
            elif isinstance(v, ast.FormattedValue):
                parts.append(ast.Call(func=ast.Name(id="str", ctx=ast.Load()), args=[v.value], keywords=[]))

        expr = parts[0]
        for p in parts[1:]:
            expr = ast.BinOp(left=expr, op=ast.Add(), right=p)
        return expr

    def build_loader(self, idx, is_bytes=False):
        return ast.Call(
            func=ast.Name(id="_l", ctx=ast.Load()),
            args=[ast.Constant(value=idx), ast.Constant(value=is_bytes)],
            keywords=[]
        )

    def inject_runtime(self, tree):
        runtime_code = f"""
__K = {self.runtime_key}
__P = {self.pool}

def _l(i, is_bytes=False):
    data, k = __P[i]
    out = bytearray()
    for b in data:
        out.append(b ^ k ^ __K)
    if is_bytes:
        return bytes(out)
    return out.decode("utf-8")
"""
        runtime_ast = ast.parse(runtime_code)
        tree.body = runtime_ast.body + tree.body
        return tree

def obfuscate(input_file, output_file, obfuscate_docstrings=False, debug=False):
    with open(input_file, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

    obf = StringObfuscator(obfuscate_docstrings=obfuscate_docstrings, debug=debug)
    tree = obf.visit(tree)
    tree = obf.inject_runtime(tree)
    ast.fix_missing_locations(tree)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(ast.unparse(tree))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python obfuscator.py input.py output.py [--docstrings] [--debug]")
        sys.exit(1)
    flag_docstrings = '--docstrings' in sys.argv
    flag_debug = '--debug' in sys.argv
    obfuscate(sys.argv[1], sys.argv[2], obfuscate_docstrings=flag_docstrings, debug=flag_debug)
