import asyncio
import sys
import os

# Ajoute la racine du projet (Nova3.0) au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.memory.symbolic_memory import symbolic_memory
from backend.memory.synthetic_memory import synthetic_memory
from backend.memory.vector_store import vector_store


def afficher_symbolic_memory():
    print("\n📚 Contenu de la mémoire symbolique:\n")
    graph = symbolic_memory.memory_graph

    if not graph["entities"]:
        print("Aucune entité en mémoire.")
    else:
        print("🧠 Entités :")
        for eid, entity in graph["entities"].items():
            print(f"- {entity['name']} ({entity['type']}) | ID: {eid}")
            if entity.get("attributes"):
                for key, value in entity["attributes"].items():
                    print(f"    - {key}: {value}")

    if not graph["relations"]:
        print("\n⚠️ Aucune relation enregistrée.")
    else:
        print("\n🔗 Relations :")
        for rel in graph["relations"]:
            source = graph["entities"].get(rel["source"], {}).get("name", rel["source"])
            target = graph["entities"].get(rel["target"], {}).get("name", rel["target"])
            print(f"- {source} --[{rel['relation']}]--> {target} (confiance: {rel['confidence']})")


async def tester_phrase_symbolique():
    phrase = input("\n📝 Entre une phrase à analyser :\n> ")
    update_stats = await symbolic_memory.update_graph_from_text(phrase)
    print("\n✅ Graphe mis à jour :")
    print(update_stats)


async def menu():
    while True:
        print("\n=== Menu Test Mémoire Symbolique ===")
        print("1. Voir le contenu de la mémoire symbolique")
        print("2. Tester une phrase (mise à jour du graphe)")
        print("3. Réinitialiser la mémoire symbolique")
        print("0. Quitter")
        choix = input("Ton choix ? ")

        if choix == "1":
            afficher_symbolic_memory()
        elif choix == "2":
            await tester_phrase_symbolique()
        elif choix == "3":
            symbolic_memory.memory_graph = {"entities": {}, "relations": []}
            symbolic_memory._save_graph()
            print("\n🧹 Mémoire symbolique réinitialisée.")
        elif choix == "0":
            print("👋 Fin du test.")
            break
        else:
            print("❌ Choix invalide. Réessaye.")


if __name__ == "__main__":
    asyncio.run(menu())
