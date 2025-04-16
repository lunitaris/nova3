import os
import logging
from logging.handlers import RotatingFileHandler
from backend.config import config  # déjà utilisé dans tes fichiers

# Créer le répertoire de logs si nécessaire
logs_dir = os.path.join(config.data_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)

# Configurer le logging global
logging.basicConfig(
    level=logging.DEBUG if config.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            os.path.join(logs_dir, "assistant.log"),
            maxBytes=10*1024*1024,  # 10 Mo
            backupCount=5
        ),
        logging.StreamHandler()  # Pour affichage console
    ]
)