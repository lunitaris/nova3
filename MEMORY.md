2. Types de mémoire en détail
2.1 Mémoire vectorielle (vector_store.py)
Objectif : Stocker des souvenirs sous forme de vecteurs d'embedding permettant des recherches sémantiques par similarité.
Fonctionnalités clés :

Utilise FAISS pour l'indexation et la recherche efficace de vecteurs
Stocke les fragments de texte avec leurs métadonnées associées
Prend en charge les recherches sémantiques par similarité
Gère l'ajout, la suppression et la mise à jour des souvenirs

Implémentation :

Les souvenirs sont représentés par des vecteurs d'embedding de dimension vector_dimension (1536 par défaut)
Chaque souvenir possède des métadonnées (timestamp, type, sujet, etc.)
L'index vectoriel est sauvegardé sur disque pour persistance

2.2 Mémoire synthétique (synthetic_memory.py)
Objectif : Condenser et distiller les conversations en résumés concis pour réduire la taille du contexte.
Fonctionnalités clés :

Synthétise des conversations en résumés pertinents
Organise les informations par sujets
Compresse périodiquement les souvenirs pour optimiser l'espace
Permet la mémorisation explicite d'informations spécifiques

Implémentation :

Utilise des templates de prompts pour guider la synthèse
Les souvenirs synthétiques sont organisés par sujets dans un dictionnaire
Stockée dans un fichier JSON pour persistance
Inclut des mécanismes de compression pour combiner d'anciennes synthèses

2.3 Mémoire symbolique (symbolic_memory.py)
Objectif : Représenter des relations structurées entre entités dans un graphe de connaissances simplifié.
Fonctionnalités clés :

Extrait des entités (personnes, lieux, objets, concepts) du texte
Identifie et stocke les relations entre ces entités
Permet des requêtes sur les relations entre entités
Génère du contexte pertinent basé sur le graphe

Implémentation :

Structure de graphe avec des entités et des relations
Chaque entité possède un type et des attributs
Les relations sont des triplets (source, relation, cible)
Stockée dans un fichier JSON

3. Gestion des conversations et intégration
La classe Conversation (conversation.py) et son gestionnaire ConversationManager constituent le point central d'intégration des différents systèmes de mémoire.
Fonctionnalités clés :

Gestion de l'historique des messages
Sauvegarde et chargement des conversations
Mise à jour automatique des systèmes de mémoire
Génération de titres et résumés pour les conversations

Intégration avec la mémoire :

Lors de l'ajout d'un message utilisateur, la mémoire symbolique est mise à jour (_update_symbolic_memory)
Les vieux messages sont synthétisés avant d'être supprimés (_synthesize_old_messages)
L'historique est limité à une taille maximale configurable (max_history_length)

4. Utilisation de LangChain
LangChain est utilisé comme couche d'abstraction pour orchestrer les différents composants et simplifier les interactions avec les modèles LLM. Le module principal est langchain_manager.py.
Points d'utilisation de LangChain :

Traitement des messages : La méthode process_message dans LangChainManager gère le pipeline complet :

Détection d'intention
Récupération de contexte pertinent depuis les mémoires
Construction du prompt
Génération de réponse
Traitement post-génération


Récupération de contexte : La méthode _get_relevant_context interroge les trois systèmes de mémoire pour enrichir le contexte du prompt.
Format de l'historique : La méthode _format_conversation_history convertit l'historique brut en format compatible avec LangChain.
Détection d'intention : La méthode _detect_intent analyse les requêtes pour identifier le type d'action demandée.
Construction de prompts : LangChain est utilisé pour construire des prompts structurés avec le système, l'historique et l'entrée utilisateur.

5. Flux de données pour une interaction type
Voici le flux de données pour une interaction typique avec l'assistant :

L'utilisateur envoie un message via l'API chat (chat.py)
Le message est ajouté à la conversation courante et le gestionnaire de conversation est appelé
Le gestionnaire délègue le traitement à langchain_manager.process_message
LangChainManager :

Détecte l'intention du message
Récupère le contexte pertinent depuis les trois systèmes de mémoire
Construit un prompt enrichi avec ce contexte et l'historique
Appelle le modèle LLM approprié pour générer une réponse


La réponse est ajoutée à la conversation
La mémoire est mise à jour :

Si la conversation devient trop longue, les anciens messages sont synthétisés
Les entités et relations sont extraites pour la mémoire symbolique
Des titres et résumés sont générés pour faciliter la navigation



6. Interactions entre les systèmes de mémoire
6.1 Comment les mémoires interagissent

Vectorielle ↔ Synthétique : Les résumés générés par la mémoire synthétique sont stockés dans la mémoire vectorielle pour recherche future
Synthétique → Symbolique : Les informations détectées par la synthèse peuvent enrichir le graphe de connaissances
Symbolique → LangChain : Le contexte du graphe est utilisé pour enrichir les prompts

6.2 Flux lors d'une recherche de contexte
Quand l'assistant a besoin de contexte pour répondre à une question :

Il interroge la mémoire vectorielle avec la requête actuelle
Il récupère les souvenirs synthétiques liés au sujet ou au contenu
Il extrait le contexte pertinent du graphe symbolique
Ces trois sources sont combinées dans un prompt amélioré

7. Configuration et paramètres clés
Les paramètres importants pour la mémoire sont définis dans config.py sous la classe MemoryConfig :

vector_dimension : Dimension des vecteurs d'embedding (1536 par défaut)
max_history_length : Nombre maximal de messages dans l'historique (20 par défaut)
synthetic_memory_refresh_interval : Intervalle de rafraîchissement pour la compression (10 par défaut)

8. Points forts et limites
Points forts

Architecture modulaire permettant différents types de représentations mémorielles
Compression intelligente pour gérer efficacement l'espace contextuel limité
Capacité à extraire des relations structurées à partir de texte
Intégration fluide avec LangChain et les modèles LLM

Limites

Pas de mécanisme d'oubli actif ou de priorisation basée sur l'importance
Pas de vérification de cohérence entre les différents systèmes de mémoire
Dépendance aux capacités d'extraction du LLM pour la mémoire symbolique

9. Améliorations possibles

Mémoire épisodique : Ajouter une couche dédiée aux expériences temporelles spécifiques
Détection des contradictions : Mécanismes pour identifier et résoudre les informations contradictoires
Oubli stratégique : Algorithmes pour réduire les informations les moins pertinentes
Mémoire procédurale : Capacité à mémoriser et reproduire des séquences d'actions
Apprentissage incrémental : Amélioration des embeddings basée sur les interactions

Cette architecture multi-couche de mémoire, associée à l'utilisation stratégique de LangChain, permet à Nova de fournir des réponses informées et contextuelles en tirant parti de différentes formes de représentation de la connaissance.RéessayerClaude peut faire des erreurs. Assurez-vous de vérifier ses réponses.