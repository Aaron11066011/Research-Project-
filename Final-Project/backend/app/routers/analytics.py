from typing import Dict, Any, Tuple
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from app.database import notes_collection
from app.config import FACTOR_KEYS, TRUST_WEIGHT_SCHEMES
from app.utils import strength_to_num

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

class CustomWeightsInput(BaseModel):
    F1_functional_value: float = Field(..., ge=0)
    F2_transaction_safety: float = Field(..., ge=0)
    F3_integrity: float = Field(..., ge=0)
    F4_reputation: float = Field(..., ge=0)
    F5_interaction: float = Field(..., ge=0)

class UnifiedDashboardRequest(BaseModel):
    analysis_basis: str
    custom_weights: CustomWeightsInput

# Extract the decision logic for generating public data snapshots
def resolve_active_snapshot(doc: dict, analysis_basis: str) -> Tuple[Any, str, bool, bool]:
    status = doc.get("workflow", {}).get("status", doc.get("verification_status", ""))
    llm_snap = doc.get("llm_annotation") or doc.get("llm_parsed_data")
    human_snap = doc.get("final_annotation") or doc.get("human_parsed_data")
    
    has_llm = bool(llm_snap)
    has_human = status in ["human_verified", "adjudicated"] and bool(human_snap)
    
    if analysis_basis == "ai_original" and has_llm: return llm_snap, "AI_ONLY", has_llm, has_human
    if analysis_basis == "human_verified" and has_human: return human_snap, "HUMAN_VERIFIED", has_llm, has_human
    if analysis_basis == "hybrid":
        if has_human: return human_snap, "HUMAN_VERIFIED", has_llm, has_human
        if has_llm: return llm_snap, "AI_ONLY", has_llm, has_human
    return None, None, has_llm, has_human

def calculate_trust_index_detailed(factor_scores: Dict[str, float], raw_weights: Dict[str, float]) -> Dict[str, Any]:
    available_factors = {k: v for k, v in factor_scores.items() if v is not None}
    missing_factors = [k for k, v in factor_scores.items() if v is None]
    valid_weight_sum = sum(raw_weights.get(k, 0) for k in available_factors.keys())
    
    if valid_weight_sum <= 0:
        return {"score": None, "effective_weights": {}, "contributions": {}, "missing_factors": missing_factors, "status": "NOT_CALCULATED_DUE_TO_ZERO_WEIGHT_OR_NO_DATA"}

    effective_weights = {k: (raw_weights.get(k, 0) / valid_weight_sum) for k in available_factors.keys()}
    contributions = {k: (available_factors[k] * effective_weights[k]) for k in available_factors.keys()}
    return {
        "score": round(sum(contributions.values()), 4),
        "effective_weights": {k: round(v, 4) for k, v in effective_weights.items()},
        "contributions": {k: round(v, 4) for k, v in contributions.items()},
        "missing_factors": missing_factors,
        "status": "CALCULATED_WITH_RENORMALIZATION" if missing_factors else "CALCULATED"
    }

async def _get_dataset_aggregations(analysis_basis: str) -> Tuple[Dict, Dict, Dict]:
    cursor = notes_collection.find()
    stats = {"total": 0, "llm_count": 0, "human_count": 0, "ai_contrib": 0, "human_contrib": 0}
    factors = {k: {"mentions": 0, "pos": 0, "neu": 0, "neg": 0, "strength_sum": 0, "strength_count": 0, "polarity_sum": 0} for k in FACTOR_KEYS}
    
    async for doc in cursor:
        stats["total"] += 1
        active_data, contributed_as, has_llm, has_human = resolve_active_snapshot(doc, analysis_basis)
        
        if has_llm or has_human: stats["llm_count"] += 1
        if has_human: stats["human_count"] += 1
        
        if active_data and "factors" in active_data:
            if contributed_as == "AI_ONLY": stats["ai_contrib"] += 1
            if contributed_as == "HUMAN_VERIFIED": stats["human_contrib"] += 1
            
            for fk in FACTOR_KEYS:
                f_data = active_data["factors"].get(fk, {})
                if f_data.get("mentioned"):
                    factors[fk]["mentions"] += 1
                    pol = f_data.get("polarity")
                    if pol == 1: factors[fk]["pos"] += 1
                    elif pol == 0: factors[fk]["neu"] += 1
                    elif pol == -1: factors[fk]["neg"] += 1
                    if pol is not None: factors[fk]["polarity_sum"] += pol

    total_contrib = stats["ai_contrib"] + stats["human_contrib"]
    return factors, {
        "total_reviews": stats["total"], "llm_annotated_reviews": stats["llm_count"],
        "human_verified_reviews": stats["human_count"],
        "verification_rate": round(stats["human_count"] / stats["total"], 4) if stats["total"] > 0 else 0
    }, {
        "analysis_basis": analysis_basis.upper(), "ai_only_contribution_count": stats["ai_contrib"],
        "human_verified_contribution_count": stats["human_contrib"], "total_reviews_included": total_contrib,
    }

