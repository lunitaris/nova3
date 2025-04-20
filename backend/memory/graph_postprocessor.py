import logging
from difflib import SequenceMatcher

# Import des rules
from backend.memory.symbolic_graph_rules import ALIASES, TYPE_MAP, RELATION_REWRITE


logger = logging.getLogger(__name__)

def normalize_name(name: str) -> str:
    return ALIASES.get(name.lower().strip(), name.strip())

def refine_type(name: str, base_type: str) -> str:
    lowered = name.lower().strip()
    return TYPE_MAP.get(lowered, base_type)

def rewrite_relation(label: str) -> str:
    return RELATION_REWRITE.get(label.lower().strip(), label.strip())

def find_similar_entity_id(name, entities, threshold=0.92):
    for entity_id, entity in entities.items():
        existing_name = entity["name"]
        ratio = SequenceMatcher(None, name.lower(), existing_name.lower()).ratio()
        if ratio > threshold:
            return entity_id
    return None

def postprocess_graph(graph: dict) -> dict:
    updated_entities = {}
    remap_ids = {}

    # 1. Traitement des entités
    for entity_id, entity in graph["entities"].items():
        original_name = entity["name"]
        normalized_name = normalize_name(original_name)
        entity_type = refine_type(normalized_name, entity["type"])

        # Chercher une entité déjà traitée avec le même nom
        existing_id = find_similar_entity_id(normalized_name, updated_entities)
        if existing_id:
            logger.info(f"Fusion: {original_name} -> {updated_entities[existing_id]['name']}")
            remap_ids[entity_id] = existing_id
            # Fusionner attributs
            updated_entities[existing_id]["attributes"].update(entity.get("attributes", {}))
        else:
            # Mise à jour
            new_id = entity_id
            new_entity = entity.copy()
            new_entity["name"] = normalized_name
            new_entity["type"] = entity_type
            updated_entities[new_id] = new_entity
            remap_ids[entity_id] = new_id

    # 2. Traitement des relations
    updated_relations = []
    for rel in graph["relations"]:
        src = remap_ids.get(rel["source"], rel["source"])
        tgt = remap_ids.get(rel["target"], rel["target"])
        label = rewrite_relation(rel["relation"])

        # Éviter les relations en double
        if not any(r for r in updated_relations if r["source"] == src and r["target"] == tgt and r["relation"] == label):
            rel_clean = rel.copy()
            rel_clean["source"] = src
            rel_clean["target"] = tgt
            rel_clean["relation"] = label
            rel_clean["confidence"] = round(rel.get("confidence", 0.8), 2)
            updated_relations.append(rel_clean)

    return {
        "entities": updated_entities,
        "relations": updated_relations
    }
