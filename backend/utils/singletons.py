# backend/utils/singletons.py

# -----------------------------------------------
# Initialisation du moteur TTS Piper
# -----------------------------------------------
from backend.voice.tts import PiperTTS
tts_engine = PiperTTS()

# -----------------------------------------------
# Initialisation du moteur STT Whisper.cpp
# -----------------------------------------------
from backend.voice.stt import WhisperCppSTT
stt_engine = WhisperCppSTT()

# -----------------------------------------------
# Initialisation différée du contrôleur domotique partagé
# -----------------------------------------------
shared_skill = None
hue_controller = None

def init_shared_skill():
    global shared_skill, hue_controller
    if shared_skill is None:
        from backend.models.skills.home_automation import HomeAutomationSkill  # ← IMPORT DIFFÉRÉ
        shared_skill = HomeAutomationSkill()
        hue_controller = shared_skill.hue_controller
