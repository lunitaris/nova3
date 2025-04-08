from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.prompts.prompt import PromptTemplate
from typing import List, Dict, Any

# Template de base pour l'assistant
ASSISTANT_SYSTEM_TEMPLATE = """Tu es un assistant IA local nommé Assistant. Tu es serviable, poli et informatif.
Voici quelques règles que tu dois suivre:
- Réponds de manière concise et précise aux questions.
- Si tu ne connais pas la réponse, dis simplement que tu ne sais pas.
- Utilise un langage simple et accessible, sauf si on te demande d'être plus technique.
- N'invente pas d'informations.
- Respecte les préférences de l'utilisateur.

{memory_context}

Date actuelle: {current_date}
"""

# Template pour les réponses rapides (modèle léger)
FAST_RESPONSE_TEMPLATE = """Tu es Assistant, un assistant IA conversationnel.
Réponds de manière TRÈS concise et directe. Limite ta réponse à 1-2 phrases maximum.
Question: {query}
Réponse concise:"""

# Template pour la compression de mémoire synthétique
MEMORY_SYNTHESIS_TEMPLATE = """Voici une série de messages échangés avec un utilisateur:

{conversation_history}

Résume en quelques points clés les informations importantes à retenir de cette conversation.
Concentre-toi uniquement sur:
1. Les préférences et goûts de l'utilisateur
2. Les faits importants mentionnés
3. Les demandes spécifiques à retenir

Synthèse des informations importantes:"""

# Template pour la mémoire explicite
REMEMBER_TEMPLATE = """L'utilisateur souhaite que tu te souviennes de l'information suivante:

{info_to_remember}

Résume cette information en une phrase concise qui sera facile à récupérer plus tard.
Résumé:"""

# Template pour intégrer la mémoire dans les prompts
MEMORY_RECALL_TEMPLATE = """Voici des informations pertinentes tirées de tes souvenirs:

{memory_items}

Utilise ces informations seulement si elles sont pertinentes pour répondre à la demande actuelle.
"""

def create_chat_prompt_template(with_memory: bool = True) -> ChatPromptTemplate:
    """
    Crée un template de prompt pour les conversations.
    
    Args:
        with_memory: Si True, inclut le contexte de mémoire
        
    Returns:
        Un ChatPromptTemplate configuré
    """
    messages = [
        ("system", ASSISTANT_SYSTEM_TEMPLATE),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ]
    
    return ChatPromptTemplate.from_messages(messages)

def create_memory_synthesis_template() -> PromptTemplate:
    """
    Crée un template pour la synthèse de mémoire.
    
    Returns:
        Un PromptTemplate configuré
    """
    return PromptTemplate.from_template(MEMORY_SYNTHESIS_TEMPLATE)

def format_remembered_items(items: List[Dict[str, Any]]) -> str:
    """
    Formate les éléments de mémoire pour inclusion dans un prompt.
    
    Args:
        items: Liste d'éléments de mémoire avec clés 'content' et 'timestamp'
        
    Returns:
        Texte formaté des éléments de mémoire
    """
    if not items:
        return "Aucune information en mémoire."
    
    formatted_items = []
    for i, item in enumerate(items, 1):
        formatted_items.append(f"{i}. {item['content']} (Mémorisé le: {item['timestamp']})")
    
    return "\n".join(formatted_items)