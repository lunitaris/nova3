"""
Gestionnaire de streaming WebSocket pour intégration avec les modèles LLM.
Permet le streaming token-par-token dans l'interface utilisateur.
"""
import logging
import asyncio
import threading
from typing import Any, Dict, List, Optional
from langchain_core.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)

class StreamingWebSocketCallbackHandler(BaseCallbackHandler):
    """Callback handler pour le streaming vers WebSocket."""
    
    def __init__(self, websocket=None):
        """Initialise le handler avec un WebSocket optionnel."""
        self.websocket = websocket
        self.is_active = True
        self.tokens_buffer = []
        self.loop = None
        
        # Tenter d'obtenir la boucle d'événements courante de manière sécurisée
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            # Pas de boucle courante
            pass
    
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Appelé à chaque nouveau token généré par le LLM."""
        if not self.websocket or not self.is_active:
            return
            
        try:
            # Ajouter le token au buffer
            self.tokens_buffer.append(token)
            
            # Logger le token pour le débogage
            logger.debug(f"Token généré: '{token}'")
            
            # Méthode de synchronisation sécurisée
            self._safe_send_token(token)
                
        except Exception as e:
            self.is_active = False
            logger.error(f"Erreur lors du traitement du token: {str(e)}")
    
    def _safe_send_token(self, token: str):
        """
        Méthode synchrone pour gérer l'envoi de tokens de manière sécurisée
        dans différents contextes de thread/boucle d'événements.
        """
        if not self.websocket or not self.is_active:
            return
            
        try:
            # Si nous avons une boucle d'événements, nous pouvons utiliser call_soon_threadsafe
            if self.loop and self.loop.is_running():
                # Méthode thread-safe pour planifier l'envoi
                self.loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(self._send_token(token))
                )
            else:
                # Approche alternative: utiliser run_coroutine_threadsafe ou créer une future
                # et l'envoyer via une méthode non-bloquante
                current_thread = threading.current_thread()
                main_thread = threading.main_thread()
                
                if current_thread == main_thread:
                    # Dans le thread principal, on peut tenter de configurer une boucle si nécessaire
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        # Pas de boucle active, ne rien faire (le token reste dans le buffer)
                        pass
                    else:
                        # Utiliser la boucle si elle existe
                        asyncio.create_task(self._send_token(token))
                else:
                    # Dans un thread secondaire, on peut essayer d'utiliser run_coroutine_threadsafe
                    # si nous avons accès à une boucle d'événements
                    if hasattr(asyncio, "run_coroutine_threadsafe") and self.loop:
                        asyncio.run_coroutine_threadsafe(self._send_token(token), self.loop)
                    else:
                        # Sinon, laisser le token dans le buffer pour qu'il soit traité
                        # avec les autres à la fin
                        pass
                
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi sécurisé du token: {str(e)}")

    async def _send_token(self, token: str):
        """Envoie un token via WebSocket."""
        if not self.websocket or not self.is_active:
            return
            
        try:
            # Envoyer directement le token
            await self.websocket.send_json({
                "type": "token",
                "content": token
            })
            # Ajoutons ce log pour confirmer l'activité positive
            if len(self.tokens_buffer) % 10 == 0:  # log tous les 10 tokens pour ne pas polluer
                logger.debug(f"✓ WebSocket streaming actif: {len(token)} caractères envoyés")
        except Exception as e:
            # Si l'envoi échoue, désactiver ce handler
            self.is_active = False

    
    async def flush_remaining_tokens(self):
        """
        Vide le buffer et envoie tous les tokens restants.
        À appeler explicitement à la fin du streaming.
        """
        if not self.tokens_buffer or not self.websocket or not self.is_active:
            logger.info("✓ Streaming terminé (aucun token restant à envoyer)")
            return
            
        try:
            combined_tokens = "".join(self.tokens_buffer)
            token_count = len(self.tokens_buffer)
            char_count = len(combined_tokens)
            self.tokens_buffer = []
            
            await self.websocket.send_json({
                "type": "token",
                "content": combined_tokens
            })
            logger.info(f"✓ Tokens restants envoyés: {token_count} tokens, {char_count} caractères")
        except Exception as e:
            logger.error(f"❌ Erreur lors du vidage du buffer: {str(e)}")