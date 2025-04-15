import sys, os

# Ajoute la racine du projet (Nova3.0) au PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
from backend.models.skills.manager import skills_manager

# Tester une compétence spécifique
async def test_weather_skill():
    result = await skills_manager.process_query("Quel temps fait-il à Toulouse?")
    print(result)

asyncio.run(test_weather_skill())
