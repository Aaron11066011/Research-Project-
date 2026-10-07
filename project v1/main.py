import os
import json
from datetime import datetime, timezone
from typing import Dict, Any
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

# Trust Index Weights Config (Can be moved to DB later)
TRUST_WEIGHTS = {
    "F1_functional_value": 0.20,
    "F2_transaction_safety": 0.20,
    "F3_integrity": 0.20,
    "F4_reputation": 0.20,
    "F5_interaction": 0.20
}

FACTOR_KEYS = list(TRUST_WEIGHTS.keys())

# ================= Data Models =================
class NoteCreate(BaseModel):
    content: str
    action: str = "save"
    
    @field_validator('content')
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Content cannot be empty")
        return v.strip()

class VerifyUpdate(BaseModel):
    human_data: Dict[str, Any]

# ================= DB Setup =================
client = AsyncIOMotorClient(MONGO_URL)
db = client.notes_database
notes_collection = db.get_collection("notes")

app = FastAPI(title="Trust Research Annotation API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ================= Prompts =================
EXTRACTION_PROMPT = """You are an expert annotation engine for customer trust research.
Your task is to analyse a customer review and extract TRUST-RELEVANT EVIDENCE. You must NOT assume that general positive sentiment is equivalent to customer trust.
The output will be used in a Human-in-the-Loop research system and must therefore be conservative, traceable, reproducible, and suitable for later statistical validation.

## STEP 1 — IDENTIFY THE TRUST TARGET
Allowed target types: PRODUCT, BRAND, PLATFORM, SERVICE, SELLER, MULTIPLE, UNCLEAR.
Never merge evidence about different targets without explicitly identifying them.

## STEP 2-6 — ASPECT-BASED TRUST EVIDENCE EXTRACTION
Evaluate F1. Functional Value, F2. Transaction Safety, F3. Ethical Behaviour, F4. Awareness/Reputation, F5. Interaction Experience.
- mentioned: true/false. (If false, polarity and strength MUST be null)
- polarity: 1, 0, -1. 
- evidence_strength: LOW, MEDIUM, HIGH.
- evidence: exact shortest span from text.

## STEP 7-9 — CONFIDENCE & TRUST LANGUAGE
Assign confidence (0.00-1.00). Identify explicit_trust_expression (true/false) and global research_interpretation.

Return ONLY valid JSON exactly matching this structure (no markdown):
{
  "target": { "type": "PRODUCT", "name": null },
  "explicit_trust": { "present": false, "polarity": null, "evidence": [] },
  "factors": {
    "F1_functional_value": { "mentioned": false, "polarity": null, "evidence_strength": null, "confidence": null, "evidence": [], "reason": "" },
    "F2_transaction_safety": { "mentioned": false, "polarity": null, "evidence_strength": null, "confidence": null, "evidence": [], "reason": "" },
    "F3_integrity": { "mentioned": false, "polarity": null, "evidence_strength": null, "confidence": null, "evidence": [], "reason": "" },
    "F4_reputation": { "mentioned": false, "polarity": null, "evidence_strength": null, "confidence": null, "evidence": [], "reason": "" },
    "F5_interaction": { "mentioned": false, "polarity": null, "evidence_strength": null, "confidence": null, "evidence": [], "reason": "" }
  },
  "overall_evidence_pattern": "insufficient_evidence",
  "research_interpretation": "",
  "requires_human_review": false,
  "review_flags": []
}"""

VALIDATION_PROMPT = """You are a research validation assistant.
You will receive: 1. The original customer review. 2. The original LLM annotation. 3. A human researcher's verified annotation.
Your task is NOT to decide which annotation is correct. Your task is to compare the two annotations independently for each factor (mentioned status, polarity, evidence strength, evidence span), identify disagreements, and produce structured data.

Disagreement types: MENTION_DISAGREEMENT, POLARITY_DISAGREEMENT, STRENGTH_DISAGREEMENT, EVIDENCE_DISAGREEMENT, NO_DISAGREEMENT.
For polarity disagreement, calculate absolute difference.

Return ONLY valid JSON exactly matching this structure (no markdown):
{
  "annotation_status": "human_verified",
  "llm_annotation_preserved": true,
  "factor_comparison": {
    "F1_functional_value": { "llm_value": {}, "human_value": {}, "agreement": true, "disagreement_types": [], "polarity_difference": 0 },
    "F2_transaction_safety": { "llm_value": {}, "human_value": {}, "agreement": true, "disagreement_types": [], "polarity_difference": 0 },
    "F3_integrity": { "llm_value": {}, "human_value": {}, "agreement": true, "disagreement_types": [], "polarity_difference": 0 },
    "F4_reputation": { "llm_value": {}, "human_value": {}, "agreement": true, "disagreement_types": [], "polarity_difference": 0 },
    "F5_interaction": { "llm_value": {}, "human_value": {}, "agreement": true, "disagreement_types": [], "polarity_difference": 0 }
  },
  "summary": { "factors_agreed": 0, "factors_disagreed": 0, "polarity_agreements": 0, "polarity_disagreements": 0, "mention_disagreements": 0, "strength_disagreements": 0 },
  "high_priority_disagreement": false,
  "high_priority_reasons": []
}"""

async def call_ai_json(system_prompt: str, user_content: str):
    try:
        ai_client = AsyncOpenAI(base_url=AI_BASE_URL, api_key=AI_API_KEY)
        response = await ai_client.chat.completions.create(
            model=AI_MODEL, 
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
            max_tokens=2500, temperature=0.1
        )         
        reply = response.choices[0].message.content.strip()
        start = reply.find('{')
        end = reply.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(reply[start : end + 1]), reply
        return None, reply
    except Exception as e:
        print(f"AI Call Error: {e}")
        return None, str(e)

def strength_to_num(val):
    if val == "HIGH": return 3
    if val == "MEDIUM": return 2
    if val == "LOW": return 1
    return None

# ================= Endpoints =================
@app.post("/api/notes")
async def create_note(note: NoteCreate):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    agent_reply, llm_data = None, None
    status = "raw" 

    if note.action == "agent":
        llm_data, agent_reply = await call_ai_json(EXTRACTION_PROMPT, note.content)
        status = "llm_annotated" if llm_data else "raw"

    # New DB Schema
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

@app.get("/api/notes")
async def get_notes():
    # Legacy fallback mapping included in output formatting
    cursor = notes_collection.find().sort("_id", -1).limit(50)
    notes = []
    async for doc in cursor:
        # Migration mapping for UI
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

@app.put("/api/notes/{note_id}/verify")
async def verify_note(note_id: str, update_data: VerifyUpdate):
    doc = await notes_collection.find_one({"_id": ObjectId(note_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    human_data = update_data.human_data
    llm_data = doc.get("llm_annotation", doc.get("llm_parsed_data", {}))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    # Automatically trigger the validation Agent to perform the comparison.
    validation_input = json.dumps({
        "review_text": doc.get("raw_data", {}).get("review_text", doc.get("content", "")),
        "llm_annotation": llm_data,
        "human_annotation": human_data
    })
    
    validation_data, _ = await call_ai_json(VALIDATION_PROMPT, validation_input)

    # Completely save the Human historical records without overwriting the original data of LLM.
    human_record = {
        "annotator_id": "human_researcher_1",
        "verified_at": now,
        "factors": human_data.get("factors", {})
    }

    await notes_collection.update_one(
        {"_id": ObjectId(note_id)},
        {
            "$push": {"human_annotations": human_record},
            "$set": {
                "final_annotation": human_data,
                "comparison": validation_data,
                "workflow.status": "human_verified",
                "workflow.last_updated_at": now,
                # Legacy updates
                "human_parsed_data": human_data,
                "validation_data": validation_data,
                "verification_status": "human_verified"
            }
        }
    )
    return {"success": True}

@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: str):
    await notes_collection.delete_one({"_id": ObjectId(note_id)})
    return {"success": True}


# ================= DETERMINISTIC ANALYTICS (Python Math Only) =================
@app.get("/api/analytics/dashboard")
async def get_dashboard_analytics():
    cursor = notes_collection.find()
    
    total = 0
    llm_count = 0
    human_count = 0
    
    # Factor aggregation tracking
    factors = {k: {"mentions": 0, "pos": 0, "neu": 0, "neg": 0, "strength_sum": 0, "strength_count": 0, "conf_sum": 0, "conf_count": 0, "polarity_sum": 0} for k in FACTOR_KEYS}
    
    # Disagreement tracking
    disagreements = {k: {"mention_diff": 0, "polarity_diff": 0, "strength_diff": 0, "total_comparisons": 0} for k in FACTOR_KEYS}

    async for doc in cursor:
        total += 1
        status = doc.get("workflow", {}).get("status", doc.get("verification_status", ""))
        
        if status in ["llm_annotated", "llm_only", "human_verified", "adjudicated"]:
            llm_count += 1
        if status in ["human_verified", "adjudicated"]:
            human_count += 1
            
        # Determine source of truth for math (Human verified preferred)
        active_data = doc.get("final_annotation") or doc.get("human_parsed_data") or doc.get("llm_annotation") or doc.get("llm_parsed_data")
        
        if active_data and "factors" in active_data:
            factors_data = active_data["factors"]
            if isinstance(factors_data, dict):
                for fk in FACTOR_KEYS:
                    f_data = factors_data.get(fk, {})
                    if f_data.get("mentioned") is True:
                        factors[fk]["mentions"] += 1
                        pol = f_data.get("polarity")
                        
                        if pol == 1: factors[fk]["pos"] += 1
                        elif pol == 0: factors[fk]["neu"] += 1
                        elif pol == -1: factors[fk]["neg"] += 1
                        
                        if pol is not None:
                            factors[fk]["polarity_sum"] += pol
                            
                        strength_val = strength_to_num(f_data.get("evidence_strength"))
                        if strength_val:
                            factors[fk]["strength_sum"] += strength_val
                            factors[fk]["strength_count"] += 1
                            
                        conf = f_data.get("confidence")
                        if conf is not None:
                            factors[fk]["conf_sum"] += conf
                            factors[fk]["conf_count"] += 1

        comp = doc.get("comparison") or doc.get("validation_data")
        if comp and "factor_comparison" in comp:
            for fk in FACTOR_KEYS:
                f_comp = comp["factor_comparison"].get(fk, {})
                disagreements[fk]["total_comparisons"] += 1
                dtypes = f_comp.get("disagreement_types", [])
                if "MENTION_DISAGREEMENT" in dtypes: disagreements[fk]["mention_diff"] += 1
                if "POLARITY_DISAGREEMENT" in dtypes: disagreements[fk]["polarity_diff"] += 1
                if "STRENGTH_DISAGREEMENT" in dtypes: disagreements[fk]["strength_diff"] += 1

    response = {
        "dataset_summary": {
            "total_reviews": total,
            "llm_annotated_reviews": llm_count,
            "human_verified_reviews": human_count,
            "verification_rate": round(human_count / total, 4) if total > 0 else 0
        },
        "factor_statistics": {},
        "factor_scores": {},
        "disagreement": {}
    }
    
    missing_factors = []
    raw_index_score = 0
    available_weight_sum = 0
    
    for fk in FACTOR_KEYS:
        f = factors[fk]
        mentions = f["mentions"]
        rate = mentions / total if total > 0 else 0
        
        response["factor_statistics"][fk] = {
            "mentioned_count": mentions,
            "mention_rate": round(rate, 4),
            "positive_count": f["pos"],
            "neutral_mixed_count": f["neu"],
            "negative_count": f["neg"],
            "positive_rate": round(f["pos"] / mentions, 4) if mentions > 0 else 0,
            "neutral_mixed_rate": round(f["neu"] / mentions, 4) if mentions > 0 else 0,
            "negative_rate": round(f["neg"] / mentions, 4) if mentions > 0 else 0,
            "mean_evidence_strength": round(f["strength_sum"] / f["strength_count"], 2) if f["strength_count"] > 0 else None,
            "mean_confidence": round(f["conf_sum"] / f["conf_count"], 2) if f["conf_count"] > 0 else None
        }
        
        score = round(f["polarity_sum"] / mentions, 4) if mentions > 0 else None
        response["factor_scores"][fk] = {
            "score": score,
            "mention_count": mentions,
            "mention_rate": round(rate, 4)
        }
        
        # Precisely handle the missing items and record only once.
        if score is None:
            missing_factors.append(fk)
        else:
            raw_index_score += score * TRUST_WEIGHTS[fk]
            available_weight_sum += TRUST_WEIGHTS[fk]
            
        d = disagreements[fk]
        comps = d["total_comparisons"]
        response["disagreement"][fk] = {
            "mention": {"numerator": d["mention_diff"], "denominator": comps, "rate": round(d["mention_diff"]/comps, 4) if comps>0 else None},
            "polarity": {"numerator": d["polarity_diff"], "denominator": comps, "rate": round(d["polarity_diff"]/comps, 4) if comps>0 else None},
            "strength": {"numerator": d["strength_diff"], "denominator": comps, "rate": round(d["strength_diff"]/comps, 4) if comps>0 else None}
        }

    # normalization
    if available_weight_sum > 0:
        trust_status = "CALCULATED_WITH_RENORMALIZATION" if missing_factors else "CALCULATED"
        index_score = raw_index_score / available_weight_sum
    else:
        trust_status = "NOT_CALCULATED_DUE_TO_NO_DATA"
        index_score = None
        
    response["trust_index"] = {
        "status": trust_status,
        "score": round(index_score, 4) if index_score is not None else None,
        "weights": TRUST_WEIGHTS,
        "coverage": round((len(FACTOR_KEYS) - len(missing_factors)) / len(FACTOR_KEYS), 4),
        "missing_factors": missing_factors,
        "validation_status": "PROPOSED_UNVALIDATED (RENORMALIZED)" if missing_factors else "PROPOSED_UNVALIDATED"
    }

    return response
