
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
from backend.memory.vector_store import vector_store
from backend.memory.synthetic_memory import synthetic_memory
from backend.memory.symbolic_memory import symbolic_memory
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
        self.system_prompt = """Tu es un assistant IA local nommé Assistant. Tu es serviable, poli et informatif.
Voici quelques règles que tu dois suivre:
- Réponds de manière concise et précise aux questions.
- Si tu ne connais pas la réponse, dis simplement que tu ne sais pas.
- Utilise un langage simple et accessible, sauf si on te demande d'être plus technique.
- N'invente pas d'informations.
- Respecte les préférences de l'utilisateur.
- Pour les commandes domotiques et les actions spécifiques, sois précis dans ta compréhension.

{context}
"""
        self._init_memory_chains()
    
    def _init_memory_chains(self):
        """Initialise les chaînes de mémoire."""
        # logger.info("Initialisation des chaînes de mémoire")  ## DEBUG
        add_startup_event({"icon": "🧠", "label": "LangChain", "message": "chaînes conversationnelles prêtes"})
    
    async def _get_relevant_context(self, query: str, conversation_history: List[Dict[str, Any]]) -> str:
        """
        Récupère le contexte pertinent à partir des mémoires.
        
        Args:
            query: La requête ou le message actuel de l'utilisateur
            conversation_history: L'historique récent de la conversation
            
        Returns:
            Contexte formaté pour le prompt
        """
        try:
            # Récupérer les souvenirs pertinents
            vector_memories = vector_store.search_memories(query, k=3)
            
            # Récupérer les souvenirs synthétiques
            synthetic_memories = synthetic_memory.get_relevant_memories(query, max_results=2)
            
            # Formater le contexte
            context = "Informations issues de la mémoire:\n"
            
            if vector_memories:
                context += "\nMémoire explicite:\n"
                for i, memory in enumerate(vector_memories, 1):
                    content = memory.get("content", "")
                    timestamp = memory.get("timestamp", "")
                    context += f"{i}. {content} (Mémorisé le: {timestamp})\n"
            
            if synthetic_memories:
                context += "\nMémoire synthétique:\n"
                for i, memory in enumerate(synthetic_memories, 1):
                    content = memory.get("content", "")
                    context += f"{i}. {content}\n"
            
            if not vector_memories and not synthetic_memories:
                context += "Aucune information pertinente en mémoire pour cette requête.\n"
            
            return context
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du contexte mémoriel: {str(e)}")
            return "Erreur d'accès à la mémoire."
    
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
    
    async def _detect_intent(self, query: str) -> Dict[str, Any]:
        """
        Détecte l'intention de l'utilisateur pour des commandes spécifiques.
        
        Args:
            query: La requête de l'utilisateur
            
        Returns:
            Informations sur l'intention détectée
        """
        # Schéma simple pour détecter les commandes domotiques, les rappels, etc.
        intent_prompt = """Analyse la requête utilisateur et identifie si c'est une commande spécifique.
Retourne une réponse au format JSON avec:
- "intent": le type de commande ("domotique", "rappel", "recherche", "general", etc.)
- "confidence": niveau de confiance entre 0 et 1
- "entities": entités extraites de la requête (appareils, lieux, dates, etc.)

Requête: {query}

Format de réponse (JSON):
"""
        
        try:
            # Utiliser un modèle rapide pour la détection d'intention
            response = await model_manager.generate_response(
                intent_prompt.replace("{query}", query),
                complexity="low"
            )
            
            # Extraire la partie JSON
            import json
            try:
                # Supprimer les backticks et identifiants de format potentiels
                clean_response = response.replace("```json", "").replace("```", "").strip()
                intent_data = json.loads(clean_response)
                return intent_data
            except json.JSONDecodeError:
                logger.warning(f"Réponse d'intention non parsable: {response}")
                return {
                    "intent": "general",
                    "confidence": 0.5,
                    "entities": {}
                }
                
        except Exception as e:
            logger.error(f"Erreur lors de la détection d'intention: {str(e)}")
            # Valeur par défaut
            return {
                "intent": "general",
                "confidence": 0.3,
                "entities": {}
            }
####################################################
    #
    #


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
            # 1. Détecter l'intention (pour traiter différemment selon le type de requête)
            intent_data = await self._detect_intent(message)
            logger.info(f"Intention détectée: {intent_data['intent']} (confiance: {intent_data['confidence']})")
            
            # 2. Récupérer le contexte depuis les mémoires
            context = await self._get_relevant_context(message, conversation_history)
            
            # 3. Intégrer le contexte personnel s'il existe
            if additional_context:
                # Ajouter le contexte personnel en début de contexte pour lui donner plus d'importance
                context = f"{additional_context}\n\n{context}"
            
            # 4. Déterminer la complexité requise selon l'intention et la longueur
            if mode == "voice" or intent_data["intent"] == "general":
                complexity = "low" if len(message.split()) < 10 else "medium"
            else:
                complexity = "medium"
            
            # 5. Formater l'historique et le contexte
            formatted_history = self._format_conversation_history(conversation_history[-5:])  # Limiter à 5 derniers messages
            
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
    async def _get_relevant_context(self, query: str, conversation_history: List[Dict[str, Any]]) -> str:
        """
        Récupère le contexte pertinent à partir des mémoires.
        
        Args:
            query: La requête ou le message actuel de l'utilisateur
            conversation_history: L'historique récent de la conversation
            
        Returns:
            Contexte formaté pour le prompt
        """
        try:
            # Récupérer les souvenirs pertinents
            vector_memories = vector_store.search_memories(query, k=3)
            
            # Récupérer les souvenirs synthétiques
            synthetic_memories = synthetic_memory.get_relevant_memories(query, max_results=2)
            
            # Récupérer le contexte du graphe symbolique
            symbolic_context = symbolic_memory.get_context_for_query(query, max_results=2)
            
            # Formater le contexte
            context = "Informations issues de la mémoire:\n"
            has_content = False
            
            if vector_memories:
                context += "\nMémoire explicite:\n"
                for i, memory in enumerate(vector_memories, 1):
                    content = memory.get("content", "")
                    timestamp = memory.get("timestamp", "")
                    context += f"{i}. {content} (Mémorisé le: {timestamp})\n"
                has_content = True
            
            if synthetic_memories:
                context += "\nMémoire synthétique:\n"
                for i, memory in enumerate(synthetic_memories, 1):
                    content = memory.get("content", "")
                    context += f"{i}. {content}\n"
                has_content = True
            
            if symbolic_context:
                context += "\nMémoire symbolique:\n"
                context += symbolic_context + "\n"
                has_content = True
            
            if not has_content:
                context += "Aucune information pertinente en mémoire pour cette requête.\n"
            
            return context
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du contexte mémoriel: {str(e)}")
            return "Erreur d'accès à la mémoire."



# Instance globale du gestionnaire LangChain
langchain_manager = LangChainManager()