# Test du processus complet de traitement de message
import asyncio
from models.langchain_manager import langchain_manager

async def test_langchain():
    response = await langchain_manager.process_message(
        "Peux-tu me rappeler quand j'ai mon rendez-vous chez le médecin?",
        conversation_history=[],  # Vous pouvez ajouter des messages d'historique ici
        mode="chat"
    )
    print(response)

asyncio.run(test_langchain())