# backend/utils/live_tracer.py
# Solution de tracing de fonctions proposé par Claude3

import asyncio
from fastapi import WebSocket

class LiveCallTracer:
    def __init__(self):
        self.websocket_connections: List[WebSocket] = []
        self.current_stack = []
        
    async def broadcast_event(self, event):
        for ws in self.websocket_connections:
            try:
                await ws.send_json(event)
            except:
                self.websocket_connections.remove(ws)
    
    def trace(self, name=None):
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                func_name = name or func.__name__
                
                # Entrée dans la fonction
                await self.broadcast_event({
                    "type": "enter",
                    "function": func_name,
                    "timestamp": time.time(),
                    "level": len(self.current_stack)
                })
                
                self.current_stack.append(func_name)
                
                try:
                    result = await func(*args, **kwargs)
                    
                    # Sortie de la fonction
                    await self.broadcast_event({
                        "type": "exit",
                        "function": func_name,
                        "timestamp": time.time(),
                        "result": str(result)[:100]
                    })
                    
                    return result
                finally:
                    self.current_stack.pop()
            
            return async_wrapper
        return decorator

# Endpoint WebSocket pour la visualisation en direct
@router.websocket("/debug/live-trace")
async def websocket_live_trace(websocket: WebSocket):
    await websocket.accept()
    live_tracer.websocket_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        live_tracer.websocket_connections.remove(websocket)
