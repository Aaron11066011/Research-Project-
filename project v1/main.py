import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from openai import OpenAI

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

# ================= Database Setup =================
DB_FILE = "notes.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        cursor.execute('ALTER TABLE notes ADD COLUMN agent_reply TEXT')
    except sqlite3.OperationalError:
        pass 
    
    conn.commit()
    conn.close()

init_db()

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
def read_root():
    return {"message": "API service is running. Open index.html in your browser to use the tool."}

@app.post("/api/notes")
def create_note(note: NoteCreate):
    try:
        agent_reply = None

        # =========================================================
        # [API Integration]
        # =========================================================
        if note.action == "agent":
            try:
                # Initialize AI client for LOCAL MODEL
                client = OpenAI(
                    # Base URL for Ollama local server
                    # Note: If you use LM Studio, change this to "http://localhost:1234/v1"
                    base_url="http://localhost:1234/v1", 
                    
                    # API key is required by the SDK format, but local servers usually ignore it
                    api_key="local-model", 
                )
                
                # Send request to local AI
                response = client.chat.completions.create(
                    # Must match the exact model name you downloaded (e.g., "llama3", "qwen2")
                    model="Qwen 3.5 9B", 
                    messages=[
                        {"role": "system", "content": "You are a data commentary and analysis expert. Split each comment into separate “aspect” sentences; each sentence can be mapped to one or more Factors (multi-label; a single comment can contribute to multiple Factors at the same time).If a passage contains a positive message, add one point; if it contains a negative message, subtract one point; for ambiguous or irrelevant passages, give zero points. just give final marks."},
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

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute(
            "INSERT INTO notes (content, agent_reply, created_at) VALUES (?, ?, ?)", 
            (note.content, agent_reply, now)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        
        return {
            "success": True, 
            "id": new_id, 
            "agent_reply": agent_reply,
            "message": "Agent channel triggered" if note.action == "agent" else "Text saved successfully"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Write failed: {str(e)}")

@app.get("/api/notes")
def get_notes():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, content, agent_reply, created_at FROM notes ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        conn.close()
        
        notes = [{
            "id": row["id"], 
            "content": row["content"], 
            "agent_reply": row["agent_reply"],
            "created_at": row["created_at"]
        } for row in rows]
        
        return {"success": True, "data": notes}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database read failed: {str(e)}")

@app.delete("/api/notes/{note_id}")
def delete_note(note_id: int):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Record not found")
        conn.commit()
        conn.close()
        return {"success": True, "message": "Deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database delete failed: {str(e)}")
    