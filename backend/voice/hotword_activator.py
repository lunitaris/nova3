"""
Détecteur de mot d'activation (hotword) pour l'assistant vocal.
Basé sur Porcupine pour une détection légère sur CPU.
"""
import os
import logging
import asyncio
import threading
import time
import numpy as np
import pyaudio
import wave
from typing import Callable, Optional, List, Dict, Any
from queue import Queue

from config import config

logger = logging.getLogger(__name__)

# Constantes pour l'enregistrement audio
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 512
BUFFER_SECONDS = 3  # Secondes à conserver dans le buffer

try:
    # Tentative d'importation de Porcupine (optionnel)
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    logger.warning("Porcupine n'est pas installé, la détection de mot d'activation sera simulée")
    PORCUPINE_AVAILABLE = False

class HotwordDetector:
    """
    Détecteur de mot d'activation utilisant Porcupine ou une simulation.
    """
    
    def __init__(
        self,
        hotword: str = "assistant",
        sensitivity: float = 0.5,
        callback: Optional[Callable] = None,
        use_simulation: bool = False
    ):
        """
        Initialise le détecteur de mot d'activation.
        
        Args:
            hotword: Mot d'activation à détecter
            sensitivity: Sensibilité de la détection (0-1)
            callback: Fonction à appeler lors de la détection
            use_simulation: Force l'utilisation de la simulation
        """
        self.hotword = hotword
        self.sensitivity = sensitivity
        self.callback = callback
        self.running = False
        self.use_simulation = use_simulation or not PORCUPINE_AVAILABLE
        
        # File d'attente pour communiquer entre threads
        self.detection_queue = Queue()
        
        # Audio buffer circulaire pour conserver les dernières secondes avant l'activation
        self.buffer_size = int(SAMPLE_RATE * BUFFER_SECONDS)
        self.audio_buffer = np.zeros(self.buffer_size, dtype=np.int16)
        self.buffer_index = 0
        
        # Chemin pour stocker le modèle personnalisé
        self.model_path = os.path.join(config.data_dir, "hotword_models")
        os.makedirs(self.model_path, exist_ok=True)
        
        # Initialiser PyAudio
        self.p = pyaudio.PyAudio()
        
        # Initialiser Porcupine si disponible
        self.porcupine = None
        if not self.use_simulation:
            self._init_porcupine()
    
    def _init_porcupine(self):
        """Initialise le moteur Porcupine."""
        try:
            # Utiliser le mot-clé par défaut "computer" pour la démonstration
            # Dans un produit, on utiliserait des mots-clés personnalisés
            keywords = ["computer"]
            if self.hotword != "assistant":
                # Si un mot-clé personnalisé est spécifié, tenter de le charger
                if os.path.exists(f"{self.model_path}/{self.hotword}.ppn"):
                    keywords = [f"{self.model_path}/{self.hotword}.ppn"]
            
            self.porcupine = pvporcupine.create(
                keywords=keywords,
                sensitivities=[self.sensitivity]
            )
            
            logger.info(f"Moteur Porcupine initialisé pour le hotword '{self.hotword}'")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de Porcupine: {str(e)}")
            logger.info("Utilisation du mode de simulation à la place")
            self.use_simulation = True
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """
        Callback appelé par PyAudio pour chaque bloc audio.
        
        Args:
            in_data: Données audio brutes
            frame_count: Nombre de trames
            time_info: Informations de timing
            status: Statut de la capture
            
        Returns:
            Données et drapeau de continuation
        """
        if not self.running:
            return None, pyaudio.paAbort
        
        # Convertir les données audio en tableau numpy
        audio_data = np.frombuffer(in_data, dtype=np.int16)
        
        # Ajouter au buffer circulaire
        samples_to_add = min(len(audio_data), self.buffer_size)
        space_left = self.buffer_size - self.buffer_index
        
        if samples_to_add <= space_left:
            # Cas simple: tout rentre dans l'espace restant
            self.audio_buffer[self.buffer_index:self.buffer_index+samples_to_add] = audio_data[:samples_to_add]
            self.buffer_index += samples_to_add
        else:
            # Cas de débordement: diviser en deux parties
            self.audio_buffer[self.buffer_index:] = audio_data[:space_left]
            self.audio_buffer[:samples_to_add-space_left] = audio_data[space_left:samples_to_add]
            self.buffer_index = samples_to_add - space_left
        
        # Si buffer plein, revenir au début
        if self.buffer_index >= self.buffer_size:
            self.buffer_index = 0
        
        # Détection du mot d'activation
        if not self.use_simulation:
            # Utiliser Porcupine pour la détection
            try:
                result = self.porcupine.process(audio_data)
                if result >= 0:  # Mot-clé détecté
                    self.detection_queue.put(True)
            except Exception as e:
                logger.error(f"Erreur lors du traitement Porcupine: {str(e)}")
        else:
            # Mode simulation: vérification basique d'intensité audio
            # Détecter un seuil d'amplitude pour simuler une activation
            if np.max(np.abs(audio_data)) > 10000:  # Seuil arbitraire
                # Un mot probablement prononcé, détecter avec une probabilité faible
                if np.random.random() < 0.01:  # 1% de chance de détection
                    self.detection_queue.put(True)
        
        return in_data, pyaudio.paContinue
    
    def _process_detections(self):
        """Traite les détections dans un thread séparé."""
        while self.running:
            try:
                # Attendre une détection
                detection = self.detection_queue.get(timeout=0.5)
                if detection and self.callback:
                    # Construire les données à envoyer au callback
                    audio_data = self._get_audio_buffer()
                    
                    logger.info("Mot d'activation détecté!")
                    
                    # Appeler le callback
                    self.callback(audio_data)
                    
                    # Réinitialiser le buffer après utilisation
                    self.audio_buffer = np.zeros(self.buffer_size, dtype=np.int16)
                    self.buffer_index = 0
                    
                    # Courte pause pour éviter les détections multiples
                    time.sleep(1)
                    
            except:
                # Timeout ou autre erreur
                pass
    
    def _get_audio_buffer(self) -> bytes:
        """
        Récupère le contenu actuel du buffer audio.
        
        Returns:
            Données audio des dernières secondes
        """
        # Récupérer le buffer de manière cohérente
        if self.buffer_index == 0:
            # Cas simple: le buffer est rempli séquentiellement
            audio_data = self.audio_buffer
        else:
            # Cas circulaire: reconstituer dans l'ordre chronologique
            audio_data = np.concatenate((
                self.audio_buffer[self.buffer_index:],
                self.audio_buffer[:self.buffer_index]
            ))
        
        return audio_data.tobytes()
    
    def save_buffer_to_file(self, filename: str) -> str:
        """
        Sauvegarde le contenu du buffer dans un fichier WAV.
        Utile pour le débogage.
        
        Args:
            filename: Nom du fichier de sortie
            
        Returns:
            Chemin complet du fichier créé
        """
        try:
            # Créer le dossier si nécessaire
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Obtenir les données audio du buffer
            audio_data = self._get_audio_buffer()
            
            # Créer le fichier WAV
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(self.p.get_sample_size(FORMAT))
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_data)
            
            logger.info(f"Buffer audio sauvegardé dans {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du buffer: {str(e)}")
            return ""
    
    def start(self):
        """Démarre la détection de mot d'activation."""
        if self.running:
            logger.warning("Le détecteur est déjà en cours d'exécution")
            return
        
        try:
            self.running = True
            
            # Démarrer le thread de traitement des détections
            self.detection_thread = threading.Thread(target=self._process_detections)
            self.detection_thread.daemon = True
            self.detection_thread.start()
            
            # Ouvrir le flux audio
            self.stream = self.p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=self._audio_callback
            )
            
            logger.info(f"Détecteur de mot d'activation démarré pour '{self.hotword}'")
            if self.use_simulation:
                logger.info("Mode de simulation actif: détection basée sur l'intensité du son")
            
        except Exception as e:
            self.running = False
            logger.error(f"Erreur lors du démarrage du détecteur: {str(e)}")
    
    def stop(self):
        """Arrête la détection de mot d'activation."""
        if not self.running:
            return
        
        self.running = False
        
        # Arrêter le flux audio
        if hasattr(self, 'stream') and self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        # Attendre la fin du thread de détection
        if hasattr(self, 'detection_thread') and self.detection_thread:
            self.detection_thread.join(timeout=1.0)
        
        logger.info("Détecteur de mot d'activation arrêté")
    
    def __del__(self):
        """Nettoyage lors de la destruction de l'objet."""
        self.stop()
        
        # Libérer PyAudio
        if hasattr(self, 'p') and self.p:
            self.p.terminate()
        
        # Libérer Porcupine
        if hasattr(self, 'porcupine') and self.porcupine:
            self.porcupine.delete()

