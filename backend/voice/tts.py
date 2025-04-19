import os
import logging
import subprocess
import tempfile
import asyncio
from typing import Optional, BinaryIO, Generator, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import io

from backend.config import config

logger = logging.getLogger(__name__)

class PiperTTS:
    """
    Gère la synthèse vocale avec Piper TTS.
    """
    
    def __init__(self, model_name: str = None, sample_rate: int = None):
        """
        Initialise le moteur Piper TTS.
        
        Args:
            model_name: Nom du modèle Piper à utiliser
            sample_rate: Taux d'échantillonnage audio
        """
        self.model_name = model_name or config.voice.tts_model
        self.sample_rate = sample_rate or config.voice.tts_sample_rate
        self.temp_dir = os.path.join(config.data_dir, "tts_temp")
        
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Vérifier l'installation de Piper
        self._check_piper_installation()
        
    def _check_piper_installation(self):
        """Vérifie si Piper est installé et disponible."""
        try:
            subprocess.run(["piper", "--help"], capture_output=True, check=False)
            logger.info("✅ Piper TTS correctement installé")
        except FileNotFoundError:
            logger.error("Piper TTS n'est pas installé ou n'est pas dans le PATH")
            logger.info("Veuillez installer Piper avec: pip install piper-tts")



    async def text_to_speech_file(self, text: str, output_file: str = None) -> str:
        """
        Convertit le texte en fichier audio.
        
        Args:
            text: Texte à convertir
            output_file: Chemin du fichier de sortie (optionnel)
            
        Returns:
            Chemin du fichier audio généré
        """
        if not text:
            logger.warning("Texte vide, génération TTS ignorée")
            return None
        
        # Créer un fichier temporaire si non spécifié
        if not output_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=self.temp_dir) as tmp:
                output_file = tmp.name
        
        try:
            # Préparer le fichier d'entrée texte
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt', dir=self.temp_dir) as text_file:
                text_file.write(text)
                text_path = text_file.name
            
            # Construire le chemin absolu du modèle
            # Remonter deux niveaux par rapport au fichier actuel (backend/voice/tts.py) pour atteindre la racine du projet
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
            model_name_with_ext = self.model_name if self.model_name.endswith('.onnx') else f"{self.model_name}.onnx"
            model_path = os.path.join(project_root, self.model_name)
            
            # Vérifier si le chemin existe
            if not os.path.exists(model_path) and not os.path.exists(model_path + ".onnx"):
                logger.error(f"Modèle Piper introuvable: {model_path}")
                logger.info(f"Tentative avec le chemin absolu: {model_path}")
                
                # Essayer différentes combinaisons de chemins
                potential_paths = [
                    model_path,  # tel quel
                    model_path + ".onnx",  # avec extension
                    os.path.join(project_root, "opt/piper", os.path.basename(self.model_name)),  # dans opt/piper/
                    os.path.join(project_root, "opt/piper", os.path.basename(self.model_name) + ".onnx")  # dans opt/piper/ avec extension
                ]
                
                for path in potential_paths:
                    if os.path.exists(path):
                        model_path = path
                        logger.info(f"Modèle trouvé à: {model_path}")
                        break
                else:
                    logger.error("Modèle introuvable après plusieurs tentatives")
                    return None
                    
            # Pour le debug
            logger.info(f"Utilisation du modèle: {model_path}")
            
            # Exécuter Piper dans un thread séparé
            cmd = [
                "piper",
                "--model", model_path,
                "--output_file", output_file
            ]
            
            # Log complet de la commande
            logger.info(f"Exécution de la commande: {' '.join(cmd)}")
            
            with ThreadPoolExecutor() as executor:
                process = await asyncio.get_event_loop().run_in_executor(
                    executor,
                    lambda: subprocess.run(cmd, check=True, capture_output=True, text=True, stdin=open(text_path))
                )
                
                # Log de la sortie pour le debug
                if process.stdout:
                    logger.info(f"Sortie Piper: {process.stdout}")
            
            # Nettoyer le fichier texte temporaire
            os.unlink(text_path)
            
            logger.info(f"Audio généré avec succès: {output_file}")
            return output_file
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur Piper (code {e.returncode}): {e.stderr if hasattr(e, 'stderr') else 'No stderr'}")
            # Nettoyer en cas d'erreur
            if 'text_path' in locals() and os.path.exists(text_path):
                os.unlink(text_path)
            if os.path.exists(output_file):
                os.unlink(output_file)
            return None
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération TTS: {str(e)}")
            # Nettoyer en cas d'erreur
            if 'text_path' in locals() and os.path.exists(text_path):
                os.unlink(text_path)
            if os.path.exists(output_file):
                os.unlink(output_file)
            return None





    async def stream_text_to_speech_pcm(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Convertit le texte en flux PCM pour streaming.
        
        Args:
            text: Texte à convertir
            
        Yields:
            Segments audio PCM
        """
        if not text:
            logger.warning("Texte vide, streaming TTS ignoré")
            return
        
        try:
            # Générer d'abord le fichier audio complet
            audio_file = await self.text_to_speech_file(text)
            
            if not audio_file:
                logger.error("Échec de la génération audio pour le streaming")
                return
            
            # Lire le fichier par morceaux et envoyer
            chunk_size = 4096  # Taille des morceaux à streamer
            
            with open(audio_file, 'rb') as f:
                # Ignorer l'en-tête WAV (44 octets)
                f.seek(44)
                
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
                    # Simuler un délai naturel de parole
                    await asyncio.sleep(len(chunk) / (self.sample_rate * 2 * 0.5))  # 0.5x speed pour parler plus vite
            
            # Nettoyer le fichier temporaire
            os.unlink(audio_file)
            
        except Exception as e:
            logger.error(f"Erreur lors du streaming TTS: {str(e)}")
            if 'audio_file' in locals() and os.path.exists(audio_file):
                os.unlink(audio_file)
    
    async def text_chunking(self, text: str, max_chars: int = 100) -> list[str]:
        """
        Découpe le texte en morceaux pour une synthèse optimale.
        
        Args:
            text: Texte à découper
            max_chars: Taille maximale des morceaux
            
        Returns:
            Liste des morceaux de texte
        """
        # Points de coupure naturels par ordre de priorité
        delimiters = ['. ', '! ', '? ', ';\n', ';\r\n', ';\r', '; ', ':\n', ':\r\n', ':\r', ': ', ',\n', ',\r\n', ',\r', ', ', '\n\n', '\r\n\r\n', '\n', '\r\n']
        
        chunks = []
        remaining_text = text.strip()
        
        while remaining_text:
            if len(remaining_text) <= max_chars:
                chunks.append(remaining_text)
                break
            
            # Trouver le meilleur point de coupure dans la limite de caractères
            chunk_end = max_chars
            delimiter_found = False
            
            for delimiter in delimiters:
                # Chercher le délimiteur le plus proche de la fin du chunk
                position = remaining_text[:max_chars].rfind(delimiter)
                if position != -1:
                    chunk_end = position + len(delimiter)
                    delimiter_found = True
                    break
            
            # Si aucun délimiteur n'est trouvé, couper au caractère max
            # mais chercher un espace pour éviter de couper un mot
            if not delimiter_found:
                space_pos = remaining_text[:max_chars].rfind(' ')
                if space_pos != -1 and space_pos > max_chars * 0.7:  # Au moins 70% de la limite
                    chunk_end = space_pos + 1
            
            # Ajouter le morceau
            chunks.append(remaining_text[:chunk_end])
            remaining_text = remaining_text[chunk_end:].strip()
        
        return chunks
    
    async def stream_long_text(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Convertit un texte long en streaming en le découpant en morceaux.
        
        Args:
            text: Texte long à convertir
            
        Yields:
            Segments audio PCM
        """
        # Découper le texte en morceaux gérables
        chunks = await self.text_chunking(text)
        
        for chunk in chunks:
            async for audio_data in self.stream_text_to_speech_pcm(chunk):
                yield audio_data
    
    async def generate_speech_for_streaming_response(
        self, 
        text_generator: AsyncGenerator[str, None]
    ) -> AsyncGenerator[bytes, None]:
        """
        Génère la parole à partir d'un générateur de texte (pour les réponses LLM en streaming).
        
        Args:
            text_generator: Générateur asynchrone de morceaux de texte
            
        Yields:
            Segments audio PCM
        """
        buffer = ""
        
        async for text_chunk in text_generator:
            buffer += text_chunk
            
            # Attendre d'avoir suffisamment de texte pour générer un segment audio
            if len(buffer) >= 50 or "." in buffer or "!" in buffer or "?" in buffer:
                # Trouver un point de coupure naturel
                cut_points = [buffer.rfind(c) for c in ['.', '!', '?', ',', ';', ':', '\n']]
                cut_point = max(cut_points)
                
                if cut_point > 0:
                    # Extraire le segment à synthétiser
                    segment = buffer[:cut_point+1].strip()
                    buffer = buffer[cut_point+1:].strip()
                    
                    # Générer et envoyer l'audio
                    async for audio_data in self.stream_text_to_speech_pcm(segment):
                        yield audio_data
        
        # Traiter le texte restant
        if buffer:
            async for audio_data in self.stream_text_to_speech_pcm(buffer):
                yield audio_data

# Instance globale du moteur TTS
tts_engine = PiperTTS()