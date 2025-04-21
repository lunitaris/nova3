"""
Smart Context Router pour l'optimisation du pipeline de traitement des requêtes.
Réduit les appels LLM en utilisant une analyse intelligente pour déterminer
quand et comment enrichir le contexte.
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from backend.models.model_manager import model_manager
from backend.memory.vector_store import vector_store
from backend.memory.synthetic_memory import synthetic_memory
from backend.memory.symbolic_memory import symbolic_memory
from backend.memory.enhanced_symbolic_memory import enhanced_symbolic_memory
from backend.utils.profiler import profile
import time
from backend.models.streaming_handler import StreamingWebSocketCallbackHandler


logger = logging.getLogger(__name__)

class SmartContextRouter:
    """
    Router intelligent qui optimise le pipeline de traitement des requêtes utilisateur.
    Détermine intelligemment si et comment enrichir le contexte, puis génère 
    une réponse avec un seul appel LLM.
    """
    
    def __init__(self, model_manager=None, symbolic_memory=None, synthetic_memory=None, vector_store=None):
        """Initialise le router avec les composants nécessaires"""

        self.model_manager = model_manager
        self.symbolic_memory = symbolic_memory or enhanced_symbolic_memory
        self.synthetic_memory = synthetic_memory
        self.vector_store = vector_store

        # Ajouter un cache pour les contextes récemment calculés
        self.context_cache = {}
        self.cache_ttl = 300  # 5 minutes en secondes
        self.cache_max_size = 50  # Nombre maximum d'entrées en cache
        
        # Patterns pour détection rapide sans LLM
        self.memory_command_prefixes = [
            "souviens-toi", "rappelle-toi", "mémorise", "retiens",
            "n'oublie pas", "garde en mémoire"
        ]
        self.question_markers = [
            "qui", "quoi", "quand", "où", "comment", "pourquoi", 
            "quel", "quelle", "quels", "quelles", "est-ce que"
        ]

        logger.info("🔄 SmartContextRouter initialisé avec cache_ttl=%d sec, cache_max_size=%d", self.cache_ttl, self.cache_max_size)

    @profile("smart_router_processing")
    async def process_request(self, user_input: str, conversation_id: str, user_id: str = "anonymous", mode: str = "chat", websocket = None) -> Dict[str, Any]:
        """
        Traite une requête utilisateur avec un pipeline intelligent optimisé.
        
        Args:
            user_input: Texte de la requête utilisateur
            conversation_id: ID de la conversation
            user_id: ID de l'utilisateur
            mode: Mode de conversation ("chat" ou "voice")
            websocket: WebSocket pour streaming (optionnel)
            
        Returns:
            Dictionnaire contenant la réponse et les métadonnées
        """
        logger.info("🎯 SmartRouter: traitement requête [%s] (mode=%s)", user_input[:30] + "..." if len(user_input) > 30 else user_input, mode)
        # 1. Analyse rapide pour classification (sans LLM)
        is_memory_command = any(user_input.lower().startswith(prefix) for prefix in self.memory_command_prefixes)
        has_question_format = any(marker in user_input.lower().split() for marker in self.question_markers)
        is_short_request = len(user_input.split()) < 8
        logger.info("🧠 SmartRouter: classification - memory_cmd=%s, question=%s, short=%s", is_memory_command, has_question_format, is_short_request)

        # 2. Traiter les commandes de mémorisation directement
        if is_memory_command:
            return await self._handle_memory_command(user_input, conversation_id, user_id, mode)
        
        
        # 3. Enrichissement contextuel sélectif sans appel LLM
        start_time = time.time()
        context = await self._selective_context_enrichment(user_input, has_question_format, is_short_request)
        context_time = time.time() - start_time
        logger.info("📊 SmartRouter: contexte obtenu en %.2f ms, taille=%d caractères", 
        context_time * 1000, len(context) if context else 0)
        
        # 4. Construire le prompt optimisé
        prompt = self._build_optimized_prompt(user_input, context, mode)
        
        # 5. Appel LLM unique avec niveau de complexité adapté
        complexity = "low" if mode == "voice" or is_short_request else "medium"
        
        # 6. Générer la réponse (avec ou sans streaming)
        llm_start = time.time()
        if websocket:
            # Envoyer message de début pour le streaming
            try:
                await websocket.send_json({
                    "type": "start",
                    "content": "",
                    "conversation_id": conversation_id
                })
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi du message de début de streaming: {str(e)}")

            # Appel avec streaming
            logger.info(f"[SmartRouter] Appel LLM final | complexité={complexity} | prompt:\n{prompt[:100]}...")
            response_text = await self.model_manager.generate_response(prompt=prompt,websocket=websocket,complexity=complexity, caller="smart_router")
            

            llm_time = time.time() - llm_start
            logger.info("⚡ SmartRouter: réponse LLM générée en %.2f ms, taille=%d caractères", llm_time * 1000, len(response_text))

        else:
            # Appel sans streaming
            logger.info(f"[SmartRouter] Appel LLM final (sans streaming) | complexité={complexity} | prompt:\n{prompt[:100]}...")
            response_text = await self.model_manager.generate_response(prompt=prompt,complexity=complexity, caller="smart_router")
        
        # 7. Déclencher une mémorisation asynchrone en arrière-plan
        asyncio.create_task(
            self._background_memory_processing(user_input, user_id, response_text)
        )


        total_time = time.time() - start_time
        logger.info("✅ SmartRouter: requête traitée en %.2f ms (contexte=%.2f ms, LLM=%.2f ms)", total_time * 1000, context_time * 1000, llm_time * 1000)
        
        return {
            "response": response_text,
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "mode": mode
        }
        


    async def _handle_memory_command(self, user_input: str, conversation_id: str, user_id: str, mode: str) -> Dict[str, Any]:
        """Traite les commandes de mémorisation explicites"""
        logger.info("💾 SmartRouter: traitement commande de mémorisation")
        info_to_memorize = user_input.split(" ", 1)[1] if " " in user_input else ""
        
        if not info_to_memorize:
            return {
                "response": "Que souhaitez-vous que je mémorise ?",
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "mode": mode
            }
        
        try:
            # Enregistrer dans les différents systèmes de mémoire
            memory_id = self.synthetic_memory.remember_explicit_info(info_to_memorize)
            logger.info("📝 SmartRouter: mémorisation explicite - memory_id=%s", memory_id)

            # [COMMENTÉ] Cette ligne provoque des extractions multiples
            # La mise à jour symbolique sera gérée par la conversation
            # asyncio.create_task(
            #     self.symbolic_memory.update_graph_from_text(info_to_memorize)
            # )
            
            return {
                "response": f"J'ai mémorisé cette information : \"{info_to_memorize}\"",
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "mode": mode
            }
        except Exception as e:
            logger.error(f"Erreur lors de la mémorisation explicite: {str(e)}")
            return {
                "response": "Désolé, je n'ai pas pu mémoriser cette information. Erreur technique.",
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "mode": mode,
                "error": str(e)
            }




    @profile("selective_context")
    async def _selective_context_enrichment(self, user_input: str, has_question_format: bool, is_short_request: bool) -> str:
        """
        Sélectionne et récupère le contexte pertinent selon le type de requête.
        Optimisé pour éviter les recherches inutiles.
        Version avec cache de l'enrichissement contextuel
        """
        import time
        logger.info("🔍 SmartRouter: début enrichissement contextuel - question=%s, court=%s", has_question_format, is_short_request)

        #######£ Version avec mise en cache ######
        # Calculer une clé simplifiée pour le cache (sans casser sur la sensibilité à la casse/ponctuation)
        cache_key = ' '.join(user_input.lower().split())
        current_time = time.time()
        
        # Vérifier si nous avons un résultat en cache
        current_time = time.time()
        if cache_key in self.context_cache:
            context, timestamp = self.context_cache[cache_key]
            # Utiliser le cache si pas expiré
            if current_time - timestamp < self.cache_ttl:
                logger.debug(f"Utilisation du contexte en cache pour: {cache_key[:30]}")
                logger.info("⚡ SmartRouter: HIT cache pour contexte! age=%.2f sec", current_time - timestamp)
                return context

        ###############
        context_parts = []
        sym_start = time.time()
        # Pour les questions, prioriser le contexte symbolique (plus rapide)
        symbolic_context = ""
        try:
            if has_question_format:
                symbolic_context = self.symbolic_memory.get_context_for_query(user_input, max_results=3)
                if symbolic_context:
                    context_parts.append(symbolic_context)
        except Exception as e:
            logger.warning(f"[SmartRouter] Erreur enrichissement symbolique: {e}")


        
        sym_time = time.time() - sym_start
        logger.info("🧩 SmartRouter: contexte symbolique obtenu en %.2f ms, taille=%d", 
        sym_time * 1000, len(symbolic_context) if symbolic_context else 0)
        syn_start = time.time()
        # Pour les requêtes plus longues ou complexes, ajouter du contexte synthétique
        if not is_short_request:
            try:
                synthetic_memories = self.synthetic_memory.get_relevant_memories(user_input, max_results=2)
                if synthetic_memories:
                    synthetic_context = "\n\n".join([
                        f"Synthèse mémorisée: {mem.get('content', '')}" 
                        for mem in synthetic_memories
                    ])
                    context_parts.append(synthetic_context)
                syn_time = time.time() - syn_start
                logger.info("📚 SmartRouter: contexte synthétique obtenu en %.2f ms, taille=%d", 
                syn_time * 1000, len(synthetic_context) if 'synthetic_context' in locals() else 0)
            except Exception as e:
                logger.warning(f"Erreur récupération contexte synthétique: {str(e)}")
        
        # Pour les requêtes très spécifiques ou personnelles, recherche vectorielle sélective
        vec_start = time.time()
        if has_question_format and (
            any(term in user_input.lower() for term in ["préfère", "aime", "déteste", "habite", "travaille"])
        ):
            try:
                vector_results = self.vector_store.search_memories(user_input, k=2)
                if vector_results:
                    vector_context = "\n".join([
                        f"Information mémorisée: {res.get('content', '')}"
                        for res in vector_results
                    ])
                    context_parts.append(vector_context)
                vec_time = time.time() - vec_start
                logger.info("📊 SmartRouter: contexte vectoriel obtenu en %.2f ms, taille=%d", 
                vec_time * 1000, len(vector_context) if 'vector_context' in locals() else 0)
            except Exception as e:
                logger.warning(f"Erreur récupération contexte vectoriel: {str(e)}")
        
        # Combiner tous les contextes
        combined_context = "\n\n".join(filter(None, context_parts))
        
        # Stocker en cache pour les prochaines requêtes similaires
        self.context_cache[cache_key] = (combined_context, current_time)
        logger.info("💾 SmartRouter: contexte mis en cache, taille=%d, état cache=%d/%d", len(combined_context), len(self.context_cache), self.cache_max_size)
        
        # Nettoyer le cache si trop grand
        if len(self.context_cache) > self.cache_max_size:
            # Supprimer les entrées les plus anciennes
            oldest_keys = sorted(
                self.context_cache.keys(), 
                key=lambda k: self.context_cache[k][1]
            )[:len(self.context_cache) - self.cache_max_size]
            
            for key in oldest_keys:
                del self.context_cache[key]
            logger.info("🧹 SmartRouter: nettoyage cache, suppression de %d entrées", len(oldest_keys))
                
        return combined_context

    
    def _build_optimized_prompt(self, user_input: str, context: str, mode: str) -> str:
        """
        Construit un prompt optimisé qui intègre intelligemment le contexte.
        Adapté au mode (chat/voice) pour des réponses appropriées.
        """
        # Base du prompt
        base_prompt = f"""Ta mission est de répondre à cette requête en tant qu'assistant domestique Nova.

