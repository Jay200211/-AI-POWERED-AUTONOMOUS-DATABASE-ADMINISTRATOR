"""LLM engine - simple, complete, with health check."""
import requests
from typing import List, Dict, Optional
from config import CONFIG


class OllamaLLM:
    def __init__(self, model: Optional[str] = None, temperature: float = 0.0):
        self.base_url = CONFIG.ollama_url.rstrip("/")
        self.model = model or CONFIG.ollama_model_fast
        self.temperature = temperature

    def chat(self, messages: List[Dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": 1024},
        }
        r = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=120
        )
        r.raise_for_status()
        return r.json()["message"]["content"]

    def health(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.ok
        except requests.RequestException:
            return False


class ModelRouter:
    def __init__(self):
        self.fast = OllamaLLM(model=CONFIG.ollama_model_fast)
        self.smart = OllamaLLM(model=CONFIG.ollama_model_smart)
        self.last_used: Optional[str] = None

    def pick(self, user_message: str) -> OllamaLLM:
        msg = user_message.lower()
        smart_words = ["explain", "why", "analyze", "compare", "complex", "join"]
        if any(w in msg for w in smart_words) or len(user_message.split()) > 15:
            self.last_used = "smart"
            return self.smart
        self.last_used = "fast"
        return self.fast

    def health(self) -> bool:
        return self.fast.health() and self.smart.health()
