import os
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from openai import AsyncOpenAI
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId


# ================= Configuration & Environment =================
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
# 如果部署到云端，请使用真实的 OpenAI API 或其他云端模型
AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:1234/v1")
AI_API_KEY = os.getenv("AI_API_KEY", "local-model")
AI_MODEL = os.getenv("AI_MODEL", "Qwen 3.5 9B")

# ================= Data Model =================
class NoteCreate(BaseModel):
    content: str
    action: str = "save"  # Default is "save", alternative is "agent"
    
    @field_validator('content')
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Content cannot be empty")
        return cleaned

# MongoDB 文档响应模型
class NoteResponse(BaseModel):
    id: str
    content: str
    agent_reply: str | None = None
    created_at: str

# ================= Database Setup =================
client = AsyncIOMotorClient(MONGO_URL)
db = client.notes_database
notes_collection = db.get_collection("notes")

# ================= FastAPI App =================
app = FastAPI(title="Quick Paste & Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= API Endpoints =================

@app.get("/")
async  def read_root():
    return {"message": "API service is running. Open index.html in your browser to use the tool."}

@app.post("/api/notes")
async def create_note(note: NoteCreate):
    try:
        agent_reply = None
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # =========================================================
        # [API Integration]
        # =========================================================
        if note.action == "agent":
            try:
                ai_client = AsyncOpenAI(base_url=AI_BASE_URL, api_key=AI_API_KEY)
                response = await ai_client.chat.completions.create(
                    model=AI_MODEL, 
                    messages=[
                        {"role": "system", "content": "You are a review analysis expert tasked with analyzing the semantics of these customer reviews. For every positive word you encounter, add one point; for every negative word, subtract one point. Output the scores for positive and negative reviews separately, as well as the total score."},
                        {"role": "user", "content": note.content}
                    ],
                    max_tokens=10000000,
                    temperature=0.1
                )         
                agent_reply = response.choices[0].message.content
                
            except Exception as e:
                agent_reply = f"Failed to connect to local AI API: {str(e)}"

        # =========================================================
        
        # =========================================================

       # 插入 MongoDB
        note_dict = {
            "content": note.content,
            "agent_reply": agent_reply,
            "created_at": now
        }
        result = await notes_collection.insert_one(note_dict)
        
        return {
            "success": True, 
            "id": str(result.inserted_id), 
            "agent_reply": agent_reply,
            "message": "Agent channel triggered" if note.action == "agent" else "Text saved successfully"
        }     
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Write failed: {str(e)}")

@app.get("/api/notes", response_model=dict)
async def get_notes():
    try:
        # 获取最新 20 条记录
        cursor = notes_collection.find().sort("_id", -1).limit(20)
        notes = []
        async for document in cursor:
            notes.append({
                "id": str(document["_id"]),
                "content": document["content"],
                "agent_reply": document.get("agent_reply"),
                "created_at": document.get("created_at")
            })
        return {"success": True, "data": notes}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database read failed: {str(e)}")

@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: str):
    try:
        result = await notes_collection.delete_one({"_id": ObjectId(note_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Record not found")
        
        return {"success": True, "message": "Deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database delete failed: {str(e)}")