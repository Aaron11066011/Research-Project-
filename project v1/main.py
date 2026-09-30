import os
import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from openai import AsyncOpenAI
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId


# ================= Configuration & Environment =================
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://viewpicture-input-survivors-beneficial.trycloudflare.com/v1")
AI_API_KEY = os.getenv("AI_API_KEY", "cloudflare-tunnel-api-key")
AI_MODEL = os.getenv("AI_MODEL", "gemma4:e4b")

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
    
# 接收前端人工校验数据的模型
class FactorScore(BaseModel):
    name: str
    score: int

class VerifyUpdate(BaseModel):
    factors: list[FactorScore]
    total: int

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

@app.post("/api/notes")
async def create_note(note: NoteCreate):
    try:
        agent_reply = None
        parsed_data = None
        # [新增] 默认状态为只有文本，如果是 AI 跑的则标记为待校验
        verification_status = "text_only" 
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        if note.action == "agent":
            try:
                ai_client = AsyncOpenAI(base_url=AI_BASE_URL, api_key=AI_API_KEY)
                response = await ai_client.chat.completions.create(
                    model=AI_MODEL, 
                    messages=[
                        {
                            "role": "system", 
                            "content": """You are an expert data evaluator. 
                            Evaluate the user's text against the following 5 predefined factors:
                            1. Functional Value and Service Benefit The extent to which the platform or product helps users achieve what they want efficiently and provides clear practical benefits.
                            2. Transaction Safety and Risk Protection The extent to which the platform protects users from fraud, financial loss, or unfair transactions.
                            3. Ethical Behaviour and Integrity of the Platform The belief that the platform, sellers, or providers act honestly, keep promises, and treat users fairly.
                            4. Awareness / Reputational Signal Trust arising from market-mediated signals about the provider that operate through AWARENESS—exposure, familiarity, share of voice, and association with premium brands, advertising and sponsorship—or through REPUTATION—evaluative feedback from others, spanning anonymous on-platform signals (ratings, reviews, reputational indicators) and personal networks (word of mouth).
                            5. Positive Interaction Experience Trust that develops from a user's direct experience interacting with the platform (smooth navigation, successful transactions, satisfying service outcomes), including ease of use / usability (simple navigation, search, and task completion).

                            Scoring Rules:
                            +1 if positive/met, -1 if negative/unmet, 0 if neutral/not mentioned.
                            Calculate the "total". Return ONLY valid JSON format below without markdown wrappers:
                            {
                              "factors": [
                                {"name": "Functional Value and Service Benefit", "score": 1},
                                {"name": "Transaction Safety and Risk Protection", "score": 1},
                                {"name": "Ethical Behaviour and Integrity of the Platform", "score": 1},
                                {"name": "Awareness / Reputational Signal", "score": 1},
                                {"name": "Positive Interaction Experience", "score": 1}
                              ],
                              "total": 0
                            }"""
                        },
                        {"role": "user", "content": note.content}
                    ],
                    max_tokens=2000,
                    temperature=0.1
                )         
                agent_reply = response.choices[0].message.content.strip()
                verification_status = "llm_only" # [新增] 标记为 AI 预处理，待人工校验
                try:
                    # 过滤掉可能的 markdown 代码块标记
                    clean_json = agent_reply.replace("```json", "").replace("```", "").strip()
                    parsed_data = json.loads(clean_json)
                except Exception as e:
                    print(f"JSON Parse Error: {e}")

            except Exception as e:
                agent_reply = f"Failed to connect to local AI API: {str(e)}"
        # =========================================================
        
        # =========================================================

       # 插入 MongoDB
        note_dict = {
            "content": note.content,
            "agent_reply": agent_reply,
            "parsed_data": parsed_data,
            "verification_status": verification_status,
            "created_at": now
        }
        result = await notes_collection.insert_one(note_dict)
        
        return {
            "success": True, 
            "id": str(result.inserted_id), 
            "agent_reply": agent_reply,
            "parsed_data": parsed_data,
            "verification_status": verification_status,
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
                "parsed_data": document.get("parsed_data"),
                "verification_status": document.get("verification_status"),
                "created_at": document.get("created_at")
            })
        return {"success": True, "data": notes}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database read failed: {str(e)}")

@app.put("/api/notes/{note_id}/verify")
async def verify_note(note_id: str, update_data: VerifyUpdate):
    try:
        result = await notes_collection.update_one(
            {"_id": ObjectId(note_id)},
            {"$set": {
                "parsed_data": update_data.model_dump(),
                "verification_status": "human_verified" # 将状态更新为人工确认完毕
            }}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Record not found")
        
        return {"success": True, "message": "Verified and updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verify failed: {str(e)}")

@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: str):
    try:
        result = await notes_collection.delete_one({"_id": ObjectId(note_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Record not found")
        
        return {"success": True, "message": "Deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database delete failed: {str(e)}")