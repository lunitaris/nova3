# Dans un terminal Python interactif
import asyncio
from models.skills.manager import skills_manager

# Tester une compétence spécifique
async def test_weather_skill():
    result = await skills_manager.process_query("Quel temps fait-il à Paris?")
    print(result)

asyncio.run(test_weather_skill())