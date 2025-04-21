
"""
Gestionnaire LangChain pour l'assistant IA.
Orchestre les chaînes de prompts et les mémoires pour les conversations.
"""
import os
import logging
from typing import Dict, Any, List, Optional, Union
import asyncio

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.models.model_manager import model_manager
from backend.models.skills.manager import skills_manager
from backend.config import config

from backend.utils.profiler import profile
from backend.utils.startup_log import add_startup_event





logger = logging.getLogger(__name__)

class LangChainManager:
    """
    Gestionnaire des chaînes LangChain, intégrant les différents types de mémoire
    et permettant des conversations contextuelles avancées.
    """
    
    def __init__(self):
        """Initialise le gestionnaire de chaînes LangChain."""
        self.system_prompt = """Tu es une intelligence artificielle locale appelée Nova, conçue pour assister Maël dans son quotidien.

Voici ce que tu sais sur Maël, ton utilisateur :
{context}

Voici tes instructions :
- Réponds directement à ce qu’on te demande, sans reformuler ce que Maël a dit.
- Ne redis pas ce que tu sais déjà, sauf si on te le demande.
- Sois concise, pertinente et naturelle, comme une IA vocale intelligente.
- Si tu ne sais pas, dis-le simplement, sans inventer.
- Tu peux te baser sur le contexte symbolique pour enrichir ta réponse intelligemment.
"""
        self._init_memory_chains()
    
    def _init_memory_chains(self):
        """Initialise les chaînes de mémoire."""
        # logger.info("Initialisation des chaînes de mémoire")  ## DEBUG
        add_startup_event({"icon": "🧠", "label": "LangChain", "message": "chaînes conversationnelles prêtes"})
    

    def _format_conversation_history(self, messages: List[Dict[str, Any]]) -> List[Union[HumanMessage, AIMessage]]:
        """
        Formate l'historique de conversation pour LangChain.
        
        Args:
            messages: Liste des messages de la conversation
            
        Returns:
            Liste formatée de messages LangChain
        """
        formatted_messages = []
        
        for msg in messages:
            if msg["role"] == "user":
                formatted_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                formatted_messages.append(AIMessage(content=msg["content"]))
        
        return formatted_messages


    async def process_message( self, message: str, conversation_history: List[Dict[str, Any]], websocket=None, mode: str = "chat", additional_context: str = "") -> str:
        """
        Traite un message utilisateur et génère une réponse avec LangChain.
        
        Args:
            message: Le message ou la requête de l'utilisateur
            conversation_history: Historique récent de la conversation
            websocket: WebSocket optionnel pour le streaming
            mode: Mode de conversation ('chat' ou 'voice')
            additional_context: Contexte personnel additionnel à intégrer
            
        Returns:
            La réponse générée
        """
        try:


            context = additional_context
            formatted_history = self._format_conversation_history(conversation_history)
            complexity = "low" if mode == "voice" or len(message.split()) < 10 else "medium"

            # 6. Construire le prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", self.system_prompt.replace("{context}", context)),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}")
            ])
            
            # 7. Utiliser le modèle pour obtenir une réponse
            chain = (
                {"input": RunnablePassthrough(), "chat_history": lambda _: formatted_history}
                | prompt
                | RunnableLambda(lambda x: model_manager.generate_response(
                    x,
                    websocket=websocket,
                    complexity=complexity
                ))
            )
            
            # Exécuter la chaîne de façon asynchrone
            response = await chain.ainvoke(message)
            
            return response
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du message: {str(e)}")
            return "Je suis désolé, j'ai rencontré une erreur lors du traitement de votre demande. Pourriez-vous reformuler ou réessayer plus tard?"
##############


# Instance globale du gestionnaire LangChain
langchain_manager = LangChainManager()