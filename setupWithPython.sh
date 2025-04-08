#!/bin/bash


echo "Installing python venv..."
python3.10 -m venv venv
source venv/bin/activate

echo "Installing Python requirements..."

pip install pip-tools   # Pour créer le fichier requirements.txt proprement si besoin 

cd backend
pip install -r requirements.txt

####### SERA MODIFIE PLUS TARD CAR ON VA UTILISER WHISPER.CPP
echo "Downloading Piper Voices models..."
mkdir -p ~/.local/share/piper-voices/
cd ~/.local/share/piper-voices/
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR-siwis-medium/fr_FR-siwis-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR-siwis-medium/fr_FR-siwis-medium.onnx.json
echo "Setup done"


echo ""
echo ""
echo "Please open 2 terminals to start Backend & Frontend!"
echo "source venv/bin/activate"

echo "cd backend  && python main.py"
echo "cd frontend && python -m http.server 3000"