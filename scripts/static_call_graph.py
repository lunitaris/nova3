# scripts/static_call_graph.py
import ast, os, json
import networkx as nx

ROOT_DIR = "Nova3.0"  # ← adapte au nom de ton dossier racine

def build_call_graph(root_dir):
    G = nx.DiGraph()
    for dirpath, _, files in os.walk(root_dir):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(dirpath, f)
                try:
                    with open(path, encoding='utf-8') as file:
                        tree = ast.parse(file.read(), filename=path)
                        funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                                caller = next((fn for fn in funcs.values() if fn.lineno < node.lineno), None)
                                callee = node.func.id
                                if caller and callee in funcs:
                                    G.add_edge(caller.name, callee)
                except Exception as e:
                    print(f"Erreur sur {path}: {e}")
    return G

if __name__ == "__main__":
    G = build_call_graph(ROOT_DIR)
    data = nx.node_link_data(G)
    with open("call_graph.json", "w") as f:
        json.dump(data, f, indent=2)
