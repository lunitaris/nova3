import ast
import os
import json
import networkx as nx

# Répertoire racine de ton code Python
ROOT_DIR = "backend"  # ← adapte si nécessaire

def build_call_graph(root_dir):
    G = nx.DiGraph()
    # Parcours récursif des fichiers .py
    for dirpath, _, files in os.walk(root_dir):
        for f in files:
            if not f.endswith('.py'):
                continue
            path = os.path.join(dirpath, f)
            try:
                with open(path, encoding='utf-8') as file:
                    source = file.read()
                tree = ast.parse(source, filename=path)

                # Collecte des définitions de fonctions
                funcs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

                # Parcours de tous les appels
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    try:
                        # Détection du callee (nom de la fonction appelée)
                        if isinstance(node.func, ast.Name):
                            callee = node.func.id
                        elif isinstance(node.func, ast.Attribute):
                            callee = node.func.attr
                        else:
                            # On ignore les autres types (Lambda, Subscript, etc.)
                            continue

                        # Détection du caller (fonction appelante)
                        caller_node = next((fn for fn in funcs if fn.lineno < node.lineno), None)
                        if caller_node:
                            caller = caller_node.name
                            # Ajout des nœuds et de l'arête
                            G.add_node(caller)
                            G.add_node(callee)
                            G.add_edge(caller, callee)
                    except Exception as e:
                        print(f"⚠️ Skip appel non lisible dans {path}: {e}")
            except Exception as e:
                print(f"❌ Erreur lors de l'analyse de {path}: {e}")
    return G

if __name__ == "__main__":
    G = build_call_graph(ROOT_DIR)
    # Utiliser 'links' pour compatibilité future de NetworkX
    data = nx.node_link_data(G, edges="links")
    with open("call_graph.json", "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2)
