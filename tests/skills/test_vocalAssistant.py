import sys, os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
from backend.voice.vocal_assistant import run_assistant

asyncio.run(run_assistant())