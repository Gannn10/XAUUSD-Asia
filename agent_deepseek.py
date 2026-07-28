import requests
import json
import logging

try:
    from config_scalping import OPENROUTER_API_KEY, LLM_TIMEOUT
except ImportError:
    OPENROUTER_API_KEY = ""
    LLM_TIMEOUT = 5.0

logger = logging.getLogger("Agent_DeepSeek")

def get_macro_bias(context: str) -> dict:
    """
    Meminta DeepSeek menganalisa bias makro ekonomi/trend sesi.
    """
    if not OPENROUTER_API_KEY:
        logger.warning("API Key OpenRouter tidak ditemukan. Fallback ke Neutral.")
        return {"bias": "NEUTRAL", "confidence": 0.5, "reason": "No API Key"}

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""Kamu adalah Analis Makro untuk bot Scalping XAUUSD Sesi Asia.
Tugas: Evaluasi kondisi saat ini dan tentukan bias trend (BULLISH, BEARISH, atau RANGING).
Konteks Pasar Saat Ini: {context}

Jawab hanya dalam format JSON seperti ini, tanpa teks tambahan:
{{"bias": "BULLISH/BEARISH/RANGING", "confidence": 0.8, "reason": "alasan singkat maksimal 1 kalimat"}}
"""

    data = {
        "model": "deepseek/deepseek-chat", # DeepSeek V3
        "messages": [
            {"role": "system", "content": "You are a professional quant analyst AI."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=LLM_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content']
        # Parse JSON output
        content = content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)
        return parsed
    except Exception as e:
        logger.error(f"DeepSeek API Error / Timeout: {e}")
        return {"bias": "NEUTRAL", "confidence": 0.5, "reason": "API Timeout/Error Fallback"}

if __name__ == "__main__":
    # Test script
    print(get_macro_bias("Harga sideways di range 2310-2315. Tidak ada news besar di Asia hari ini."))