class ContinuousVoiceProcessor:
    """
    Processeur vocal continu qui gère l'activation vocale et l'écoute prolongée.
    """
    
    def __init__(
        self,
        hotword: str = "assistant",
        hotword_sensitivity: float = 0.5,
        conversation_timeout: int = 15,
        callback: Optional[Callable] = None
    ):
        """
        Initialise le processeur vocal continu.
        
        Args:
            hotword: Mot d'activation
            hotword_sensitivity: Sensibilité de détection du mot d'activation
            conversation_timeout: Délai d'inactivité avant fin de conversation (secondes)
            callback: Fonction à appeler avec l'audio de la conversation
        """
        self.hotword = hotword
        self.conversation_timeout = conversation_timeout
        self.callback = callback
        self.in_conversation = False
        self.last_activity = 0
        self.conversation_audio = bytearray()
        
        # Initialiser le détecteur de mot d'activation
        self.hotword_detector = HotwordDetector(
            hotword=hotword,
            sensitivity=hotword_sensitivity,
            callback=self._hotword_detected
        )
        
        # Timer pour vérifier l'inactivité
        self.timer_thread = None
        self.running = False
    
    def _hotword_detected(self, initial_audio: bytes):
        """
        Appelé quand le mot d'activation est détecté.
        
        Args:
            initial_audio: Audio capturé contenant le mot d'activation
        """
        if self.in_conversation:
            # Déjà en conversation, l'utilisateur a peut-être répété le mot d'activation
            logger.info("Détection du mot d'activation pendant une conversation active")
            return
        
        logger.info("Mot d'activation détecté, début de la conversation")
        
        # Commencer une nouvelle conversation
        self.in_conversation = True
        self.last_activity = time.time()
        
        # Stocker l'audio initial
        self.conversation_audio = bytearray(initial_audio)
        
        # Arrêter la détection de mot d'activation
        self.hotword_detector.stop()
        
        # Démarrer l'enregistrement continu
        self._start_continuous_recording()
    
    def _start_continuous_recording(self):
        """Démarre l'enregistrement continu après détection du mot d'activation."""
        try:
            # Initialisation de PyAudio
            self.p = pyaudio.PyAudio()
            
            # Ouvrir le flux audio pour l'enregistrement continu
            self.stream = self.p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=self._continuous_audio_callback
            )
            
            logger.info("Enregistrement continu démarré")
            
            # Démarrer le timer d'inactivité
            self._check_activity()
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage de l'enregistrement continu: {str(e)}")
            self._end_conversation()
    
    def _continuous_audio_callback(self, in_data, frame_count, time_info, status):
        """
        Callback pour l'enregistrement continu.
        
        Args:
            in_data: Données audio brutes
            frame_count: Nombre de trames
            time_info: Informations de timing
            status: Statut de la capture
            
        Returns:
            Données et drapeau de continuation
        """
        if not self.in_conversation:
            return None, pyaudio.paAbort
        
        # Convertir les données audio
        audio_data = np.frombuffer(in_data, dtype=np.int16)
        
        # Détecter l'activité vocale (implémentation simple)
        if np.max(np.abs(audio_data)) > 2000:  # Seuil d'activité
            self.last_activity = time.time()
        
        # Ajouter l'audio à la conversation
        self.conversation_audio.extend(in_data)
        
        return in_data, pyaudio.paContinue
    
    def _check_activity(self):
        """Vérifie l'inactivité pour terminer la conversation."""
        if not self.in_conversation or not self.running:
            return
        
        # Vérifier si le délai d'inactivité est dépassé
        if time.time() - self.last_activity > self.conversation_timeout:
            logger.info(f"Fin de conversation après {self.conversation_timeout}s d'inactivité")
            self._end_conversation()
            return
        
        # Programmer la prochaine vérification
        self.timer_thread = threading.Timer(1.0, self._check_activity)
        self.timer_thread.daemon = True
        self.timer_thread.start()
    
    def _end_conversation(self):
        """Termine la conversation en cours."""
        if not self.in_conversation:
            return
        
        # Arrêter l'enregistrement
        if hasattr(self, 'stream') and self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        if hasattr(self, 'p') and self.p:
            self.p.terminate()
        
        # Appeler le callback avec l'audio complet
        if self.callback and len(self.conversation_audio) > 0:
            self.callback(bytes(self.conversation_audio))
        
        # Réinitialiser l'état
        self.in_conversation = False
        self.conversation_audio = bytearray()
        
        # Redémarrer la détection de mot d'activation
        if self.running:
            self.hotword_detector.start()
    
    def start(self):
        """Démarre le processeur vocal continu."""
        if self.running:
            logger.warning("Le processeur vocal est déjà en cours d'exécution")
            return
        
        self.running = True
        
        # Démarrer la détection de mot d'activation
        self.hotword_detector.start()
        
        logger.info(f"Processeur vocal continu démarré, en attente du mot d'activation '{self.hotword}'")
    
    def stop(self):
        """Arrête le processeur vocal continu."""
        if not self.running:
            return
        
        self.running = False
        
        # Arrêter la détection de mot d'activation
        self.hotword_detector.stop()
        
        # Terminer la conversation en cours
        if self.in_conversation:
            self._end_conversation()
        
        # Arrêter le timer
        if self.timer_thread:
            self.timer_thread.cancel()
        
        logger.info("Processeur vocal continu arrêté")
    
    def is_in_conversation(self) -> bool:
        """
        Indique si une conversation est en cours.
        
        Returns:
            True si en conversation, False sinon
        """
        return self.in_conversation

# Exemple d'utilisation
if __name__ == "__main__":
    # Configurer le logging
    logging.basicConfig(level=logging.INFO)
    
    # Callback de test
    def process_conversation(audio_data):
        print(f"Conversation terminée, {len(audio_data)} octets capturés")
        
        # Sauvegarder l'audio pour test
        with wave.open("conversation.wav", "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16 bits = 2 octets
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data)
        
        print("Audio sauvegardé dans conversation.wav")
    
    # Créer et démarrer le processeur vocal
    processor = ContinuousVoiceProcessor(
        hotword="ordinateur",  # Mot d'activation en français
        conversation_timeout=5,  # Timeout court pour test
        callback=process_conversation
    )
    
    processor.start()
    
    try:
        # Maintenir le programme actif
        print("Dites le mot d'activation ('ordinateur' ou 'computer')...")
        print("Appuyez sur Ctrl+C pour quitter")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Arrêt...")
    finally:
        processor.stop()