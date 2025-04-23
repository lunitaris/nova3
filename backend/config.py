import os
from pydantic import BaseModel
from typing import Dict, List, Optional, Union
from dotenv import load_dotenv

# Chargement des variables d'environnement (tous les .env)
load_dotenv(dotenv_path="config_API.env")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

class ModelConfig(BaseModel):
    name: str
    api_base: str
    type: str  # "local" ou "cloud"
    priority: int
    latency_threshold: float
    context_window: int
    streaming: bool = True
    parameters: Dict[str, Union[str, int, float, bool]] = {}

class VoiceConfig(BaseModel):
    stt_model: str = "/opt/whisper.cpp/models/ggml-base.bin"
    stt_binary: str = "/opt/whisper.cpp/whisper-cli"
    stt_device: str = "cpu"
    tts_model: str = "opt/piper/fr_FR-siwis-medium.onnx"
    tts_sample_rate: int = 22050

class MemoryConfig(BaseModel):
    vector_dimension: int = 1536
    max_history_length: int = 20
    synthetic_memory_refresh_interval: int = 10
    use_chatgpt_for_symbolic_memory: bool = True
    nlist: int = 25

class SecurityConfig(BaseModel):
    enable_auth: bool = False
    jwt_secret: Optional[str] = None
    token_expire_minutes: int = 60 * 24

class AppConfig(BaseModel):
    debug: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    models: Dict[str, ModelConfig] = {
        "fast": ModelConfig(
            name="zephyr",
            api_base="http://localhost:11434",
            type="local",
            priority=1,
            latency_threshold=1.0,
            context_window=4096,
            parameters={
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 1024
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
                "max_tokens": 2048
            }
        )
    }
    voice: VoiceConfig = VoiceConfig()
    memory: MemoryConfig = MemoryConfig()
    security: SecurityConfig = SecurityConfig()
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    data_dir: str = os.getenv("DATA_DIR", "./data")

# Création de l'instance de configuration
config = AppConfig()

# Préparation des répertoires
os.makedirs(config.data_dir, exist_ok=True)
os.makedirs(os.path.join(config.data_dir, "memories"), exist_ok=True)
os.makedirs(os.path.join(config.data_dir, "conversations"), exist_ok=True)