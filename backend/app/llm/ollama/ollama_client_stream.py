# ollama_client_stream.py
import json
import requests
from typing import Dict, Any, Iterator, Optional

def ollama_generate_stream(
    model: str,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.2,
) -> Iterator[str]:
    """
    Streams tokens from Ollama /api/generate with stream=True.
    Yields text chunks as they arrive.
    """
    url = "http://localhost:11434/api/generate"
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system

    with requests.post(url, json=payload, stream=True, timeout=120) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            data = json.loads(line)
            if data.get("done"):
                break
            chunk = data.get("response", "")
            if chunk:
                yield chunk
