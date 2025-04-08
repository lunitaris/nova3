import os
import logging
import tempfile
import asyncio
from typing import Optional, BinaryIO, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import whisper
import numpy as np
import torch

from config import config

logger = logging.getLogger(__name__)



### DESACTIVATION DE TOUTES ACCELERATIONS MATERIELLES POSSIBLES (FOPRCE MODE CPU)
if torch.backends.mps.is_available():
    logger.warning("Désactivation de MPS pour éviter les erreurs de segmentation sur macOS.")
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "0"
    torch.backends.mps.is_available = lambda: False
#############################################################################################

class WhisperSTT:
    """
    Classe pour la reconnaissance vocale avec OpenAI Whisper.
    """
    
    def __init__(self, model_name: str = None, device: str = None):
        """
        Initialise le moteur de reconnaissance vocale Whisper.
        
        Args:
            model_name: Taille du modèle Whisper ("tiny", "base", "small", "medium", "large")
            device: Appareil à utiliser ("cpu" ou "cuda")
        """
        self.model_name = model_name or config.voice.stt_model
        self.device = device or config.voice.stt_device
        self.temp_dir = os.path.join(config.data_dir, "stt_temp")
        self.model = None
        
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Vérifier le device
        if self.device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA demandé mais non disponible. Utilisation du CPU à la place.")
            self.device = "cpu"
        
        # Charger le modèle
        self._load_model()
    
    def _load_model(self):
        """Charge le modèle Whisper."""
        try:
            logger.info(f"Chargement du modèle Whisper '{self.model_name}' sur {self.device}")
            self.model = whisper.load_model(self.model_name, device=self.device)
            logger.info("Modèle Whisper chargé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle Whisper: {str(e)}")
            raise RuntimeError(f"Impossible de charger le modèle Whisper: {str(e)}")
    
    async def transcribe_file(self, audio_file: str) -> Dict[str, Any]:
        """
        Transcrit un fichier audio.
        
        Args:
            audio_file: Chemin du fichier audio à transcrire
            
        Returns:
            Dictionnaire contenant la transcription et les métadonnées
        """
        if not self.model:
            self._load_model()
        
        try:
            # Exécuter la transcription dans un thread séparé pour ne pas bloquer
            with ThreadPoolExecutor() as executor:
                result = await asyncio.get_event_loop().run_in_executor(
                    executor,
                    lambda: self.model.transcribe(audio_file, language="fr")
                )
            
            logger.info(f"Transcription réussie: {result.get('text', '')[:50]}...")
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la transcription audio: {str(e)}")
            return {"error": str(e), "text": ""}
    
    async def transcribe_audio_data(self, audio_data: bytes, sample_rate: int = 16000) -> Dict[str, Any]:
        """
        Transcrit des données audio brutes.
        
        Args:
            audio_data: Données audio au format brut (PCM)
            sample_rate: Taux d'échantillonnage des données audio
            
        Returns:
            Dictionnaire contenant la transcription et les métadonnées
        """
        if not self.model:
            self._load_model()
        
        try:
            # Écrire dans un fichier temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=self.temp_dir) as temp_file:
                temp_path = temp_file.name
                temp_file.write(audio_data)
            
            # Transcrire le fichier
            result = await self.transcribe_file(temp_path)
            
            # Nettoyer
            os.unlink(temp_path)
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la transcription des données audio: {str(e)}")
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
            return {"error": str(e), "text": ""}
    
    async def stream_transcribe(self, audio_generator) -> Dict[str, Any]:
        """
        Transcrit un flux audio en recevant les morceaux progressivement.
        
        Args:
            audio_generator: Générateur ou AsyncGenerator produisant des morceaux audio
            
        Returns:
            Dictionnaire contenant la transcription finale
        """
        try:
            # Créer un fichier temporaire pour stocker le flux audio
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=self.temp_dir) as temp_file:
                temp_path = temp_file.name
                
                # Écrire l'en-tête WAV (format PCM 16-bit, mono, 16kHz)
                sample_rate = 16000
                channels = 1
                bits_per_sample = 16
                
                # En-tête WAV
                temp_file.write(b'RIFF')
                temp_file.write(b'\x00\x00\x00\x00')  # Taille (à mettre à jour à la fin)
                temp_file.write(b'WAVE')
                
                # Format chunk
                temp_file.write(b'fmt ')
                temp_file.write((16).to_bytes(4, byteorder='little'))  # Taille du chunk fmt
                temp_file.write((1).to_bytes(2, byteorder='little'))   # Format (1 = PCM)
                temp_file.write(channels.to_bytes(2, byteorder='little'))
                temp_file.write(sample_rate.to_bytes(4, byteorder='little'))
                temp_file.write((sample_rate * channels * bits_per_sample // 8).to_bytes(4, byteorder='little'))  # Byte rate
                temp_file.write((channels * bits_per_sample // 8).to_bytes(2, byteorder='little'))  # Block align
                temp_file.write(bits_per_sample.to_bytes(2, byteorder='little'))
                
                # Data chunk
                temp_file.write(b'data')
                temp_file.write(b'\x00\x00\x00\x00')  # Taille des données (à mettre à jour)
                
                # Position où écrire la taille des données audio
                data_size_pos = temp_file.tell() - 4
                
                # Écrire le flux audio
                data_size = 0
                
                if asyncio.iscoroutinefunction(audio_generator.__anext__):
                    # Pour les AsyncGenerator
                    async for chunk in audio_generator:
                        temp_file.write(chunk)
                        data_size += len(chunk)
                else:
                    # Pour les générateurs classiques
                    for chunk in audio_generator:
                        temp_file.write(chunk)
                        data_size += len(chunk)
                
                # Mettre à jour les tailles dans l'en-tête
                temp_file.seek(4)
                temp_file.write((data_size + 36).to_bytes(4, byteorder='little'))  # Taille RIFF
                
                temp_file.seek(data_size_pos)
                temp_file.write(data_size.to_bytes(4, byteorder='little'))  # Taille DATA
            
            # Transcrire le fichier complet
            result = await self.transcribe_file(temp_path)
            
            # Nettoyer
            os.unlink(temp_path)
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la transcription du flux audio: {str(e)}")
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
            return {"error": str(e), "text": ""}
    
    async def transcribe_chunks(self, chunks, max_chunk_duration: float = 30.0):
        """
        Transcrit des morceaux audio avec détection de segments.
        Utile pour les enregistrements longs divisés en morceaux.
        
        Args:
            chunks: Liste de chemins de fichiers audio ou de données audio
            max_chunk_duration: Durée maximale d'un segment en secondes
            
        Returns:
            Texte transcrit complet
        """
        if not chunks:
            return {"text": ""}
        
        # Si un seul morceau, transcription directe
        if len(chunks) == 1:
            if isinstance(chunks[0], str):
                return await self.transcribe_file(chunks[0])
            else:
                return await self.transcribe_audio_data(chunks[0])
        
        # Transcription par morceaux
        transcriptions = []
        
        for chunk in chunks:
            if isinstance(chunk, str):
                result = await self.transcribe_file(chunk)
            else:
                result = await self.transcribe_audio_data(chunk)
            
            if "text" in result:
                transcriptions.append(result["text"])
        
        # Fusionner les transcriptions
        full_text = " ".join(transcriptions)
        
        return {"text": full_text}

# Instance globale du moteur STT
stt_engine = WhisperSTT()