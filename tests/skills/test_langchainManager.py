# Test du processus complet de traitement de message
import asyncio

import sys, os

# Ajoute la racine du projet (Nova3.0) au PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

    
from backend.models.langchain_manager import langchain_manager



async def test_langchain():
    response = await langchain_manager.process_message(
        "Peux-tu me rappeler quand j'ai mon rendez-vous chez le médecin?",
        conversation_history=[],  # Vous pouvez ajouter des messages d'historique ici
        mode="chat"
    )
    print(response)

asyncio.run(test_langchain())