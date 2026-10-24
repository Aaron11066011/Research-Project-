EXTRACTION_PROMPT = """You are an expert annotation engine for customer trust research.
Your task is to analyse a customer review and extract TRUST-RELEVANT EVIDENCE. You must NOT assume that general positive sentiment is equivalent to customer trust.
The output will be used in a Human-in-the-Loop research system and must therefore be conservative, traceable, reproducible, and suitable for later statistical validation.

## STEP 1 — IDENTIFY THE TRUST TARGET
Allowed target types: PRODUCT, BRAND, PLATFORM, SERVICE, SELLER, MULTIPLE, UNCLEAR.
Never merge evidence about different targets without explicitly identifying them.

## STEP 2-6 — ASPECT-BASED TRUST EVIDENCE EXTRACTION
Evaluate F1. Functional Value and Service Benefit, F2. Transaction Safety and Risk Protection, F3. Ethical Behaviour and Integrity of the Platform, F4. Awareness / Reputational Signal, F5. Positive Interaction Experience.
- mentioned: true/false. (If false, polarity and strength MUST be null)
- polarity: 1, 0, -1. 
- evidence_strength: LOW, MEDIUM, HIGH.
- evidence: exact shortest span from text. 
  CRITICAL RULES FOR EVIDENCE EXTRACTION:
  1. MUST be an exact, contiguous verbatim substring copied directly from the original text. Do not paraphrase.
  2. Do NOT extract single words, pronouns, or isolated adjectives (e.g., never extract just "i", "it", "good", or "issue").
  3. MUST extract a meaningful phrase or full clause (minimum 4-5 words) to preserve context (e.g., extract "there is a lot of extra fabric at the chest" instead of just "extra fabric").

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
