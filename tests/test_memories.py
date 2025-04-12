import asyncio
from memory.symbolic_memory import symbolic_memory
from memory.synthetic_memory import synthetic_memory
from memory.vector_store import vector_store

async def test_memory():
    # Test mémoire symbolique
    update_stats = await symbolic_memory.update_graph_from_text(
        "Jean habite à Paris et il aime les chats. Son chat s'appelle Félix."
    )
    print("Graph update stats:", update_stats)
    
    # Test mémoire vectorielle
    memory_id = vector_store.add_memory(
        content="Mon anniversaire est le 15 juin",
        metadata={"type": "explicit", "topic": "user_info"}
    )
    print("Memory ID:", memory_id)
    
    # Recherche dans la mémoire
    results = vector_store.search_memories("Quand est mon anniversaire?")
    print("Search results:", results)

asyncio.run(test_memory())