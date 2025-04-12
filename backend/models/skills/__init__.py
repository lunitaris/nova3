"""
Module de compétences (skills) pour l'assistant IA.
"""
from models.skills.base import Skill
from models.skills.weather import WeatherSkill
from models.skills.home_automation import HomeAutomationSkill
from models.skills.timer_reminder import TimerReminderSkill
from models.skills.general_qa import GeneralQASkill
from models.skills.manager import skills_manager

__all__ = [
    'Skill',
    'WeatherSkill',
    'HomeAutomationSkill',
    'TimerReminderSkill',
    'GeneralQASkill',
    'skills_manager'
]