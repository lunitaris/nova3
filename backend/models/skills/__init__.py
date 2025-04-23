"""
Module de compétences (skills) pour l'assistant IA.
"""
from backend.models.skills.base import Skill
from backend.models.skills.weather import WeatherSkill
from backend.models.skills.timer_reminder import TimerReminderSkill
from backend.models.skills.general_qa import GeneralQASkill
from backend.models.skills.manager import skills_manager

__all__ = [
    'Skill',
    'WeatherSkill',
    'HomeAutomationSkill',
    'TimerReminderSkill',
    'GeneralQASkill',
    'skills_manager'
]