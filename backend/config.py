import os
from pydantic import BaseModel
from typing import Dict, List, Optional, Union
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

class ModelConfig(BaseModel):
    name: str
    api_base: str
    type: str  # "local" ou "cloud"
    priority: int  # Priorité d'utilisation (plus petit = plus prioritaire)
    latency_threshold: float  # Seuil de latence en secondes
    context_window: int  # Taille du contexte en tokens
    streaming: bool = True
    parameters: Dict[str, Union[str, int, float, bool]] = {}

class VoiceConfig(BaseModel):
    stt_model: str = "/opt/whisper.cpp/models/ggml-base.bin"
    stt_binary: str = "/opt/whisper.cpp/whisper-cli"
    stt_device: str = "cpu"  # Whisper.cpp utilise le CPU par défaut
    tts_model: str = "opt/piper/fr_FR-siwis-medium.onnx"
    tts_sample_rate: int = 22050

class MemoryConfig(BaseModel):
    vector_dimension: int = 1536  # Dimension des vecteurs FAISS
    max_history_length: int = 20  # Nombre maximal de messages dans l'historique
    synthetic_memory_refresh_interval: int = 10  # Intervalle de rafraîchissement de la mémoire synthétique

class SecurityConfig(BaseModel):
    enable_auth: bool = False
    jwt_secret: Optional[str] = None
    token_expire_minutes: int = 60 * 24  # 1 jour

class AppConfig(BaseModel):
    debug: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    models: Dict[str, ModelConfig] = {
        "fast": ModelConfig(
            name="gemma:2b",
            api_base="http://localhost:11434",
            type="local",
            priority=1,
            latency_threshold=1.0,
            context_window=4096,
            parameters={
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 512
            }
        ),
        "balanced": ModelConfig(
            name="zephyr",
            api_base="http://localhost:11434",
            type="local",
            priority=2,
            latency_threshold=3.0,
            context_window=8192,
            parameters={
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 1024
            }
        ),
        "cloud_fallback": ModelConfig(
            name="gpt-3.5-turbo",
            api_base="https://api.openai.com/v1",
            type="cloud",
            priority=3,
            latency_threshold=10.0,
            context_window=16384,
            parameters={
                "temperature": 0.7,
                "max_tokens": 2048
            }
        )
    }
    voice: VoiceConfig = VoiceConfig()
    memory: MemoryConfig = MemoryConfig()
    security: SecurityConfig = SecurityConfig()
    
    # Autres configurations générales
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    data_dir: str = os.getenv("DATA_DIR", "./data")

# Création de l'instance de configuration
config = AppConfig()

# Préparation du répertoire de données
os.makedirs(config.data_dir, exist_ok=True)
os.makedirs(os.path.join(config.data_dir, "memories"), exist_ok=True)
os.makedirs(os.path.join(config.data_dir, "conversations"), exist_ok=True)