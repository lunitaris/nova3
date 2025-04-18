#!/bin/bash

# === Emplacement des fichiers mémoire ===
DATA_DIR="./data"
VECTOR_INDEX="$DATA_DIR/vector_index.faiss"
VECTOR_METADATA="$DATA_DIR/vector_metadata.json"
SYNTHETIC_MEMORY="$DATA_DIR/synthetic_memory.json"
SYMBOLIC_MEMORY="$DATA_DIR/memories/symbolic_memory.json"

echo "🧠 Nettoyage de la mémoire Nova..."

for FILE in "$VECTOR_INDEX" "$VECTOR_METADATA" "$SYNTHETIC_MEMORY" "$SYMBOLIC_MEMORY"; do
    if [ -f "$FILE" ]; then
        echo "🗑️ Suppression : $FILE"
        rm "$FILE"
    else
        echo "✅ Déjà supprimé ou introuvable : $FILE"
    fi
done

echo "✅ Mémoire nettoyée avec succès."
