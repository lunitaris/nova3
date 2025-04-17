class AutomaticMemoryContextualizer:
    """
    Analyse les requêtes utilisateur, récupère les souvenirs pertinents et les formate
    pour enrichir le contexte conversationnel de façon totalement autonome.
    """

    def __init__(self, model_manager, vector_store, symbolic_memory):
        self.model_manager = model_manager
        self.vector_store = vector_store
        self.symbolic_memory = symbolic_memory
        self.relevance_cache = {}  # Cache pour éviter des requêtes redondantes

    async def enrich_context(self, query: str, user_id: str) -> str:
        """
        Point d'entrée principal qui orchestre le processus d'enrichissement contextuel.
        
        Args:
            query: La requête de l'utilisateur
            user_id: Identifiant de l'utilisateur
            
        Returns:
            Contexte enrichi formaté pour le LLM
        """
        # 1. Analyser la requête pour identifier les sujets et entités potentiellement pertinents
        query_analysis = await self._analyze_query(query)
        
        # 2. Récupérer les souvenirs pertinents de la mémoire symbolique
        symbolic_memories = await self._retrieve_symbolic_memories(
            user_id=user_id,
            entity_types=query_analysis['entity_types'],
            relation_types=query_analysis['relation_types'],
            topics=query_analysis['topics']
        )
        
        # 3. Récupérer les souvenirs pertinents de la mémoire vectorielle
        vector_memories = await self._retrieve_vector_memories(
            query=query,
            user_id=user_id,
            entity_filter=query_analysis['entity_types']
        )
        
        # 4. Fusionner et dédupliquer les souvenirs récupérés
        all_memories = self._merge_memories(symbolic_memories, vector_memories)
        
        # 5. Évaluer la pertinence des souvenirs pour le contexte actuel
        relevant_memories = await self._evaluate_relevance(all_memories, query)
        
        # 6. Formater les souvenirs en contexte utilisable
        formatted_context = self._format_context(relevant_memories, user_id)
        
        return formatted_context

    async def _analyze_query(self, query: str) -> Dict[str, List[str]]:
        """
        Analyse la requête pour en extraire des sujets, types d'entités et types de relations pertinents.
        Utilise le LLM pour une analyse sémantique sans règles codées en dur.
        """
        prompt = """
        Analyse cette requête utilisateur et identifie les informations qui pourraient nécessiter
        des connaissances personnelles ou des souvenirs antérieurs pour y répondre correctement.
        
        Requête: "{query}"
        
        Format JSON souhaité:
        {{
          "topics": ["sujet1", "sujet2"],  // Thèmes généraux comme "identité", "préférences", "localisation", etc.
          "entity_types": ["type1", "type2"],  // Types d'entités comme "personne", "lieu", "date", etc.
          "relation_types": ["relation1", "relation2"],  // Types de relations comme "habite_à", "aime", etc.
          "requires_personal_context": true,  // Si la requête nécessite un contexte personnel
          "confidence": 0.8  // Niveau de confiance de l'analyse
        }}
        """
        
        prompt = prompt.replace("{query}", query)
        
        try:
            # Utiliser le LLM pour analyser la requête
            response = await self.model_manager.generate_response(prompt, complexity="low")
            
            # Extraire et parser le JSON
            import json
            import re
            
            json_match = re.search(r'{.*}', response, re.DOTALL)
            if not json_match:
                return {"topics": [], "entity_types": [], "relation_types": [], "requires_personal_context": False}
                
            analysis = json.loads(json_match.group(0))
            return analysis
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de la requête: {str(e)}")
            return {"topics": [], "entity_types": [], "relation_types": [], "requires_personal_context": False}

    async def _retrieve_symbolic_memories(self, user_id: str, entity_types: List[str], 
                                        relation_types: List[str], topics: List[str]) -> List[Dict[str, Any]]:
        """
        Récupère les souvenirs pertinents de la mémoire symbolique.
        """
        memories = []
        
        # Récupérer l'entité utilisateur
        user_entity_id = self.symbolic_memory.find_entity_by_name(user_id)
        if not user_entity_id:
            return memories
            
        # Récupérer toutes les relations de l'utilisateur
        all_relations = self.symbolic_memory.query_relations(user_entity_id)
        if not all_relations:
            return memories
            
        # Filtrer les relations pertinentes
        for relation in all_relations:
            relation_type = relation.get("relation", "")
            target_type = relation.get("target_type", "")
            
            # Vérifier si le type de relation ou d'entité correspond aux types recherchés
            relation_match = not relation_types or any(r_type in relation_type for r_type in relation_types)
            entity_match = not entity_types or any(e_type in target_type for e_type in entity_types)
            
            # Vérifier si la relation est liée aux sujets recherchés
            topic_match = False
            for topic in topics:
                # Mappage des sujets généraux à des types de relations
                topic_relation_mapping = {
                    "identité": ["nom", "prénom", "appel"],
                    "localisation": ["habite", "vit", "situé"],
                    "préférences": ["aime", "préfère", "déteste"],
                    "profession": ["travail", "métier", "profession"],
                    "famille": ["parent", "enfant", "famille"],
                    "contacts": ["téléphone", "email", "contact"]
                }
                
                # Vérifier si le sujet est lié à la relation
                if topic in topic_relation_mapping:
                    topic_keywords = topic_relation_mapping[topic]
                    if any(keyword in relation_type for keyword in topic_keywords):
                        topic_match = True
                        break
            
            # Si au moins un critère correspond, ajouter la relation aux souvenirs
            if relation_match or entity_match or topic_match or not (relation_types or entity_types or topics):
                memories.append({
                    "source": "symbolic",
                    "relation_type": relation_type,
                    "entity_type": target_type,
                    "entity_value": relation.get("target_name", ""),
                    "confidence": relation.get("confidence", 0.5)
                })
        
        return memories

    async def _retrieve_vector_memories(self, query: str, user_id: str, 
                                      entity_filter: List[str] = None) -> List[Dict[str, Any]]:
        """
        Récupère les souvenirs pertinents de la mémoire vectorielle.
        """
        # Rechercher des souvenirs similaires
        vector_results = self.vector_store.search_memories(
            query=query,
            k=5,  # Limiter à 5 résultats pour ne pas surcharger le contexte
            min_score=0.6  # Seuil minimal de pertinence
        )
        
        # Filtrer pour l'utilisateur spécifique
        filtered_results = []
        for result in vector_results:
            # Vérifier si le souvenir concerne l'utilisateur actuel
            if result.get("user_id") == user_id or user_id in result.get("content", ""):
                # Filtrer par type d'entité si spécifié
                entity_type = result.get("entity_type", "")
                if not entity_filter or not entity_type or any(e_type in entity_type for e_type in entity_filter):
                    filtered_results.append({
                        "source": "vector",
                        "content": result.get("content", ""),
                        "entity_type": entity_type,
                        "entity_value": result.get("entity_value", ""),
                        "confidence": result.get("score", 0.5)
                    })
        
        return filtered_results

    def _merge_memories(self, symbolic_memories: List[Dict[str, Any]], 
                       vector_memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fusionne et déduplique les souvenirs récupérés des différentes sources.
        """
        all_memories = symbolic_memories + vector_memories
        
        # Dédupliquer les souvenirs similaires
        unique_memories = []
        seen_content = set()
        
        for memory in all_memories:
            # Créer une représentation du contenu pour détecter les doublons
            if "content" in memory:
                content_key = memory["content"]
            else:
                content_key = f"{memory.get('relation_type', '')}-{memory.get('entity_value', '')}"
            
            if content_key not in seen_content:
                seen_content.add(content_key)
                unique_memories.append(memory)
        
        return unique_memories

    async def _evaluate_relevance(self, memories: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        Évalue la pertinence des souvenirs pour le contexte actuel de la conversation.
        Utilise le LLM pour une évaluation plus fine si nécessaire.
        """
        if not memories:
            return []
            
        # Si peu de souvenirs, pas besoin d'évaluation supplémentaire
        if len(memories) <= 3:
            return memories
            
        # Construire un prompt pour évaluer la pertinence
        memories_str = "\n".join([
            (m.get('content') or (m.get('relation_type', '') + " " + m.get('entity_value', '')))
            for m in memories
        ])
        
        prompt = f"""
        Évalue la pertinence de ces souvenirs par rapport à la requête utilisateur:
        
        Requête: "{query}"
        
        Souvenirs:
        {memories_str}
        
        Pour chaque souvenir, attribue un score de pertinence de 0 à 1.
        Format: [index1, index2, ...] pour les souvenirs pertinents (score >= 0.6)
        Exemple: [0, 2, 3]
        """
        
        try:
            # Extraire les indices des souvenirs pertinents
            response = await self.model_manager.generate_response(prompt, complexity="low")
            
            import re
            import json
            
            # Rechercher un format de liste dans la réponse
            list_match = re.search(r'\[.*?\]', response)
            if list_match:
                relevant_indices = json.loads(list_match.group(0))
                
                # Filtrer les souvenirs pertinents
                relevant_memories = [memories[i] for i in relevant_indices if i < len(memories)]
                return relevant_memories
            
            # Si l'analyse échoue, retourner les souvenirs avec la confiance la plus élevée
            memories.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            return memories[:3]  # Limiter à 3 souvenirs
            
        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation de pertinence: {str(e)}")
            
            # En cas d'erreur, retourner les souvenirs triés par confiance
            memories.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            return memories[:3]  # Limiter à 3 souvenirs

    def _format_context(self, memories: List[Dict[str, Any]], user_id: str) -> str:
        """
        Formate les souvenirs en un contexte utilisable pour le LLM.
        """
        if not memories:
            return ""
            
        context_parts = [f"Informations précédemment mémorisées à propos de l'utilisateur:"]
        
        for memory in memories:
            if memory["source"] == "symbolic":
                relation = memory.get("relation_type", "").replace("_", " ")
                value = memory.get("entity_value", "")
                
                # Formater en langage naturel
                if relation.startswith("a pour"):
                    context_parts.append(f"- {relation.replace('a pour', 'Son').strip()} est {value}")
                elif relation.startswith("est"):
                    context_parts.append(f"- {relation} {value}")
                elif relation.startswith("habite"):
                    context_parts.append(f"- Il/Elle {relation} {value}")
                else:
                    context_parts.append(f"- {relation} {value}")
                    
            elif memory["source"] == "vector":
                content = memory.get("content", "")
                
                # Nettoyer et reformater le contenu
                cleaned = content.replace(f"L'utilisateur {user_id}", "L'utilisateur")
                cleaned = cleaned.replace(f"Information sur {user_id}:", "")
                cleaned = cleaned.strip()
                
                if cleaned:
                    context_parts.append(f"- {cleaned}")
        
        return "\n".join(context_parts)