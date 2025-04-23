"""
Gestionnaire de modèles LLM pour l'assistant IA.
"""
import logging
import time
import os
from typing import Dict, Any, Optional
import asyncio

from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI

from backend.config import config
from backend.config import OPENAI_API_KEY
from langchain_core.callbacks.base import BaseCallbackHandler
from backend.utils.profiler import profile
from backend.utils.startup_log import add_startup_event
import textwrap
from backend.models.streaming_callbacks import StreamingWebSocketCallbackHandler
import asyncio  # <-- Ajout important !
from typing import Dict, Any, Optional
from backend.utils.profiler import trace_step, TreeTracer, current_trace  # AJOUT POUR TRACE




logger = logging.getLogger(__name__)

class ModelManager:
    """
    Gère les différents modèles LLM et sélectionne le plus approprié selon le contexte.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    
    def __init__(self):
        """Initialise le gestionnaire de modèles."""
        self.models = {}
        self._initialize_models()
        
    def _initialize_models(self):
        llm_models = []
        try:
            for model_id, model_config in config.models.items():
                if model_config.type == "local":
                    try:
                        self.models[model_id] = self._init_ollama_model(model_config)
                        # logger.info(f"Modèle local {model_id} ({model_config.name}) initialisé")  ## DEBUG
                        llm_models.append(f"{model_config.name} ({model_id})")
                    except Exception as e:
                        logger.error(f"Erreur d'initialisation du modèle {model_id}: {str(e)}")

                elif model_config.type == "cloud" and model_config.name.startswith("gpt"):
                    try:
                        if not OPENAI_API_KEY:
                            logger.warning(f"Clé API OpenAI manquante pour le modèle {model_id}")
                        else:
                            # logger.info(f"Modèle cloud {model_config.name} ({model_id}) configuré")   ## DEBUG
                            llm_models.append(f"{model_config.name} ({model_id}, cloud)")
                    except Exception as e:
                        logger.error(f"Erreur de validation du modèle cloud {model_id}: {str(e)}")

            if llm_models:
                models_str = ", ".join(llm_models)
                add_startup_event({
                    "icon": "🧠",
                    "label": "Modèles LLM",
                    "message": models_str
                })

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation des modèles: {str(e)}")


    # @profile("ollama_init")       ## DEBUG A DECOMMENTER SI BESOIN
    def _init_ollama_model(self, model_config):
        """
        Initialise un modèle Ollama.
        
        Args:
            model_config: Configuration du modèle
            
        Returns:
            Instance Ollama configurée
        """
        return OllamaLLM(
            model=model_config.name,
            temperature=model_config.parameters.get("temperature", 0.7),
            top_p=model_config.parameters.get("top_p", 0.9),
            top_k=model_config.parameters.get("top_k", 40),
            num_ctx=model_config.context_window,
            base_url=model_config.api_base,
            callbacks=[]  # FIX: Retirez les callbacks de démarrage qui pourraient causer des problèmes
        )


    @profile("llm_get_model")
    @trace_step("⚙️ ModelManager > _get_appropriate_model()")
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
            
            logger.info(f"[LLM] 1.....Modèle sélectionné : {model_id}")
            # Utiliser le premier modèle disponible
            model_id = available_models[0]        

        logger.info(f"[ModelManager] Modèle sélectionné : {model_id}")
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
        logger.info(f"🧠 Modèle final utilisé : {model_id}")
        return model
    
    @profile("generate_response")
    @trace_step("🧠 ModelManager > generate_response()")
    async def generate_response(self, prompt: str, websocket=None, complexity: str = "auto",max_retries: int = 2,retry_delay: int = 1,caller: str = "unknown") -> str:
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
        # ⚠️ OPTIMISATION: logs et surveillance de taille
        safe_preview = prompt[:100].replace("\n", " ") + ("..." if len(prompt) > 100 else "")
        logger.info(f"🧠 Appel LLM via generate_response() [{caller}]: complexité={complexity}, longueur={len(prompt)}, début={safe_preview}")

        if len(prompt) > 4000:
            logger.warning(f"⚠️ Prompt très long détecté ({len(prompt)} caractères) — à optimiser")
        logger.debug(f"[DEBUG] Prompt complet envoyé au LLM:\n{prompt}")
        logger.info(f"[DEBUG] Longueur du prompt : {len(prompt)} caractères")
        retries = 0

        logger.info(textwrap.dedent(f"""
        🧠 Appel LLM via generate_response()
        • Complexité       : {complexity}
        • Max tokens       : {model_config.parameters.get("max_tokens", "?" ) if 'model_config' in locals() else "?"}
        • WebSocket actif  : {"oui" if websocket else "non"}
        • Prompt (début)   : {repr(prompt[:120])}...
        """))

        global current_trace
        tracer = TreeTracer("📤 Envoi prompt au LLM", args={"caller": caller, "complexity": complexity})
        current_trace = tracer

        
        while retries <= max_retries:
            try:
                start_time = time.time()
                safe_prompt = prompt[:200].replace('\n', ' ')
                logger.info(f"[ModelManager] ➤ Prompt envoyé (complexité={complexity}) : {safe_prompt}...")
                 
                # Sélectionner le modèle approprié
                step_model = tracer.step("🎯 Sélection du modèle")
                model = self._get_appropriate_model(prompt, complexity, websocket)
                step_model.done(type(model).__name__)
                
                # Générer la réponse
                logger.info(f"[ModelManager] Prompt word count : {len(prompt.split())}")
                step_gen = tracer.step("✍️ Génération de la réponse")
                response = await self._generate_from_model(model, prompt, websocket)
                step_gen.done(f"{len(response.strip())} caractères")
                elapsed_time = time.time() - start_time
                logger.info(f"Réponse générée en {elapsed_time:.2f}s")
                
                # Nettoyer la réponse
                response = response.strip()
                logger.info(f"[ModelManager] ✅ Réponse générée - taille: {len(response)} caractères")
                tracer.done("✅ Réponse générée")
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


    @profile("llm_generation")
    @trace_step("🧪 ModelManager > _generate_from_model()")
    async def _generate_from_model(self, model, prompt, websocket):
        """Génère la réponse avec le modèle spécifié."""

        global current_trace
        tracer = TreeTracer("⚙️ Appel du modèle", args={"type": type(model).__name__})
        current_trace = tracer

        # Si modèle OpenAI → logique actuelle conservée
        if isinstance(model, ChatOpenAI):
            if websocket:
                from backend.models.streaming_callbacks import StreamingWebSocketCallbackHandler  # ✅ nouveau chemin
                callback = StreamingWebSocketCallbackHandler(websocket)
                response = await model.ainvoke(prompt, config={"callbacks": [callback]})
                # Envoyer les tokens restants à la fin
                await callback.flush_remaining_tokens()
                tracer.done("✅ Réponse générée")
                return response.content
            else:
                response = await model.ainvoke(prompt)
                tracer.done("✅ Réponse générée")
                return response.content

        # ✅ PATCH OLLAMA STREAMING
        if websocket:
            from backend.models.streaming_callbacks import StreamingWebSocketCallbackHandler  # ✅ nouveau chemin
            callback = StreamingWebSocketCallbackHandler(websocket)            
            streamed_chunks = []
            try:
                # Utiliser astream avec le callback
                async for chunk in model.astream(prompt, config={"callbacks": [callback]}):
                    streamed_chunks.append(chunk)
                
                # Vider les tokens restants à la fin du streaming
                await callback.flush_remaining_tokens()
                tracer.done("✅ Réponse générée")
                return "".join(streamed_chunks)
            except Exception as e:
                logger.error(f"Erreur pendant le streaming: {str(e)}")
                # En cas d'erreur, essayer de vider le buffer si possible
                try:
                    await callback.flush_remaining_tokens()
                except:
                    pass
                # Fallback: continuer avec une génération non-streaming
                tracer.done("✅ Fallback génération non streaming..")
                return await model.ainvoke(prompt)

        # Si pas de WebSocket, réponse normale
        return await model.ainvoke(prompt)


# Instance globale du gestionnaire de modèles
model_manager = ModelManager()