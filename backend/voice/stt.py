import os
import logging
import tempfile
import asyncio
import subprocess
import json
from typing import Dict, Any

from config import config

logger = logging.getLogger(__name__)

class WhisperCppSTT:
    """
    Moteur de reconnaissance vocale utilisant Whisper.cpp
    """
    
    def __init__(self, 
                 model_path: str = None, 
                 binary_path: str = None):
        """
        Initialise le moteur Whisper.cpp
        
        Args:
            model_path: Chemin du modèle Whisper.cpp
            binary_path: Chemin de l'exécutable whisper-cli
        """
        # Chemins relatifs à la racine du projet
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        self.model_path = model_path or os.path.join(project_root, "opt", "whisper.cpp", "models", "ggml-base.bin")
        self.binary_path = binary_path or os.path.join(project_root, "opt", "whisper.cpp", "whisper-cli")
        
        # Vérifier la disponibilité
        self._check_whisper_binary()
    
    def _check_whisper_binary(self):
        """Vérifie la disponibilité de l'exécutable Whisper.cpp"""
        if not os.path.exists(self.binary_path):
            logger.warning(f"Whisper.cpp binaire non trouvé à {self.binary_path}")
            raise RuntimeError(f"Whisper.cpp binaire non trouvé à {self.binary_path}")
        
        if not os.path.exists(self.model_path):
            logger.warning(f"Modèle Whisper.cpp non trouvé à {self.model_path}")
            raise RuntimeError(f"Modèle Whisper.cpp non trouvé à {self.model_path}")
        
        # Vérifier les permissions d'exécution
        if not os.access(self.binary_path, os.X_OK):
            logger.warning(f"Le binaire n'est pas exécutable: {self.binary_path}")
            # Tenter de rendre exécutable
            try:
                os.chmod(self.binary_path, 0o755)
                logger.info(f"Permissions du binaire mises à jour: {self.binary_path}")
            except Exception as e:
                logger.error(f"Impossible de modifier les permissions: {e}")
                raise
    
    async def transcribe_file(self, audio_file: str) -> Dict[str, Any]:
        """
        Transcrit un fichier audio via Whisper.cpp
        
        Args:
            audio_file: Chemin du fichier audio à transcrire
        
        Returns:
            Dictionnaire de transcription
        """
        try:
            # Commande Whisper.cpp
            cmd = [
                self.binary_path, 
                "-m", self.model_path,  # Chemin du modèle
                "-f", audio_file,        # Fichier audio
                "-l", "fr",              # Langue forcée
                "-oj"                    # Sortie JSON
            ]
            
            # Exécution dans un thread séparé
            proc = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                logger.error(f"Erreur Whisper.cpp: {stderr.decode()}")
                return {"error": stderr.decode(), "text": ""}
            
            # Parser la sortie JSON
            result = json.loads(stdout.decode())
            
            # Extraire le texte transcrit
            transcription = result.get('text', '').strip()
            
            return {
                "text": transcription,
                "language": result.get('language', 'fr'),
                "confidence": result.get('confidence', 0.0)
            }
        
        except Exception as e:
            logger.error(f"Erreur de transcription Whisper.cpp: {str(e)}")
            return {"error": str(e), "text": ""}
    
    async def transcribe_audio_data(self, audio_data: bytes) -> Dict[str, Any]:
        """
        Transcrit des données audio brutes
        """
        try:
            # Écrire dans un fichier temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_path = temp_file.name
                temp_file.write(audio_data)
            
            # Transcrire
            result = await self.transcribe_file(temp_path)
            
            # Nettoyer
            os.unlink(temp_path)
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la transcription des données audio: {str(e)}")
            return {"error": str(e), "text": ""}

# Instance globale du moteur STT
stt_engine = WhisperCppSTT()