import os

# ================= Configuration & Environment =================
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://maas.qwencloudapi.com/compatible-mode/v1")
AI_API_KEY = os.getenv("AI_API_KEY", "AI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "qwen3.8-max")

# Trust Index Weights Config 
TRUST_WEIGHT_SCHEMES = {
    "equal": {
        "F1_functional_value": 0.20,
        "F2_transaction_safety": 0.20,
        "F3_integrity": 0.20,
        "F4_reputation": 0.20,
        "F5_interaction": 0.20
    },
    "literature_proposed": {
        "F1_functional_value": 0.25,
        "F2_transaction_safety": 0.25,
        "F3_integrity": 0.20,
        "F4_reputation": 0.15,
        "F5_interaction": 0.15
    }
}

FACTOR_KEYS = list(TRUST_WEIGHT_SCHEMES["equal"].keys())