REQUÊTE: "{user_input}"
"""
        
        # Ajouter le contexte s'il existe
        if context:
            base_prompt += f"""
CONTEXTE PERTINENT:
{context}
"""
        
        # Instructions adaptées au mode
        if mode == "voice":
            base_prompt += """
INSTRUCTIONS:
1. Réponds de façon très concise (1-2 phrases maximum).
2. Utilise un ton conversationnel et naturel, adapté à une interaction vocale.
3. Évite de mentionner explicitement le "contexte" ou "ce que tu sais déjà".
4. Si aucune information pertinente n'est disponible dans le contexte, réponds simplement que tu ne connais pas l'information.
5. Formule ta réponse pour qu'elle soit immédiatement utile.
"""
        else:  # mode chat
            base_prompt += """
INSTRUCTIONS:
1. Réponds de façon claire et précise.
2. Si la requête concerne des informations personnelles de l'utilisateur, base-toi uniquement sur le contexte fourni.
3. Si aucune information pertinente n'est disponible dans le contexte, réponds simplement que tu ne connais pas l'information.
4. Évite de mentionner explicitement le "contexte fourni" ou "ce que tu sais".
"""

        # Demander la réponse
        base_prompt += "\nRÉPONSE:"
        
        return base_prompt


    async def _background_memory_processing(self, user_input: str, user_id: str, response_text: str) -> None:
        """
        Traite la mémorisation en arrière-plan sans bloquer la réponse.
        Analyse et stocke les informations pertinentes pour un apprentissage continu.
        """
        try:
            # Commenté pour éviter la duplication avec l'extraction de Conversation
            # L'extraction symbolique est déjà gérée par la classe Conversation
            # 1. Mise à jour du graphe symbolique (si pertinent)
            # if len(user_input.split()) > 5:  # Ignorer les entrées très courtes
            #     asyncio.create_task(
            #         self.symbolic_memory.update_graph_from_text(user_input, confidence=0.7)
            #     )
            
            # 2. D'autres traitements de mémoire peuvent être ajoutés ici
            # Par exemple, analyser le dialogue pour extraire des préférences utilisateur
            # ou mettre à jour un profile utilisateur, etc.
            
            pass
                
        except Exception as e:
            # Ne pas interrompre la réponse principale en cas d'erreur
            logger.error(f"Erreur dans le traitement mémoire en arrière-plan: {str(e)}")


logger.info("🚀 Création de l'instance SmartContextRouter")
# Instance globale du router
smart_router = SmartContextRouter(
    model_manager=model_manager,
    symbolic_memory=enhanced_symbolic_memory,
    synthetic_memory=synthetic_memory,
    vector_store=vector_store
)
logger.info("✅ SmartContextRouter initialisé avec succès")
