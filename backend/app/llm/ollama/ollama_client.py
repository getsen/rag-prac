# ollama_client.py
import requests
from typing import Dict, Any, Optional


def ollama_generate(
    model: str,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.2,
) -> str:
    url = "http://localhost:11434/api/generate"
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system

    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data.get("response", "")
