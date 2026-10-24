import json
from openai import AsyncOpenAI
from app.config import AI_BASE_URL, AI_API_KEY, AI_MODEL

async def call_ai_json(system_prompt: str, user_content: str):
    try:
        ai_client = AsyncOpenAI(base_url=AI_BASE_URL, api_key=AI_API_KEY)
        response = await ai_client.chat.completions.create(
            model=AI_MODEL, 
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
            max_tokens=10000, temperature=0.1
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