@router.post("/dashboard/unified")
async def get_unified_dashboard(req: UnifiedDashboardRequest):
    if req.analysis_basis not in ["ai_original", "human_verified", "hybrid"]: raise HTTPException(400, "Unknown analysis basis")
    factors, dataset_summary, analysis_metadata = await _get_dataset_aggregations(req.analysis_basis)
    
    factor_scores, factor_statistics = {}, {}
    total = analysis_metadata["total_reviews_included"]
    for fk in FACTOR_KEYS:
        mentions = factors[fk]["mentions"]
        rate = mentions / total if total > 0 else 0
        score = (factors[fk]["polarity_sum"] / mentions) if mentions > 0 else None
        factor_scores[fk] = {"score": round(score, 4) if score is not None else None, "mention_count": mentions, "mention_rate": round(rate, 4)}
        factor_statistics[fk] = {
            "positive_rate": round(factors[fk]["pos"] / mentions, 4) if mentions > 0 else 0,
            "neutral_mixed_rate": round(factors[fk]["neu"] / mentions, 4) if mentions > 0 else 0,
            "negative_rate": round(factors[fk]["neg"] / mentions, 4) if mentions > 0 else 0,
        }

    fs_index = {k: v["score"] for k, v in factor_scores.items()}
    baseline_result = calculate_trust_index_detailed(fs_index, {k: 0.20 for k in FACTOR_KEYS})
    adjusted_result = calculate_trust_index_detailed(fs_index, req.custom_weights.model_dump())

    diff, abs_diff = None, None
    if baseline_result["score"] is not None and adjusted_result["score"] is not None:
        diff = round(adjusted_result["score"] - baseline_result["score"], 4)
        abs_diff = round(abs(diff), 4)

    return {"success": True, "dataset_summary": dataset_summary, "analysis_metadata": analysis_metadata, "factor_scores": factor_scores, "factor_statistics": factor_statistics, "baseline": baseline_result, "adjusted": adjusted_result, "comparison": {"signed_difference": diff, "absolute_difference": abs_diff}}

@router.get("/evidence")
async def get_factor_evidence(factor: str = Query(...), analysis_basis: str = Query("hybrid"), page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=50)):
    if analysis_basis not in ["ai_original", "human_verified", "hybrid"]: raise HTTPException(400, "Unknown basis")
    cursor = notes_collection.find().sort("_id", -1)
    records = []
    
    async for doc in cursor:
        active_data, contributed_as, _, _ = resolve_active_snapshot(doc, analysis_basis)
        if active_data and "factors" in active_data and active_data["factors"].get(factor, {}).get("mentioned"):
            prov = doc.get("llm_provenance", {}) or {}
            history = [{"event": "LLM Annotation", "timestamp": prov.get("generated_at", doc.get("created_at", "")), "model": prov.get("model", "Unknown")}]
            for h in doc.get("human_annotations", []):
                history.append({"event": "Human Verification", "timestamp": h.get("verified_at", ""), "model": h.get("annotator_id", "Unknown")})
            
            records.append({
                "id": str(doc["_id"]), "review_text": doc.get("raw_data", {}).get("review_text", doc.get("content", "")),
                "contributed_as": contributed_as, "factor_data": active_data["factors"][factor],
                "llm_snapshot_factor": (doc.get("llm_annotation") or doc.get("llm_parsed_data") or {}).get("factors", {}).get(factor),
                "human_snapshot_factor": (doc.get("final_annotation") or doc.get("human_parsed_data") or {}).get("factors", {}).get(factor),
                "history": history
            })

    total = len(records)
    return {"success": True, "data": records[(page - 1) * limit : page * limit], "pagination": {"total": total, "page": page, "limit": limit, "total_pages": (total + limit - 1) // limit}}
