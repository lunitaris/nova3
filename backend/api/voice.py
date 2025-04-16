from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, File, UploadFile, Form, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import logging
import asyncio
import io
import tempfile
import os
import subprocess


from voice.stt import stt_engine
from voice.tts import tts_engine
from memory.conversation import conversation_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

# Modèles de données
class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    conversation_id: Optional[str] = None

class STTResult(BaseModel):
    text: str
    confidence: Optional[float] = None
    language: Optional[str] = "fr"
    error: Optional[str] = None

# Endpoints
@router.post("/tts", response_model=Dict[str, Any])
async def text_to_speech(request: TTSRequest):
    """
    Convertit du texte en audio et renvoie l'URL du fichier audio.
    """
    try:
        # Générer le fichier audio
        audio_file = await tts_engine.text_to_speech_file(request.text)
        
        if not audio_file:
            raise HTTPException(status_code=500, detail="Échec de la génération audio")
        
        # Créer une réponse avec le chemin relatif
        base_name = os.path.basename(audio_file)
        
        return {
            "status": "success",
            "audio_path": f"/audio/{base_name}",
            "file_path": audio_file
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la génération TTS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur TTS: {str(e)}")




@router.post("/tts/stream")
async def stream_text_to_speech(request: TTSRequest):
    try:
        audio_path = await tts_engine.text_to_speech_file(request.text)
        
        # Lire le son côté serveur (pas dans la réponse HTTP)
        subprocess.Popen(["ffplay", "-nodisp", "-autoexit", audio_path])
        return {"status": "lecture démarrée"}
    
    except Exception as e:
        logger.error(f"Erreur TTS: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur TTS")



@router.post("/stt", response_model=STTResult)
async def speech_to_text(
    file: UploadFile = File(...),
    language: str = Form("fr")
):
    """
    Convertit un fichier audio en texte.
    """
    try:
        # Stocker le fichier temporairement
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            temp_path = temp_file.name
            temp_file.write(await file.read())
        
        # Transcrire le fichier
        result = await stt_engine.transcribe_file(temp_path)
        
        # Nettoyer le fichier temporaire
        os.unlink(temp_path)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return STTResult(
            text=result.get("text", ""),
            confidence=result.get("confidence", 0.0),
            language=result.get("language", language)
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de la transcription STT: {str(e)}")
        
        # Nettoyer en cas d'erreur
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
            
        raise HTTPException(status_code=500, detail=f"Erreur STT: {str(e)}")

# WebSocket pour le streaming vocal bidirectionnel
@router.websocket("/ws/stream/{conversation_id}")
async def voice_websocket(websocket: WebSocket, conversation_id: str):
    await websocket.accept()
    
    try:
        # Buffer pour les données audio entrantes
        audio_buffer = io.BytesIO()
        
        # Indique si nous sommes en train d'enregistrer
        is_recording = False
        
        while True:
            message = await websocket.receive()
            
            # Gérer les messages texte (commandes)
            if "text" in message:
                data = json.loads(message["text"])
                command = data.get("command")
                
                # Commande pour démarrer l'enregistrement
                if command == "start_recording":
                    is_recording = True
                    audio_buffer = io.BytesIO()  # Réinitialiser le buffer
                    await websocket.send_json({"status": "recording_started"})
                
                # Commande pour arrêter l'enregistrement et transcrire
                elif command == "stop_recording":
                    is_recording = False
                    
                    # Préparer les données audio pour transcription
                    audio_data = audio_buffer.getvalue()
                    
                    if len(audio_data) > 0:
                        # Transcription
                        result = await stt_engine.transcribe_audio_data(audio_data)
                        
                        transcribed_text = result.get("text", "").strip()
                        
                        if transcribed_text:
                            # Envoyer la transcription
                            await websocket.send_json({
                                "type": "transcription",
                                "text": transcribed_text
                            })
                            
                            # Traiter la demande et générer une réponse
                            user_id = data.get("user_id", "anonymous")
                            
                            # Informer le client que la génération de réponse commence
                            await websocket.send_json({
                                "type": "generating_response"
                            })
                            
                            # Générer la réponse (utiliser le processeur de conversation)
                            response = await conversation_manager.process_user_input(
                                conversation_id=conversation_id,
                                user_input=transcribed_text,
                                user_id=user_id,
                                mode="voice"
                            )
                            
                            # Envoyer la réponse texte
                            await websocket.send_json({
                                "type": "response_text",
                                "text": response["response"],
                                "conversation_id": response["conversation_id"]
                            })
                            
                            # Streaming audio de la réponse
                            await websocket.send_json({
                                "type": "response_audio_start"
                            })
                            
                            # Générer et envoyer l'audio par morceaux
                            async for audio_chunk in tts_engine.stream_long_text(response["response"]):
                                await websocket.send_bytes(audio_chunk)
                            
                            await websocket.send_json({
                                "type": "response_audio_end"
                            })
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "text": "Aucun texte transcrit"
                            })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "text": "Aucune donnée audio reçue"
                        })
                
                # Commande pour synthétiser du texte en audio
                elif command == "synthesize":
                    text = data.get("text", "")
                    
                    if text:
                        # Informer que la synthèse commence
                        await websocket.send_json({
                            "type": "synthesis_start"
                        })
                        
                        # Générer et envoyer l'audio
                        async for audio_chunk in tts_engine.stream_long_text(text):
                            await websocket.send_bytes(audio_chunk)
                        
                        await websocket.send_json({
                            "type": "synthesis_end"
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "text": "Texte vide"
                        })
            
            # Gérer les données binaires (audio)
            elif "bytes" in message and is_recording:
                # Ajouter les données audio au buffer
                audio_buffer.write(message["bytes"])
    
    except WebSocketDisconnect:
        logger.info(f"Client WebSocket vocal déconnecté: {conversation_id}")
    except Exception as e:
        logger.error(f"Erreur WebSocket vocal: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "text": f"Erreur: {str(e)}"
        })