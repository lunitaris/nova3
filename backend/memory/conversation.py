import os
import json
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
import time


from backend.config import config
from backend.memory.synthetic_memory import synthetic_memory
from backend.memory.enhanced_symbolic_memory import enhanced_symbolic_memory
from backend.models.model_manager import model_manager
from backend.models.langchain_manager import langchain_manager
from backend.memory.vector_store import vector_store
from backend.memory.personal_extractor import ConversationMemoryProcessor
from backend.utils.profiler import profile
from backend.memory.smart_router import smart_router




logger = logging.getLogger(__name__)

class Conversation:
    """
    Gère une conversation avec un utilisateur, incluant l'historique et les métadonnées.
    """
    
    def __init__(self, conversation_id: str = None, user_id: str = "anonymous"):
        """
        Initialise ou charge une conversation.
        
        Args:
            conversation_id: ID de la conversation existante à charger
            user_id: ID de l'utilisateur
        """
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.user_id = user_id
        self.messages = []

        # Système de verrouillage pour éviter les extractions multiples
        self._memory_extraction_locks = {}

        self.metadata = {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "title": "Nouvelle conversation",
            "summary": "",
            "topic": "general",
            "tags": []
        }
        self._memory_extraction_locks = {}


        # Initialiser le gestionnaire de mémoire personnelle
        self.memory_processor = ConversationMemoryProcessor(
            model_manager, vector_store, enhanced_symbolic_memory
        )

        
        # Chemin du fichier de conversation
        self.file_path = os.path.join(
            config.data_dir, 
            "conversations", 
            f"{self.conversation_id}.json"
        )
        
        # Si un ID est fourni, tenter de charger la conversation
        if conversation_id:
            self._load_conversation()
        else:
            # Nouvelle conversation, sauvegarder immédiatement
            self._save_conversation()
    
    def _load_conversation(self):
        """Charge une conversation existante depuis le stockage."""
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.messages = data.get("messages", [])
                    self.metadata = data.get("metadata", self.metadata)
                    self.user_id = data.get("user_id", self.user_id)
                    logger.info(f"Conversation {self.conversation_id} chargée avec {len(self.messages)} messages")
            else:
                logger.warning(f"Conversation {self.conversation_id} non trouvée, création d'une nouvelle")
                self._save_conversation()
        except Exception as e:
            logger.error(f"Erreur lors du chargement de la conversation {self.conversation_id}: {str(e)}")
            self._save_conversation()
    
    def _save_conversation(self):
        """Sauvegarde la conversation dans le stockage."""
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            
            # Mettre à jour la date de modification
            self.metadata["updated_at"] = datetime.now().isoformat()
            
            # Préparer les données
            data = {
                "conversation_id": self.conversation_id,
                "user_id": self.user_id,
                "messages": self.messages,
                "metadata": self.metadata
            }
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"Conversation {self.conversation_id} sauvegardée")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la conversation {self.conversation_id}: {str(e)}")
    


    def add_message(self, content: str, role: str = "user", metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Ajoute un message à la conversation.
        
        Args:
            content: Contenu du message
            role: Rôle de l'expéditeur ("user" ou "assistant")
            metadata: Métadonnées additionnelles du message
            
        Returns:
            Le message ajouté
        """
        message_id = str(uuid.uuid4())
        message = {
            "id": message_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.messages.append(message)
        
        # Limiter la taille de l'historique si nécessaire
        max_history = config.memory.max_history_length
        if len(self.messages) > max_history:
            # Avant de tronquer, synthétiser la mémoire des messages anciens
            asyncio.create_task(self._synthesize_old_messages())
            # Garder seulement les messages les plus récents
            self.messages = self.messages[-max_history:]
        
        # Mettre à jour et sauvegarder
        self.metadata["updated_at"] = datetime.now().isoformat()
        self._save_conversation()
        
        # Si c'est un message utilisateur, mettre à jour la mémoire symbolique
        if role == "user":
            # Passer l'ID du message pour le verrouillage
            asyncio.create_task(self._update_enhanced_symbolic_memory(content, message_id))
        
        return message

    @profile("symbolic_update")
    async def _update_enhanced_symbolic_memory(self, content: str, message_id: str = None):
        """
        Met à jour la mémoire symbolique avec le contenu du message.
        Utilise un verrouillage pour éviter les extractions multiples.
        
        Args:
            content: Contenu du message
            message_id: ID du message pour le verrouillage
        """
        try:
            # Uniquement traiter les messages suffisamment longs
            if len(content.split()) < 5:
                return

            # Générer un ID de verrouillage basé sur le contenu si non fourni
            lock_id = message_id or f"msg_{hash(content)}"
            
            # Vérifier si ce message est déjà en cours de traitement
            if lock_id in self._memory_extraction_locks:
                logger.info(f"⏭️ Extraction symbolique déjà en cours pour message {lock_id[:10]}, ignorée")
                return
            
            # Marquer comme en cours de traitement
            self._memory_extraction_locks[lock_id] = True
            
            try:
                logger.info(f"🔒 Mise à jour de la mémoire symbolique pour la conversation {self.conversation_id} (lock: {lock_id[:10]})")
                update_stats = await enhanced_symbolic_memory.update_graph_from_text(content)
                
                if update_stats.get("entities_added", 0) > 0 or update_stats.get("relations_added", 0) > 0:
                    logger.info(f"✅ Graph mis à jour: {update_stats.get('entities_added', 0)} entités, {update_stats.get('relations_added', 0)} relations")
            finally:
                # Toujours nettoyer le verrou, même en cas d'erreur
                if lock_id in self._memory_extraction_locks:
                    del self._memory_extraction_locks[lock_id]
                    logger.debug(f"🔓 Verrou d'extraction libéré: {lock_id[:10]}")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la mise à jour de la mémoire symbolique: {str(e)}")


    async def _synthesize_old_messages(self):
        """Synthétise les messages anciens avant qu'ils ne soient supprimés."""
        try:
            # Prendre les 10 premiers messages ou moins
            old_messages = self.messages[:10]
            if len(old_messages) < 3:  # Pas assez de messages pour synthétiser
                return
            
            # Synthétiser les messages
            await synthetic_memory.synthesize_conversation(
                old_messages, 
                topic=self.metadata.get("topic", "general")
            )
            
            logger.info(f"Messages anciens de la conversation {self.conversation_id} synthétisés")
        except Exception as e:
            logger.error(f"Erreur lors de la synthèse des messages anciens: {str(e)}")
    
    async def generate_title(self) -> str:
        """
        Génère un titre pour la conversation basé sur son contenu.
        
        Returns:
            Titre généré
        """
        try:
            # Vérifier s'il y a assez de messages
            if len(self.messages) < 2:
                return "Nouvelle conversation"
            
            # Extraire les premiers messages (3 max)
            sample_messages = self.messages[:3]
            formatted_messages = "\n".join([
                f"{'Utilisateur' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in sample_messages
            ])
            
            # Prompt pour générer le titre
            prompt = f"""Voici le début d'une conversation:

{formatted_messages}

Génère un titre court (5 mots maximum) qui résume le sujet principal de cette conversation.
Réponds uniquement avec le titre, sans guillemets ni ponctuation supplémentaire."""
            
            # Générer le titre avec un modèle léger ## AMELIORATION POSSIBLE
            title = await model_manager.generate_response(prompt, complexity="low")
                
            
            # Nettoyer et limiter la longueur
            title = title.strip().strip('"\'').strip()
            if len(title) > 50:
                title = title[:47] + "..."
            
            # Mettre à jour et sauvegarder
            self.metadata["title"] = title
            self._save_conversation()
            
            logger.info(f"Titre généré pour la conversation {self.conversation_id}: {title}")
            return title
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du titre: {str(e)}")
            return "Conversation"
    
    async def generate_summary(self) -> str:
        """
        Génère un résumé de la conversation.
        
        Returns:
            Résumé généré
        """
        try:
            # Vérifier s'il y a assez de messages
            if len(self.messages) < 3:
                return ""
            
            # Pour les conversations longues, échantillonner
            max_messages = 10
            if len(self.messages) > max_messages:
                # Prendre le début, le milieu et la fin
                start = self.messages[:3]
                middle = self.messages[len(self.messages)//2 - 1:len(self.messages)//2 + 2]
                end = self.messages[-3:]
                sample_messages = start + middle + end
            else:
                sample_messages = self.messages
            
            # Formater les messages
            formatted_messages = "\n".join([
                f"{'Utilisateur' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in sample_messages
            ])
            
            # Prompt pour générer le résumé
            prompt = f"""Voici une conversation entre un utilisateur et un assistant:

{formatted_messages}

Génère un résumé concis (2-3 phrases) qui capture l'essence de cette conversation.
Résumé:"""
            
            # Générer le résumé
            if len(self.messages) > 4:
                summary = await model_manager.generate_response(prompt, complexity="medium")

            
            # Mettre à jour et sauvegarder
            self.metadata["summary"] = summary
            self._save_conversation()
            
            logger.info(f"Résumé généré pour la conversation {self.conversation_id}")
            return summary
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du résumé: {str(e)}")
            return ""
    
    def clear_history(self):
        """Efface l'historique de la conversation tout en conservant les métadonnées."""
        try:
            # Sauvegarder la synthèse avant de supprimer
            if len(self.messages) > 0:
                asyncio.create_task(synthetic_memory.synthesize_conversation(
                    self.messages,
                    topic=self.metadata.get("topic", "general")
                ))
            
            self.messages = []
            self.metadata["updated_at"] = datetime.now().isoformat()
            self._save_conversation()
            
            logger.info(f"Historique de la conversation {self.conversation_id} effacé")
        except Exception as e:
            logger.error(f"Erreur lors de l'effacement de l'historique: {str(e)}")
    
    def get_messages(self, limit: int = None, include_metadata: bool = False) -> List[Dict[str, Any]]:
        """
        Récupère les messages de la conversation.
        
        Args:
            limit: Nombre maximal de messages à retourner
            include_metadata: Si True, inclut les métadonnées
            
        Returns:
            Liste des messages
        """
        messages = self.messages
        
        if limit:
            messages = messages[-limit:]
        
        if not include_metadata:
            # Filtrer les métadonnées des messages
            messages = [{k: v for k, v in msg.items() if k != 'metadata'} for msg in messages]
        
        return messages
    
    def get_context_for_model(self, max_messages: int = None) -> str:
        """
        Prépare le contexte de conversation pour le modèle.
        
        Args:
            max_messages: Nombre maximal de messages à inclure
            
        Returns:
            Contexte formaté pour le modèle
        """
        # Limiter le nombre de messages si spécifié
        messages = self.messages
        if max_messages:
            messages = messages[-max_messages:]
        
        # Formater pour le modèle
        formatted_messages = []
        for msg in messages:
            prefix = "Utilisateur: " if msg["role"] == "user" else "Assistant: "
            formatted_messages.append(f"{prefix}{msg['content']}")
        
        return "\n".join(formatted_messages)

class ConversationManager:
    """
    Gère toutes les conversations et fournit des méthodes pour y accéder.
    """
    
    def __init__(self):
        """Initialise le gestionnaire de conversations."""
        self.conversations = {}  # Cache des conversations actives
        self.conversations_dir = os.path.join(config.data_dir, "conversations")
        os.makedirs(self.conversations_dir, exist_ok=True)
        
        # C'EST ICI QU'IL FAUT AJOUTER LE CODE :
        # Initialiser le gestionnaire de mémoire personnelle
        self.memory_processor = ConversationMemoryProcessor(
            model_manager, vector_store, enhanced_symbolic_memory
        )
    


    def get_conversation(self, conversation_id: str = None, user_id: str = "anonymous") -> Conversation:
        """
        Récupère ou crée une conversation.
        
        Args:
            conversation_id: ID de la conversation à récupérer
            user_id: ID de l'utilisateur
            
        Returns:
            Instance de Conversation
        """
        # Si pas d'ID spécifié, créer une nouvelle conversation
        if not conversation_id:
            conversation = Conversation(user_id=user_id)
            self.conversations[conversation.conversation_id] = conversation
            return conversation
        
        # Vérifier si la conversation est déjà en cache
        if conversation_id in self.conversations:
            return self.conversations[conversation_id]
        
        # Charger la conversation
        conversation = Conversation(conversation_id=conversation_id, user_id=user_id)
        self.conversations[conversation_id] = conversation
        
        return conversation
    
    def list_conversations(self, user_id: str = None, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Liste les conversations disponibles.
        
        Args:
            user_id: Filtre optionnel par utilisateur
            limit: Nombre maximal de conversations à retourner
            offset: Index de départ pour la pagination
            
        Returns:
            Liste des métadonnées de conversation
        """
        try:
            # Lister tous les fichiers de conversation
            conversation_files = []
            for filename in os.listdir(self.conversations_dir):
                if filename.endswith(".json"):
                    file_path = os.path.join(self.conversations_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                            # Filtrer par utilisateur si spécifié
                            if user_id and data.get("user_id") != user_id:
                                continue
                            
                            # Extraire les métadonnées principales
                            conversation_info = {
                                "conversation_id": data.get("conversation_id"),
                                "title": data.get("metadata", {}).get("title", "Conversation"),
                                "last_updated": data.get("metadata", {}).get("updated_at"),
                                "summary": data.get("metadata", {}).get("summary", ""),
                                "message_count": len(data.get("messages", [])),
                                "topics": data.get("metadata", {}).get("tags", [])
                            }
                            
                            conversation_files.append(conversation_info)
                    except Exception as e:
                        logger.error(f"Erreur lors de la lecture du fichier {filename}: {str(e)}")
            
            # Trier par date de mise à jour (plus récent d'abord)
            conversation_files.sort(
                key=lambda x: x.get("last_updated", ""),
                reverse=True
            )
            
            # Appliquer pagination
            paginated_results = conversation_files[offset:offset+limit]
            
            return paginated_results
            
        except Exception as e:
            logger.error(f"Erreur lors de la liste des conversations: {str(e)}")
            return []
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Supprime une conversation.
        
        Args:
            conversation_id: ID de la conversation à supprimer
            
        Returns:
            True si supprimée avec succès, False sinon
        """
        try:
            file_path = os.path.join(self.conversations_dir, f"{conversation_id}.json")
            
            if os.path.exists(file_path):
                os.remove(file_path)
                
                # Supprimer du cache si présente
                if conversation_id in self.conversations:
                    del self.conversations[conversation_id]
                
                logger.info(f"Conversation {conversation_id} supprimée")
                return True
            else:
                logger.warning(f"Conversation {conversation_id} non trouvée pour suppression")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de la conversation {conversation_id}: {str(e)}")
            return False


    @profile("process_input")
    async def process_user_input(self, conversation_id: str, user_input: str, user_id: str = "anonymous", mode: str = "chat", websocket = None) -> Dict[str, Any]:
        """
        Traite une entrée utilisateur avec pipeline optimisé utilisant le Smart Router.
        """
        logger.info("🔄 ConversationManager: traitement demande utilisateur - conv_id=%s", conversation_id)
        try:
            start_time = time.time()
            # Récupérer la conversation
            conversation = self.get_conversation(conversation_id, user_id)
            logger.info("📋 ConversationManager: conversation récupérée - msg_count=%d", len(conversation.messages))
            
            # Ajouter le message utilisateur à l'historique
            conversation.add_message(user_input, role="user", metadata={"mode": mode})
            logger.info("➕ ConversationManager: message utilisateur ajouté")

            
            # Utiliser le Smart Router pour générer la réponse avec un seul appel LLM
            router_start = time.time()
            logger.info("🧭 ConversationManager: appel au SmartRouter")
            result = await smart_router.process_request(
                user_input=user_input, 
                conversation_id=conversation_id,
                user_id=user_id,
                mode=mode,
                websocket=websocket
            )
            router_time = time.time() - router_start
            logger.info("⏱️ ConversationManager: SmartRouter a répondu en %.2f ms", router_time * 1000)
            
            # Ajouter la réponse à la conversation
            conversation.add_message(result["response"], role="assistant", metadata={"mode": mode})
            logger.info("💬 ConversationManager: réponse assistant ajoutée, taille=%d", len(result["response"]))
            
            # Générer un titre si c'est une nouvelle conversation
            if len(conversation.messages) <= 4 and not conversation.metadata.get("title"):
                asyncio.create_task(conversation.generate_title())
            

            total_time = time.time() - start_time
            logger.info("✅ ConversationManager: requête complète traitée en %.2f ms", total_time * 1000)

            return result
        except Exception as e:
            logger.error(f"Erreur lors du traitement de l'entrée utilisateur: {str(e)}")
            return {
                "response": "Je rencontre une difficulté à traiter votre demande. Pourriez-vous réessayer?",
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "mode": mode,
                "error": str(e)
            }

conversation_manager = ConversationManager()