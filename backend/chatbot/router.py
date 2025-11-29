from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse
from typing import Optional, List
import json
import sys
from pathlib import Path
from datetime import datetime
import base64

# Add backend root to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from auth.router import get_current_user
from database import db, get_next_sequence
from logger import get_logger
from chatbot.schema import ChatRequest, ChatResponse, StreamingChunk, MCPGraph
from chatbot.orchestrator import ChatOrchestrator
from chatbot.mcp_server import MCPServer
from config import ASSEMBLY_AI_API_KEY

logger = get_logger(__name__)
router = APIRouter()

# Initialize orchestrator and MCP server
orchestrator = ChatOrchestrator()
mcp_server = MCPServer()

@router.post("/chat")
async def chat(
    message: str = Form(...),
    conversation_id: Optional[str] = Form(None),
    media: Optional[List[UploadFile]] = File(None),
    current_user: dict = Depends(get_current_user),
):
    """Chat endpoint with streaming support."""
    user_id = current_user.get("user_id") or str(current_user["_id"])
    
    # Get or create conversation
    if not conversation_id:
        conv_seq = await get_next_sequence("conversations")
        conversation_id = str(conv_seq)
        
        # Create conversation document
        await db.conversations.insert_one({
            "conversationId": conversation_id,
            "userId": user_id,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
            "messages": [],
        })
    
    # Process media files
    media_data = []
    if media:
        for file in media:
            file_bytes = await file.read()
            media_data.append({
                "type": file.content_type,
                "data": file_bytes,
                "filename": file.filename,
            })
    
    # Get conversation history
    conv_doc = await db.conversations.find_one({"conversationId": conversation_id})
    conversation_history = conv_doc.get("messages", []) if conv_doc else []
    
    # Save user message
    user_message = {
        "role": "user",
        "content": message,
        "timestamp": datetime.utcnow(),
    }
    conversation_history.append(user_message)
    
    async def generate_stream():
        message_id = None
        assistant_message = {
            "role": "assistant",
            "content": "",
            "sources": [],
            "citations": [],
            "intent": None,
            "tools_used": [],
            "metadata": {},
            "timestamp": datetime.utcnow(),
        }
        
        try:
            async for chunk in orchestrator.process_message(
                message=message,
                conversation_id=conversation_id,
                media=media_data,
                conversation_history=conversation_history,
            ):
                chunk_type = chunk.get("type")
                chunk_data = chunk.get("data", {})
                message_id = chunk.get("message_id")
                
                if chunk_type == "progress":
                    # Send progress update
                    yield f"data: {json.dumps({'type': 'progress', 'data': chunk_data, 'message_id': message_id})}\n\n"
                
                elif chunk_type == "content":
                    # Update assistant message
                    assistant_message["content"] = chunk_data.get("message", "")
                    assistant_message["sources"] = chunk_data.get("sources", [])
                    assistant_message["citations"] = chunk_data.get("citations", [])
                    chunk_data["conversation_id"] = conversation_id
                    yield f"data: {json.dumps({'type': 'content', 'data': chunk_data, 'message_id': message_id})}\n\n"
                
                elif chunk_type == "complete":
                    assistant_message["intent"] = chunk_data.get("intent")
                    assistant_message["tools_used"] = chunk_data.get("tools_used", [])
                    assistant_message["metadata"] = chunk_data.get("metadata", {})
                    chunk_data["conversation_id"] = conversation_id
                    yield f"data: {json.dumps({'type': 'complete', 'data': chunk_data, 'message_id': message_id})}\n\n"
            
            # Save assistant message to conversation
            conversation_history.append(assistant_message)
            await db.conversations.update_one(
                {"conversationId": conversation_id},
                {
                    "$set": {
                        "messages": conversation_history,
                        "updatedAt": datetime.utcnow(),
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Chat streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': {'error': str(e)}, 'message_id': message_id})}\n\n"
    
    return StreamingResponse(generate_stream(), media_type="text/event-stream")

@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get conversation history."""
    user_id = current_user.get("user_id") or str(current_user["_id"])
    
    conv = await db.conversations.find_one({
        "conversationId": conversation_id,
        "userId": user_id,
    })
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {
        "conversation_id": conversation_id,
        "messages": conv.get("messages", []),
    }

@router.get("/conversations")
async def list_conversations(
    current_user: dict = Depends(get_current_user),
):
    """List all conversations for user."""
    user_id = current_user.get("user_id") or str(current_user["_id"])
    
    conversations = await db.conversations.find(
        {"userId": user_id}
    ).sort("updatedAt", -1).limit(50).to_list(length=None)
    
    return {
        "conversations": [
            {
                "conversation_id": conv["conversationId"],
                "created_at": conv["createdAt"].isoformat(),
                "updated_at": conv["updatedAt"].isoformat(),
                "message_count": len(conv.get("messages", [])),
            }
            for conv in conversations
        ]
    }

@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Transcribe audio using Assembly AI (reuse from misinformation router)."""
    user_id = current_user.get("user_id") or str(current_user["_id"])
    logger.info(f"Audio transcription requested by user {user_id}, filename={file.filename}")
    
    if not ASSEMBLY_AI_API_KEY:
        logger.error("AssemblyAI API key not configured")
        raise HTTPException(
            status_code=500,
            detail="AssemblyAI API key not configured on the server.",
        )
    
    audio_bytes = await file.read()
    if not audio_bytes:
        logger.warning(f"Audio transcription failed: Empty file from user {user_id}")
        raise HTTPException(status_code=400, detail="Audio file is empty.")
    if len(audio_bytes) > 25 * 1024 * 1024:
        logger.warning(f"Audio transcription failed: File too large ({len(audio_bytes)} bytes) from user {user_id}")
        raise HTTPException(status_code=400, detail="Audio file exceeds 25 MB limit.")
    
    logger.info(f"Transcribing audio for user {user_id}, size={len(audio_bytes)} bytes")
    
    # Use Assembly AI transcription with proper error handling
    import httpx
    import asyncio
    
    ASSEMBLY_BASE_URL = "https://api.assemblyai.com"
    headers = {"authorization": ASSEMBLY_AI_API_KEY}
    
    try:
        # Upload audio
        async with httpx.AsyncClient(timeout=60.0) as client:
            upload_response = await client.post(
                f"{ASSEMBLY_BASE_URL}/v2/upload",
                headers=headers,
                content=audio_bytes,
            )
            if upload_response.status_code >= 400:
                logger.error(f"AssemblyAI upload failed: {upload_response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"AssemblyAI upload failed: {upload_response.text}",
                )
            upload_data = upload_response.json()
            audio_url = upload_data.get("upload_url")
            if not audio_url:
                raise HTTPException(status_code=502, detail="Invalid upload response from AssemblyAI.")
            
            # Create transcript
            transcript_response = await client.post(
                f"{ASSEMBLY_BASE_URL}/v2/transcript",
                headers={**headers, "content-type": "application/json"},
                json={"audio_url": audio_url},
            )
            if transcript_response.status_code >= 400:
                logger.error(f"AssemblyAI transcription request failed: {transcript_response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"AssemblyAI transcription request failed: {transcript_response.text}",
                )
            transcript_data = transcript_response.json()
            transcript_id = transcript_data.get("id")
            if not transcript_id:
                raise HTTPException(status_code=502, detail="Invalid transcript response from AssemblyAI.")
            
            # Poll for completion
            start_time = asyncio.get_event_loop().time()
            timeout_seconds = 120
            poll_interval = 2.0
            
            while True:
                status_response = await client.get(
                    f"{ASSEMBLY_BASE_URL}/v2/transcript/{transcript_id}",
                    headers=headers,
                )
                if status_response.status_code >= 400:
                    logger.error(f"AssemblyAI polling failed: {status_response.text}")
                    raise HTTPException(
                        status_code=502,
                        detail=f"AssemblyAI polling failed: {status_response.text}",
                    )
                status_data = status_response.json()
                status_value = status_data.get("status")
                
                if status_value == "completed":
                    transcript_text = status_data.get("text", "")
                    logger.info(f"Audio transcription completed for user {user_id}, transcript_length={len(transcript_text)}")
                    return {"text": transcript_text}
                elif status_value == "error":
                    error_msg = status_data.get("error", "Unknown error")
                    logger.error(f"Transcription failed: {error_msg}")
                    raise HTTPException(
                        status_code=502,
                        detail=f"Transcription failed: {error_msg}",
                    )
                
                if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                    raise HTTPException(status_code=504, detail="AssemblyAI transcription timed out.")
                
                await asyncio.sleep(poll_interval)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during transcription: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}",
        )

@router.get("/mcp/graph")
async def get_mcp_graph(
    current_user: dict = Depends(get_current_user),
):
    """Get MCP graph representation."""
    graph = mcp_server.get_graph()
    return graph.model_dump()

