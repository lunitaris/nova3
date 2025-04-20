"""
Intégration du système vocal complet pour l'assistant IA.
Combine la détection de mot d'activation, la reconnaissance vocale, et le traitement des requêtes.
"""
import os
import logging
import asyncio
import time
import tempfile
import wave
from typing import Optional, Callable, Dict, Any

# Après (fonctionne quand backend est dans PYTHONPATH)
from backend.voice.hotword_detector import HotwordDetector, ContinuousVoiceProcessor
from backend.utils.singletons import stt_engine
from backend.utils.singletons import tts_engine
from backend.memory.conversation import conversation_manager
from backend.models.langchain_manager import langchain_manager
from backend.models.skills.manager import skills_manager
from backend.config import config  # ✅ ← ajoute ça ici

logger = logging.getLogger(__name__)

class VocalAssistant:
    """
    Assistant vocal complet avec détection de mot d'activation, traitement des requêtes et réponse vocale.
    """
    
    def __init__(
        self,
        hotword: str = "assistant",
        sensitivity: float = 0.5,
        conversation_timeout: int = 10,
        conversation_id: Optional[str] = None,
        user_id: str = "anonymous"
    ):
        """
        Initialise l'assistant vocal.
        
        Args:
            hotword: Mot d'activation
            sensitivity: Sensibilité de détection du mot d'activation
            conversation_timeout: Timeout d'inactivité pour terminer une conversation (secondes)
            conversation_id: ID de conversation à utiliser (optionnel)
            user_id: ID d'utilisateur
        """
        self.hotword = hotword
        self.sensitivity = sensitivity
        self.conversation_timeout = conversation_timeout
        self.conversation_id = conversation_id
        self.user_id = user_id
        
        self.conversation_processor = None
        self.is_running = False
        self.is_responding = False
        
        # Contrôle de débogage
        self.debug_save_audio = config.debug
        self.debug_dir = os.path.join(config.data_dir, "debug_audio")
        if self.debug_save_audio:
            os.makedirs(self.debug_dir, exist_ok=True)
    
    async def start(self):
        """Démarre l'assistant vocal."""
        if self.is_running:
            logger.warning("L'assistant vocal est déjà en cours d'exécution")
            return
        
        self.is_running = True
        
        # Initialiser le processeur vocal continu
        self.conversation_processor = ContinuousVoiceProcessor(
            hotword=self.hotword,
            hotword_sensitivity=self.sensitivity,
            conversation_timeout=self.conversation_timeout,
            callback=self._handle_conversation_audio
        )
        
        # Démarrer le processeur
        self.conversation_processor.start()
        
        logger.info(f"Assistant vocal démarré avec le mot d'activation '{self.hotword}'")
        
        # Synthétiser un message de démarrage
        greeting = "Je suis prêt à vous aider. Dites mon nom pour m'activer."
        await self._play_response(greeting)
    
    async def stop(self):
        """Arrête l'assistant vocal."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Arrêter le processeur vocal
        if self.conversation_processor:
            self.conversation_processor.stop()
        
        logger.info("Assistant vocal arrêté")
    
    async def _handle_conversation_audio(self, audio_data: bytes):
        """
        Traite l'audio d'une conversation activée par le mot d'activation.
        
        Args:
            audio_data: Données audio de la conversation
        """
        try:
            # Éviter le traitement pendant que l'assistant répond
            if self.is_responding:
                logger.info("Traitement audio ignoré car l'assistant est en train de répondre")
                return
            
            self.is_responding = True
            
            # Sauvegarder l'audio pour le débogage si activé
            if self.debug_save_audio:
                debug_file = os.path.join(self.debug_dir, f"conversation_{int(time.time())}.wav")
                with wave.open(debug_file, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # 16 bits = 2 octets
                    wf.setframerate(16000)
                    wf.writeframes(audio_data)
                logger.debug(f"Audio de conversation sauvegardé dans {debug_file}")
            
            # Transcrire l'audio
            logger.info("Transcription de l'audio...")
            
            # Sauvegarder l'audio dans un fichier temporaire pour la transcription
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_path = temp_file.name
                
                # Écrire l'en-tête WAV et les données audio
                with wave.open(temp_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # 16 bits = 2 octets
                    wf.setframerate(16000)
                    wf.writeframes(audio_data)
            
            # Transcrire le fichier
            transcription_result = await stt_engine.transcribe_file(temp_path)
            
            # Nettoyer le fichier temporaire
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            
            if "error" in transcription_result or not transcription_result.get("text"):
                logger.warning("Échec de la transcription ou texte vide")
                await self._play_response("Je n'ai pas compris ce que vous avez dit.")
                self.is_responding = False
                return
            
            # Texte transcrit
            text = transcription_result["text"]
            logger.info(f"Texte transcrit: {text}")
            
            # Vérifier si le texte contient le mot d'activation seul
            if text.lower().strip() == self.hotword.lower():
                await self._play_response("Je vous écoute, que puis-je faire pour vous?")
                self.is_responding = False
                return
            
            # Traiter la demande
            await self._process_query(text)
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement de l'audio: {str(e)}")
            await self._play_response("Désolé, j'ai rencontré un problème technique.")
        finally:
            self.is_responding = False
    
    async def _process_query(self, query: str):
        """
        Traite une requête utilisateur et génère une réponse.
        
        Args:
            query: Requête utilisateur transcrite
        """
        try:
            # Récupérer ou créer une conversation
            if self.conversation_id is None:
                result = await conversation_manager.process_user_input(
                    conversation_id=None,
                    user_input=query,
                    user_id=self.user_id,
                    mode="voice"
                )
                self.conversation_id = result["conversation_id"]
            else:
                result = await conversation_manager.process_user_input(
                    conversation_id=self.conversation_id,
                    user_input=query,
                    user_id=self.user_id,
                    mode="voice"
                )
            
            # Réponse textuelle
            response_text = result["response"]
            logger.info(f"Réponse générée: {response_text}")
            
            # Synthétiser et jouer la réponse
            await self._play_response(response_text)
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la requête: {str(e)}")
            await self._play_response("Je n'ai pas pu traiter votre demande.")
    
    async def _play_response(self, text: str):
        """
        Synthétise et joue une réponse vocale.
        
        Args:
            text: Texte à synthétiser
        """
        try:
            # Synthétiser la réponse
            logger.info(f"Synthèse de la réponse: {text}")
            
            # Utiliser le streaming pour une meilleure réactivité
            chunks_played = 0
            async for audio_chunk in tts_engine.stream_long_text(text):
                # Ici, en environnement réel, on enverrait le chunk à un dispositif de lecture audio
                # Pour le développement, on compte simplement les chunks
                chunks_played += 1
                await asyncio.sleep(0.05)  # Simuler le temps de lecture
            
            logger.info(f"{chunks_played} chunks audio joués")
            
        except Exception as e:
            logger.error(f"Erreur lors de la lecture de la réponse: {str(e)}")

# Fonction utilitaire pour exécuter l'assistant
async def run_assistant():
    """Exécute l'assistant vocal en mode continu."""
    assistant = VocalAssistant(hotword="assistant", sensitivity=0.7)
    
    try:
        await assistant.start()
        
        # Maintenir l'assistant actif
        print("Assistant vocal démarré, appuyez sur Ctrl+C pour quitter...")
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Arrêt demandé...")
    finally:
        await assistant.stop()

# Point d'entrée pour l'exécution directe
if __name__ == "__main__":
    asyncio.run(run_assistant())