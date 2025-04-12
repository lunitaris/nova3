"""
Compétence de minuteurs et rappels pour l'assistant IA.
"""
import re
import time
import asyncio
import logging
from typing import Dict, List, Any

from models.skills.base import Skill

logger = logging.getLogger(__name__)

class TimerReminderSkill(Skill):
    """Compétence pour les minuteurs et rappels."""
    
    name = "timer_reminder"
    description = "Gère les minuteurs et rappels"
    examples = [
        "Règle un minuteur pour 5 minutes",
        "Rappelle-moi de sortir le poulet du four dans 45 minutes",
        "Mets une alarme pour 7h demain"
    ]
    
    # Stockage pour les minuteurs et rappels actifs
    timers = {}
    reminders = {}
    
    timer_keywords = ["minuteur", "compte à rebours", "chronomètre", "timer"]
    reminder_keywords = ["rappelle", "rappel", "souviens", "n'oublie pas"]
    
    async def can_handle(self, query: str, intent_data: Dict[str, Any]) -> float:
        """Vérifie si la requête concerne un minuteur ou un rappel."""
        query_lower = query.lower()
        
        # Vérifier l'intention détectée
        if intent_data.get("intent") == "timer" or intent_data.get("intent") == "reminder":
            return intent_data.get("confidence", 0.8)
        
        # Rechercher des mots-clés de minuteur
        for keyword in self.timer_keywords:
            if keyword in query_lower:
                return 0.9
        
        # Rechercher des mots-clés de rappel
        for keyword in self.reminder_keywords:
            if keyword in query_lower:
                return 0.9
        
        # Rechercher des patterns d'expression de temps
        time_patterns = [
            r"\b(\d+)\s*minutes?\b",
            r"\b(\d+)\s*heures?\b",
            r"\b(\d+)\s*secondes?\b",
            r"\bdemain\b",
            r"\bce soir\b"
        ]
        
        for pattern in time_patterns:
            if re.search(pattern, query_lower):
                return 0.7
        
        return 0.0
    
    async def handle(self, query: str, intent_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Traite une requête de minuteur ou rappel."""
        try:
            query_lower = query.lower()
            
            # Déterminer s'il s'agit d'un minuteur ou d'un rappel
            is_timer = any(keyword in query_lower for keyword in self.timer_keywords)
            is_reminder = any(keyword in query_lower for keyword in self.reminder_keywords)
            
            if is_timer or (not is_reminder and self._extract_duration(query_lower)):
                # Traiter un minuteur
                return await self._handle_timer(query, intent_data)
            elif is_reminder:
                # Traiter un rappel
                return await self._handle_reminder(query, intent_data)
            else:
                return {
                    "success": False,
                    "response": "Je n'ai pas compris si vous souhaitez un minuteur ou un rappel."
                }
        except Exception as e:
            logger.error(f"Erreur dans TimerReminderSkill: {str(e)}")
            return {
                "success": False,
                "response": "Désolé, je n'ai pas pu créer votre minuteur ou rappel.",
                "error": str(e)
            }
    
    async def _handle_timer(self, query: str, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Gère une demande de minuteur."""
        duration_seconds = self._extract_duration(query)
        
        if not duration_seconds:
            return {
                "success": False,
                "response": "Je n'ai pas compris la durée du minuteur."
            }
        
        # Créer un ID unique pour ce minuteur
        timer_id = f"timer_{len(self.timers) + 1}"
        
        # Calculer l'heure de fin
        end_time = time.time() + duration_seconds
        
        # Stocker le minuteur
        self.timers[timer_id] = {
            "end_time": end_time,
            "duration": duration_seconds,
            "created_at": time.time()
        }
        
        # Formater la durée pour l'affichage
        duration_str = self._format_duration(duration_seconds)
        
        # Simuler le déclenchement du minuteur (dans un vrai système, cela utiliserait un planificateur)
        if self.manager:
            asyncio.create_task(self._timer_task(timer_id, duration_seconds))
        
        return {
            "success": True,
            "response": f"Minuteur réglé pour {duration_str}.",
            "data": {
                "timer_id": timer_id,
                "duration": duration_seconds,
                "duration_str": duration_str,
                "end_time": end_time
            }
        }
    
    async def _handle_reminder(self, query: str, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Gère une demande de rappel."""
        # Extraire le contenu du rappel
        reminder_content = self._extract_reminder_content(query)
        
        if not reminder_content:
            return {
                "success": False,
                "response": "Je n'ai pas compris ce dont je dois vous rappeler."
            }
        
        # Extraire la durée
        duration_seconds = self._extract_duration(query)
        
        if not duration_seconds:
            return {
                "success": False,
                "response": "Je n'ai pas compris quand je dois vous rappeler."
            }
        
        # Créer un ID unique pour ce rappel
        reminder_id = f"reminder_{len(self.reminders) + 1}"
        
        # Calculer l'heure de déclenchement
        trigger_time = time.time() + duration_seconds
        
        # Stocker le rappel
        self.reminders[reminder_id] = {
            "content": reminder_content,
            "trigger_time": trigger_time,
            "duration": duration_seconds,
            "created_at": time.time()
        }
        
        # Formater la durée pour l'affichage
        duration_str = self._format_duration(duration_seconds)
        
        # Simuler le déclenchement du rappel
        if self.manager:
            asyncio.create_task(self._reminder_task(reminder_id, duration_seconds))
        
        return {
            "success": True,
            "response": f"D'accord, je vous rappellerai de {reminder_content} dans {duration_str}.",
            "data": {
                "reminder_id": reminder_id,
                "content": reminder_content,
                "duration": duration_seconds,
                "duration_str": duration_str,
                "trigger_time": trigger_time
            }
        }
    
    def _extract_duration(self, query: str) -> int:
        """
        Extrait la durée en secondes à partir de la requête.
        
        Args:
            query: Requête utilisateur
            
        Returns:
            Durée en secondes, ou 0 si non trouvée
        """
        # Rechercher des patterns de temps
        minutes_match = re.search(r"(\d+)\s*minutes?", query)
        hours_match = re.search(r"(\d+)\s*heures?", query)
        seconds_match = re.search(r"(\d+)\s*secondes?", query)
        
        total_seconds = 0
        
        if minutes_match:
            total_seconds += int(minutes_match.group(1)) * 60
        
        if hours_match:
            total_seconds += int(hours_match.group(1)) * 3600
        
        if seconds_match:
            total_seconds += int(seconds_match.group(1))
        
        # Si une durée précise a été trouvée, la retourner
        if total_seconds > 0:
            return total_seconds
        
        # Sinon, rechercher des expressions temporelles
        if "demain" in query:
            # Environ 24 heures
            return 24 * 3600
        
        if "ce soir" in query:
            # Supposons que "ce soir" est dans environ 6 heures (à ajuster selon l'heure actuelle)
            return 6 * 3600
        
        if "dans une heure" in query or "dans 1 heure" in query:
            return 3600
        
        if "dans une minute" in query or "dans 1 minute" in query:
            return 60
        
        # Pas de durée trouvée
        return 0
    
    def _extract_reminder_content(self, query: str) -> str:
        """
        Extrait le contenu du rappel à partir de la requête.
        
        Args:
            query: Requête utilisateur
            
        Returns:
            Contenu du rappel, ou chaîne vide si non trouvé
        """
        # Patterns pour extraire le contenu du rappel
        patterns = [
            r"rappelle-moi\s+(?:de\s+)?(.+?)(?:\s+dans|$)",
            r"rappel\s+(?:pour\s+)?(.+?)(?:\s+dans|$)",
            r"souviens-toi\s+(?:de\s+)?(.+?)(?:\s+dans|$)",
            r"n'oublie pas\s+(?:de\s+)?(.+?)(?:\s+dans|$)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                # Nettoyer la fin qui pourrait contenir des indications de temps
                content = re.sub(r'\s+(?:dans|après)\s+\d+\s+(?:minutes?|heures?|secondes?)$', '', content)
                return content
        
        # Si pas de pattern spécifique trouvé, tenter une approche générique
        # Supprimer les mots-clés de rappel et les expressions de temps
        clean_query = query.lower()
        for keyword in self.reminder_keywords:
            clean_query = clean_query.replace(keyword, '')
        
        # Supprimer les expressions de temps
        clean_query = re.sub(r'dans\s+\d+\s+(?:minutes?|heures?|secondes?)', '', clean_query)
        
        return clean_query.strip()
    
    def _format_duration(self, seconds: int) -> str:
        """
        Formate une durée en secondes en texte lisible.
        
        Args:
            seconds: Durée en secondes
            
        Returns:
            Durée formatée (ex: "5 minutes et 30 secondes")
        """
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        
        if hours == 1:
            parts.append("1 heure")
        elif hours > 1:
            parts.append(f"{hours} heures")
        
        if minutes == 1:
            parts.append("1 minute")
        elif minutes > 1:
            parts.append(f"{minutes} minutes")
        
        if seconds == 1:
            parts.append("1 seconde")
        elif seconds > 1:
            parts.append(f"{seconds} secondes")
        
        if not parts:
            return "0 seconde"
        
        if len(parts) == 1:
            return parts[0]
        
        return " et ".join([", ".join(parts[:-1]), parts[-1]])
    
    async def _timer_task(self, timer_id: str, duration: int):
        """
        Tâche asynchrone pour simuler le déclenchement d'un minuteur.
        
        Args:
            timer_id: ID du minuteur
            duration: Durée en secondes
        """
        try:
            # Attendre la durée spécifiée
            await asyncio.sleep(duration)
            
            # Vérifier si le minuteur existe toujours
            if timer_id in self.timers:
                logger.info(f"Minuteur {timer_id} terminé!")
                
                # Dans un système réel, on enverrait une notification
                # Ici, on se contente de mettre à jour l'état
                self.timers[timer_id]["status"] = "completed"
                
                # Supprimer le minuteur après un certain temps
                await asyncio.sleep(60)  # Garder pendant 1 minute
                if timer_id in self.timers:
                    del self.timers[timer_id]
        except asyncio.CancelledError:
            logger.info(f"Minuteur {timer_id} annulé")
        except Exception as e:
            logger.error(f"Erreur dans la tâche de minuteur {timer_id}: {str(e)}")
    
    async def _reminder_task(self, reminder_id: str, duration: int):
        """
        Tâche asynchrone pour simuler le déclenchement d'un rappel.
        
        Args:
            reminder_id: ID du rappel
            duration: Durée en secondes
        """
        try:
            # Attendre la durée spécifiée
            await asyncio.sleep(duration)
            
            # Vérifier si le rappel existe toujours
            if reminder_id in self.reminders:
                reminder = self.reminders[reminder_id]
                logger.info(f"Rappel {reminder_id} déclenché: {reminder['content']}")
                
                # Dans un système réel, on enverrait une notification
                # Ici, on se contente de mettre à jour l'état
                self.reminders[reminder_id]["status"] = "triggered"
                
                # Supprimer le rappel après un certain temps
                await asyncio.sleep(60)  # Garder pendant 1 minute
                if reminder_id in self.reminders:
                    del self.reminders[reminder_id]
        except asyncio.CancelledError:
            logger.info(f"Rappel {reminder_id} annulé")
        except Exception as e:
            logger.error(f"Erreur dans la tâche de rappel {reminder_id}: {str(e)}")