# backend/models/streaming_callbacks.py

import logging
import time
import asyncio
from langchain_core.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)

class StreamingWebSocketCallbackHandler(BaseCallbackHandler):
    def __init__(self, websocket=None):
        self.websocket = websocket
        self.is_active = True
        self.tokens_buffer = []
        self.last_send_time = time.time()
        self.batch_size = 5


        # ✅ Boucle sécurisée même hors thread principal
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def on_llm_new_token(self, token: str, **kwargs):
        if not self.websocket or not self.is_active:
            return
        try:
            self.tokens_buffer.append(token)
            now = time.time()
            if len(self.tokens_buffer) >= self.batch_size or (now - self.last_send_time) > 0.5:
                self.loop.call_soon_threadsafe(  # ✅ appel thread-safe avec ta propre loop
                    lambda: asyncio.create_task(self._send_batch())
                )
                self.last_send_time = now
        except Exception as e:
            self.is_active = False
            logger.error(f"[StreamingHandler] Erreur traitement token: {str(e)}")

    async def _send_batch(self):
        if not self.websocket or not self.is_active or not self.tokens_buffer:
            return
        try:
            tokens_to_send = "".join(self.tokens_buffer)
            self.tokens_buffer = []
            await self.websocket.send_json({"type": "token", "content": tokens_to_send})
            logger.info(f"[StreamingHandler] ✅ Batch envoyé: {tokens_to_send}")
        except Exception as e:
            self.is_active = False
            logger.error(f"[StreamingHandler] Erreur envoi batch: {str(e)}")

    async def flush_remaining_tokens(self):
        if not self.tokens_buffer or not self.websocket or not self.is_active:
            return
        try:
            combined_tokens = "".join(self.tokens_buffer)
            self.tokens_buffer = []
            await self.websocket.send_json({"type": "token", "content": combined_tokens})
            logger.info(f"[StreamingHandler] ✓ Tokens restants envoyés ({len(combined_tokens)} caractères)")
            
            # ✅ AJOUT : notifier explicitement la fin du streaming
            await self.websocket.send_json({"type": "end", "content": combined_tokens})  # ✅ FIN DU STREAMING

        except Exception as e:
            logger.error(f"[StreamingHandler] ❌ Erreur flush: {str(e)}")

