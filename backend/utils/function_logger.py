# backend/utils/function_logger.py
# Solution de tracing de fonctions proposé par Claude3
import logging
import json
from functools import wraps

class StructuredLogger:
    def __init__(self):
        self.logger = logging.getLogger("function_calls")
        self.current_depth = 0
        
    def trace(self, name=None):
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                func_name = name or func.__name__
                indent = "  " * self.current_depth
                
                self.logger.info(json.dumps({
                    "event": "function_start",
                    "name": func_name,
                    "depth": self.current_depth,
                    "timestamp": time.time(),
                    "indent": indent
                }))
                
                self.current_depth += 1
                
                try:
                    result = await func(*args, **kwargs)
                    
                    self.logger.info(json.dumps({
                        "event": "function_end",
                        "name": func_name,
                        "depth": self.current_depth - 1,
                        "timestamp": time.time(),
                        "result_size": len(str(result)) if result else 0
                    }))
                    
                    return result
                finally:
                    self.current_depth -= 1
            
            return async_wrapper
        return decorator