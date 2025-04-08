"""
Gestionnaire de modèles LLM pour l'assistant IA.
"""
import logging
import time
import os
from typing import Dict, Any, Optional
import asyncio

# Remplacer les importations dépréciées
from langchain_community.llms import Ollama
from langchain_community.chat_models import ChatOpenAI
from langchain_core.callbacks import CallbackManager, StreamingStdOutCallbackHandler
from langchain_core.callbacks.base import BaseCallbackHandler

from config import config

logger = logging.getLogger(__name__)

class StreamingWebSocketCallbackHandler(BaseCallbackHandler):
    """Callback handler pour le streaming vers WebSocket."""
    
    def __init__(self, websocket=None):
        """Initialise le handler avec un WebSocket optionnel."""
        self.websocket = websocket
        self.is_active = True
        self.buffer = ""
        

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Appelé à chaque nouveau token généré par le LLM."""
        if self.websocket and self.is_active:
            try:
                # Accumulate token in buffer and send if it contains a word or punctuation
                self.buffer += token
                
                # Send immediately for better user experience
                asyncio.create_task(self._send_token(token))
                
            except Exception as e:
                self.is_active = False
                logger.error(f"Impossible d'envoyer un token via WebSocket: {str(e)}")

    async def _send_token(self, token: str):
        """Envoie un token via WebSocket."""
        try:
            await self.websocket.send_json({
                "type": "token",
                "content": token
            })
            logger.debug(f"Token envoyé: {token}")
        except Exception as e:
            # Si l'envoi échoue, désactiver ce handler
            self.is_active = False
            logger.error(f"Échec d'envoi de token: {str(e)}")



class ModelManager:
    """
    Gère les différents modèles LLM et sélectionne le plus approprié selon le contexte.
    """
    
    def __init__(self):
        """Initialise le gestionnaire de modèles."""
        self.models = {}
        self._initialize_models()
        
    def _initialize_models(self):
        """Initialise les modèles configurés."""
        try:
            # Initialiser les modèles locaux via Ollama
            for model_id, model_config in config.models.items():
                if model_config.type == "local":
                    try:
                        self.models[model_id] = self._init_ollama_model(model_config)
                        logger.info(f"Modèle local {model_id} ({model_config.name}) initialisé")
                    except Exception as e:
                        logger.error(f"Erreur d'initialisation du modèle {model_id}: {str(e)}")
                
                elif model_config.type == "cloud" and model_config.name.startswith("gpt"):
                    try:
                        # On utilisera ChatOpenAI à la demande, pas d'initialisation préalable
                        # Vérifier juste la présence de la clé API
                        if not os.environ.get("OPENAI_API_KEY"):
                            logger.warning(f"Clé API OpenAI manquante pour le modèle {model_id}")
                        else:
                            logger.info(f"Configuration pour modèle cloud {model_id} validée")
                    except Exception as e:
                        logger.error(f"Erreur de validation du modèle cloud {model_id}: {str(e)}")
        
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation des modèles: {str(e)}")
    
    def _init_ollama_model(self, model_config):
        """
        Initialise un modèle Ollama.
        
        Args:
            model_config: Configuration du modèle
            
        Returns:
            Instance Ollama configurée
        """
        return Ollama(
            model=model_config.name,
            temperature=model_config.parameters.get("temperature", 0.7),
            top_p=model_config.parameters.get("top_p", 0.9),
            top_k=model_config.parameters.get("top_k", 40),
            num_ctx=model_config.context_window,
            base_url=model_config.api_base,
            callbacks=[StreamingStdOutCallbackHandler()]  # Utiliser callbacks au lieu de callback_manager
        )
        
    def _get_appropriate_model(self, prompt: str, complexity: str = "auto", websocket=None):
        """
        Sélectionne le modèle le plus approprié selon le contexte.
        
        Args:
            prompt: Prompt à traiter
            complexity: Complexité de la requête ("low", "medium", "high" ou "auto")
            websocket: WebSocket pour streaming (optionnel)
            
        Returns:
            Instance du modèle sélectionné
        """
        # Si modèle spécifié directement, l'utiliser si disponible
        if complexity in self.models:
            model_id = complexity
        
        # Sinon, sélection automatique selon longueur et complexité
        else:
            # Estimation simple de la longueur de la réponse attendue
            prompt_length = len(prompt.split())
            
            if complexity == "auto":
                # Logique simple d'estimation de complexité
                if prompt_length < 100:
                    model_id = "fast"  # Requêtes courtes
                else:
                    model_id = "balanced"  # Requêtes moyennes à longues
            elif complexity == "low":
                model_id = "fast"
            elif complexity == "high" and "cloud_fallback" in self.models:
                model_id = "cloud_fallback"
            else:
                model_id = "balanced"  # Par défaut pour complexité moyenne
        
        # Si le modèle n'est pas disponible, fallback
        if model_id not in self.models:
            available_models = list(self.models.keys())
            if not available_models:
                raise ValueError("Aucun modèle disponible")
            
            # Utiliser le premier modèle disponible
            model_id = available_models[0]
            logger.warning(f"Modèle {model_id} non disponible, utilisation de {model_id}")
        
        # Pour OpenAI, créer une nouvelle instance à chaque fois avec streaming si nécessaire
        if model_id == "cloud_fallback":
            model_config = config.models[model_id]
            
            callbacks = []
            if websocket:
                callbacks.append(StreamingWebSocketCallbackHandler(websocket))
            
            return ChatOpenAI(
                model_name=model_config.name,
                temperature=model_config.parameters.get("temperature", 0.7),
                max_tokens=model_config.parameters.get("max_tokens", 1024),
                streaming=bool(websocket),
                callbacks=callbacks  # Utiliser callbacks directement
            )
        
        # Pour les modèles locaux
        model = self.models[model_id]
        
        # Si WebSocket fourni et streaming demandé, configurer le callback
        if websocket and hasattr(model, 'callbacks'):               # Nouvelle façon (si le modèle supporte les callbacks dynamiques):
            model.callbacks.append(StreamingWebSocketCallbackHandler(websocket))
        return model
    
    async def generate_response(
        self, 
        prompt: str, 
        websocket=None, 
        complexity: str = "auto",
        max_retries: int = 2,
        retry_delay: int = 1
    ) -> str:
        """
        Génère une réponse à partir du prompt.
        
        Args:
            prompt: Prompt pour la génération
            websocket: WebSocket pour streaming (optionnel)
            complexity: Complexité de la requête ("low", "medium", "high" ou "auto")
            max_retries: Nombre maximal de tentatives
            retry_delay: Délai entre les tentatives (secondes)
            
        Returns:
            Texte généré
        """
        retries = 0
        
        while retries <= max_retries:
            try:
                start_time = time.time()
                
                # Sélectionner le modèle approprié
                model = self._get_appropriate_model(prompt, complexity, websocket)
                
                # Générer la réponse
                if isinstance(model, ChatOpenAI):
                    # Pour ChatOpenAI, utiliser le format de messages
                    from langchain_core.messages import HumanMessage
                    messages = [HumanMessage(content=prompt)]
                    if websocket:
                        response = await model.agenerate([messages])
                        return response.generations[0][0].text
                    else:
                        response = await model.ainvoke(messages)
                        return response.content
                else:
                    # Pour les autres modèles (Ollama)
                    response = await model.ainvoke(prompt)
                    
                elapsed_time = time.time() - start_time
                logger.info(f"Réponse générée en {elapsed_time:.2f}s")
                
                # Nettoyer la réponse
                response = response.strip()
                return response
                
            except Exception as e:
                logger.error(f"Erreur de génération (tentative {retries+1}/{max_retries+1}): {str(e)}")
                retries += 1
                
                if retries <= max_retries:
                    # Attendre avant de réessayer
                    await asyncio.sleep(retry_delay)
                else:
                    # Si toutes les tentatives ont échoué
                    error_msg = f"Erreur lors de la génération de réponse après {max_retries+1} tentatives."
                    logger.error(error_msg)
                    return "Désolé, je rencontre des difficultés techniques. Pourriez-vous reformuler ou réessayer plus tard?"

# Instance globale du gestionnaire de modèles
model_manager = ModelManager()