# Assistant IA Local

Nova3 est un assistant vocal intelligent qui fonctionne en local, avec interface web, mémoire vectorielle et capacités vocales.

## Fonctionnalités

- **Interface Web** intuitive et responsive
- **Mode Chat** pour les interactions textuelles
- **Mode Vocal** avec reconnaissance et synthèse vocale
- **Mémoire vectorielle** pour se souvenir des conversations
- **Délégation de modèles** - utilise des modèles plus légers pour les réponses simples, et des modèles plus puissants si nécessaire
- **Architecture modulaire** extensible

## Prérequis

- [Ollama](https://ollama.com/) pour les modèles LLM locaux
- Environ 5 Go d'espace disque minimum pour les modèles de base
- Python3.10

## Installation rapide

### 1. Cloner le dépôt

```bash
git clone https://github.com/lunitaris/nova3
cd nova3
```

### 2. Télécharger les modèles Ollama requis

```bash
ollama pull gemma:2b
ollama pull zephyr
```

### 3. Démarrer avec Docker Compose

```bash
docker-compose up -d
```

L'assistant sera accessible à l'adresse: [http://localhost:3000](http://localhost:3000)

## Installation manuelle (sans Docker)

### 1. Prérequis

- Python 3.10+
- Node.js 16+ (optionnel, seulement pour le développement frontend)
- Ollama installé et en cours d'exécution
- FFmpeg installé

### 2. Backend Install

En premier, setup le venv à la racine du projet:
```bash
python3.10 -m venv venv
source venv/bin/activate
```

#### 2.1 Install python requirements
From root folder:
```bash
cd backend
pip install -r requirements.txt
```

#### 2.2 Download Piper's model files for vocal synthese

```bash
# From root folder
mkdir -p ./opt/piper/
cd ./opt/piper/
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR-siwis-medium/fr_FR-siwis-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR-siwis-medium/fr_FR-siwis-medium.onnx.json
```

#### 2.3 Place Whisper.cpp binary and models

```bash
# From root folder
mkdir -p ./opt/whisper.cpp/models
```
1. Compile whisper.cpp on your system
2. Place binary 'whisper-cli' to: $ROOT_PROJECT/opt/whisper.cpp/whisper-cli
3. Download models (ggml-base.bin / ggml-medium.bin) to $ROOT_PROJECT/opt/whisper.cpp/models/


---

# Démarrer le backend

```bash
# From root folder
# Make sure you activated venv before (and installed all requirements)
python -m backend.main
```

### 3. Servir le frontend

Le moyen le plus simple est d'utiliser un serveur HTTP simple :

```bash
# From root folder
cd frontend
# Avec Python
python -m http.server 3000
# Ou avec Node.js
npx serve -s . -p 3000
```



Nova3 sera accessible à l'adresse: [http://localhost:3000](http://localhost:3000).

## Configuration

### Configuration du backend (config.py)

Le fichier `backend/config.py` contient les paramètres principaux de l'application :

- **Modèles LLM** : modifiez les configurations pour utiliser vos propres modèles Ollama
- **Voix TTS** : configurez les voix et paramètres de synthèse vocale
- **Paramètres de mémoire** : ajustez la taille et les paramètres de la mémoire vectorielle
- **Sécurité** : activez l'authentification si nécessaire

### Configuration du frontend (scripts/config.js)

Le fichier `frontend/scripts/config.js` contient les paramètres du frontend :

- **URL API** : modifiez-les si vous hébergez le backend sur un autre serveur
- **Préférences par défaut** : thème, voix, et autres paramètres

## Utilisation

### Mode Chat

1. Écrivez votre message dans la zone de texte
2. Appuyez sur Entrée ou cliquez sur le bouton d'envoi
3. L'assistant répondra avec du texte

### Mode Vocal

1. Cliquez sur le bouton "Mode Vocal" en bas de l'écran
2. Appuyez sur le bouton microphone et parlez
3. Relâchez le bouton quand vous avez terminé
4. L'assistant transcrira votre message et répondra vocalement

### Mémorisation

Pour que l'assistant mémorise une information spécifique :

1. Écrivez "souviens-toi que [information]" ou utilisez le bouton "Mémoriser"
2. L'assistant stockera cette information dans sa mémoire vectorielle
3. Il pourra la rappeler plus tard lorsqu'elle sera pertinente pour répondre à vos questions

## Architecture

L'application est divisée en plusieurs composants principaux :

### Backend
- **FastAPI** : serveur API REST et WebSocket
- **LangChain** : orchestration des modèles et agents
- **FAISS** : index vectoriel pour la mémorisation
- **Whisper** : reconnaissance vocale
- **Piper** : synthèse vocale
- **Ollama** : modèles de langage locaux

### Frontend
- **HTML/CSS/JS** : interface utilisateur simple et réactive
- **WebSockets** : communication en temps réel avec le backend
- **Web Audio API** : enregistrement et lecture audio

## Extension et personnalisation

### Ajouter de nouveaux modèles LLM

Modifiez `config.py` pour ajouter de nouveaux modèles dans la section `models` :

```python
"nouveau_modele": ModelConfig(
    name="nom-du-modele-ollama",
    api_base="http://localhost:11434",
    type="local",
    priority=2,
    latency_threshold=2.0,
    context_window=8192,
    parameters={
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 1024
    }
)
```

### Ajouter de nouvelles voix

1. Téléchargez de nouvelles voix Piper depuis https://huggingface.co/rhasspy/piper-voices
2. Placez-les dans le répertoire des voix Piper
3. Mettez à jour l'interface pour inclure ces nouvelles voix

## Dépannage

### Le backend ne démarre pas

- Vérifiez que Ollama est bien en cours d'exécution
- Vérifiez que les modèles nécessaires ont été téléchargés (`gemma:2b` et `zephyr`)
- Démerde toi ou pose ta question ;)

### Problèmes avec la reconnaissance vocale

- Assurez-vous que votre navigateur a accès au microphone (vérifiez les permissions)
- Vérifiez que FFmpeg est correctement installé
- Si vous utilisez un VPN ou un proxy, cela peut interférer avec les WebSockets

### Problèmes de synthèse vocale

- Vérifiez que les modèles Piper ont été correctement téléchargés
- Vérifiez les logs pour des erreurs spécifiques

## Licence

Ce projet est sous licence MIT.


## 2do

A faire:



## Remerciements

Ce projet utilise plusieurs technologies open-source :
- [Ollama](https://ollama.com/) pour l'inférence LLM locale
- [Whisper](https://github.com/openai/whisper) pour la reconnaissance vocale
- [Piper TTS](https://github.com/rhasspy/piper) pour la synthèse vocale
- [FastAPI](https://fastapi.tiangolo.com/) pour le backend
- [FAISS](https://faiss.ai/) pour l'indexation vectorielle