# backend/utils/singletons.py

# Initialisation du Hue Controller
from backend.models.skills.home_automation import HomeAutomationSkill
shared_skill = HomeAutomationSkill()
hue_controller = shared_skill.hue_controller


# Initialisation du moteur TTS Piper
from backend.voice.tts import PiperTTS
tts_engine = PiperTTS()

# Initialisation du moteur STT Whisper.cpp
from backend.voice.stt import WhisperCppSTT
stt_engine = WhisperCppSTT()