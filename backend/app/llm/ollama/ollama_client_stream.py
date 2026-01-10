import json
import logging
import requests
from typing import Dict, Any, Iterator, Optional

logger = logging.getLogger(__name__)


class OllamaStreamClient:
    """Client for streaming text generation from Ollama."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
    ):
        """
        Initialize OllamaStreamClient.
        
        Args:
            base_url: Base URL for Ollama API (default: http://localhost:11434)
            timeout: Request timeout in seconds (default: 120)
        """
        self.base_url = base_url
        self.timeout = timeout
        self.api_endpoint = f"{base_url}/api/generate"
        logger.info(f"OllamaStreamClient initialized with base_url={base_url}, timeout={timeout}")

    def generate_stream(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
    ) -> Iterator[str]:
        """
        Stream tokens from Ollama /api/generate.
        
        Args:
            model: Model name to use
            prompt: Input prompt text
            system: Optional system prompt
            temperature: Sampling temperature (0-1)
            
        Yields:
            Text chunks as they arrive from the model
        """
        logger.debug(f"Streaming from model={model} with temperature={temperature}")
        
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        try:
            with requests.post(self.api_endpoint, json=payload, stream=True, timeout=self.timeout) as r:
                r.raise_for_status()
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("done"):
                        logger.debug(f"Stream completed")
                        break
                    chunk = data.get("response", "")
                    if chunk:
                        yield chunk
        except requests.exceptions.RequestException as e:
            logger.error(f"Error streaming from Ollama: {e}")
            raise


# Global client instance for backward compatibility
_stream_client = OllamaStreamClient()


def ollama_generate_stream(
    model: str,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.2,
) -> Iterator[str]:
    """
    Legacy function for backward compatibility.
    Streams tokens from Ollama /api/generate with stream=True.
    Yields text chunks as they arrive.
    """
    return _stream_client.generate_stream(
        model=model,
        prompt=prompt,
        system=system,
        temperature=temperature,
    )
