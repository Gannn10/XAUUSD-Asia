import requests
import json
import logging

try:
    from config_scalping import OPENROUTER_API_KEY, LLM_TIMEOUT
except ImportError:
    OPENROUTER_API_KEY = ""
    LLM_TIMEOUT = 5.0

logger = logging.getLogger("Agent_Hermes")

def evaluate_execution(xgb_signal: dict, deepseek_bias: dict, market_context: dict) -> dict:
    """
    Hermes mengevaluasi sinyal dari XGBoost dan DeepSeek untuk memberi keputusan final (EXECUTE / HOLD).
    """
    if not OPENROUTER_API_KEY:
        logger.warning("API Key OpenRouter tidak ditemukan. Fallback ke logika XGBoost.")
        # Fallback langsung eksekusi jika XGBoost yakin
        action = "EXECUTE" if xgb_signal.get("confidence", 0) > 0.6 else "HOLD"
        return {"action": action, "lot_multiplier": 1.0, "reason": "Fallback XGBoost"}

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""Kamu adalah Eksekutor Trading (Agentic AI) untuk Sesi Asia XAUUSD.
Tugas: Putuskan apakah akan EXECUTE sinyal dari XGBoost atau HOLD.

Input Data:
1. Sinyal XGBoost: {xgb_signal} (Akurasi/Confidence harus > 0.60 untuk trading normal)
2. Bias DeepSeek: {deepseek_bias}
3. Kondisi Pasar: {market_context}

Aturan Ketat:
- Jika Sinyal XGBoost searah dengan Bias DeepSeek = EXECUTE dengan lot_multiplier 1.0
- Jika Sinyal XGBoost BERLAWANAN arah (Counter-Trend), eksekusi hanya jika XGBoost confidence > 0.80. Berikan lot_multiplier 0.5. Jika < 0.80, HOLD.
- Jika Bias NEUTRAL atau RANGING = EXECUTE jika XGBoost confidence > 0.65.

Output HANYA format JSON valid tanpa teks lain:
{{"action": "EXECUTE" atau "HOLD", "lot_multiplier": 1.0 atau 0.5, "reason": "Alasan 1 kalimat singkat"}}
"""

    # Menggunakan hermes-3 (atau hermes-2-pro) yang sanggat ahli mengikuti instruksi dan memformat JSON
    data = {
        "model": "nousresearch/hermes-3-llama-3.1-405b", 
        "messages": [
            {"role": "system", "content": "You are a rigid rule-based execution engine."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=LLM_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content']
        # Bersihkan format JSON dari markdown kalau ada
        content = content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)
        return parsed
    except Exception as e:
        logger.error(f"Hermes API Error / Timeout: {e}. Fallback ke murni XGBoost.")
        action = "EXECUTE" if xgb_signal.get("confidence", 0) > 0.60 else "HOLD"
        return {"action": action, "lot_multiplier": 1.0, "reason": "API Timeout Fallback"}

if __name__ == "__main__":
    # Test skenario counter-trend
    test_xgb = {"direction": "BUY", "confidence": 0.85}
    test_ds = {"bias": "BEARISH", "confidence": 0.7, "reason": "USD menguat"}
    test_ctx = {"price": 2300, "volatility": "low"}
    print(evaluate_execution(test_xgb, test_ds, test_ctx))
