import ast
import random
import sys


class StringObfuscator(ast.NodeTransformer):
    def __init__(self):
        self.pool = []
        self.runtime_key = random.randint(1, 255)

    # ─────────────────────────────
    # Encrypt
    # ─────────────────────────────
    def encrypt(self, data: bytes):
        key = random.randint(1, 255)
        encrypted = bytes((b ^ key ^ self.runtime_key) for b in data)
        index = len(self.pool)
        self.pool.append((list(encrypted), key))
        return index

    # ─────────────────────────────
    # Replace constants
    # ─────────────────────────────
    def visit_Constant(self, node):
        if isinstance(node.value, str):
            if node.value == "__main__":
                return node
            idx = self.encrypt(node.value.encode("utf-8"))
            return self.build_loader(idx)

        elif isinstance(node.value, bytes):
            idx = self.encrypt(node.value)
            return self.build_loader(idx, is_bytes=True)

        return node

    # ─────────────────────────────
    # Proper f-string rewrite
    # ─────────────────────────────
    def visit_JoinedStr(self, node):
        parts = []

        for v in node.values:
            if isinstance(v, ast.Constant):
                if v.value == "__main__":
                    parts.append(v)
                else:
                    idx = self.encrypt(v.value.encode("utf-8"))
                    parts.append(self.build_loader(idx))

            elif isinstance(v, ast.FormattedValue):
                value = v.value

                # Handle format spec correctly
                if v.format_spec and isinstance(v.format_spec, ast.JoinedStr):
                    spec_parts = []
                    for sp in v.format_spec.values:
                        if isinstance(sp, ast.Constant):
                            spec_parts.append(sp.value)
                    spec = "".join(spec_parts)

                    formatted = ast.Call(
                        func=ast.Name(id="format", ctx=ast.Load()),
                        args=[value, ast.Constant(value=spec)],
                        keywords=[]
                    )
                    parts.append(formatted)
                else:
                    parts.append(
                        ast.Call(
                            func=ast.Name(id="str", ctx=ast.Load()),
                            args=[value],
                            keywords=[]
                        )
                    )

        expr = parts[0]
        for p in parts[1:]:
            expr = ast.BinOp(left=expr, op=ast.Add(), right=p)

        return expr

    # ─────────────────────────────
    # Loader call
    # ─────────────────────────────
    def build_loader(self, idx, is_bytes=False):
        return ast.Call(
            func=ast.Name(id="_l", ctx=ast.Load()),
            args=[ast.Constant(value=idx),
                  ast.Constant(value=is_bytes)],
            keywords=[]
        )

    # ─────────────────────────────
    # Inject runtime
    # ─────────────────────────────
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


def obfuscate(input_file, output_file):
    with open(input_file, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    obf = StringObfuscator()
    tree = obf.visit(tree)
    tree = obf.inject_runtime(tree)
    ast.fix_missing_locations(tree)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(ast.unparse(tree))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python obfuscator.py input.py output.py")
        sys.exit(1)

    obfuscate(sys.argv[1], sys.argv[2])
