import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.utils import compare_annotations_python
from app.models import NoteCreate, VerifyUpdate
from app.database import notes_collection
from app.prompts import EXTRACTION_PROMPT
from app.services.ai_service import call_ai_json

router = APIRouter(prefix="/api/notes", tags=["Notes"])

@router.post("")
async def create_note(note: NoteCreate):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    agent_reply, llm_data = None, None
    status = "raw" 

    if note.action == "agent":
        llm_data, agent_reply = await call_ai_json(EXTRACTION_PROMPT, note.content)
        status = "llm_annotated" if llm_data else "raw"

    document = {
        "review_id": f"R-{ObjectId()}",
        "raw_data": {
            "review_text": note.content,
            "created_at": now
        },
        "llm_annotation": llm_data,
        "llm_raw_reply": agent_reply,
        "human_annotations": [],
        "final_annotation": None,
        "comparison": None,
        "workflow": {
            "status": status,
            "last_updated_at": now
        }
    }
    
    result = await notes_collection.insert_one(document)
    return {"success": True, "id": str(result.inserted_id)}

@router.get("")
async def get_notes():
    cursor = notes_collection.find().sort("_id", -1).limit(50)
    notes = []
    async for doc in cursor:
        status = doc.get("workflow", {}).get("status", doc.get("verification_status", "raw"))
        notes.append({
            "id": str(doc["_id"]),
            "content": doc.get("raw_data", {}).get("review_text", doc.get("content", "")),
            "llm_parsed_data": doc.get("llm_annotation", doc.get("llm_parsed_data")),
            "human_parsed_data": doc.get("final_annotation", doc.get("human_parsed_data")),
            "validation_data": doc.get("comparison", doc.get("validation_data")),
            "verification_status": status,
            "created_at": doc.get("raw_data", {}).get("created_at", doc.get("created_at", ""))
        })
    return {"success": True, "data": notes}

@router.put("/{note_id}/verify")
async def verify_note(note_id: str, update_data: VerifyUpdate):
    doc = await notes_collection.find_one({"_id": ObjectId(note_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
        
    human_data = update_data.human_data
    llm_data = doc.get("llm_annotation") or doc.get("llm_parsed_data") or {}
    
    
    validation_data = compare_annotations_python(llm_data, human_data)
    
    now_iso = datetime.now(timezone.utc).isoformat()
    human_entry = {
        "annotator_id": "human_researcher",
        "verified_at": now_iso,
        "annotation": human_data,
        "comparison": validation_data
    }
    
    await notes_collection.update_one(
        {"_id": ObjectId(note_id)},
        {
            "$set": {
                "final_annotation": human_data,
                "human_parsed_data": human_data,
                "comparison": validation_data,
                "validation_data": validation_data,
                "workflow.status": "human_verified",
                "verification_status": "human_verified",
                "updated_at": now_iso
            },
            "$push": {"human_annotations": human_entry}
        }
    )
    return {"success": True, "validation_data": validation_data}


    await notes_collection.update_one(
        {"_id": ObjectId(note_id)},
        {
            "$push": {"human_annotations": human_record},
            "$set": {
                "final_annotation": human_data,
                "comparison": validation_data,
                "workflow.status": "human_verified",
                "workflow.last_updated_at": now,
                "human_parsed_data": human_data,
                "validation_data": validation_data,
                "verification_status": "human_verified"
            }
        }
    )
    return {"success": True}

@router.delete("/{note_id}")
async def delete_note(note_id: str):
    await notes_collection.delete_one({"_id": ObjectId(note_id)})
    return {"success": True}
