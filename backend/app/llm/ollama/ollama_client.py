import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for non-streaming text generation from Ollama."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
    ):
        """
        Initialize OllamaClient.
        
        Args:
            base_url: Base URL for Ollama API (default: http://localhost:11434)
            timeout: Request timeout in seconds (default: 120)
        """
        self.base_url = base_url
        self.timeout = timeout
        self.api_endpoint = f"{base_url}/api/generate"
        logger.info(f"OllamaClient initialized with base_url={base_url}, timeout={timeout}")

    def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        """
        Generate text from Ollama.
        
        Args:
            model: Model name to use
            prompt: Input prompt text
            system: Optional system prompt
            temperature: Sampling temperature (0-1)
            
        Returns:
            Generated text response
        """
        logger.debug(f"Generating from model={model} with temperature={temperature}")
        
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        try:
            r = requests.post(self.api_endpoint, json=payload, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            response = data.get("response", "")
            logger.debug(f"Generated {len(response)} characters")
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating from Ollama: {e}")
            raise


# Global client instance for backward compatibility
_client = OllamaClient()


def ollama_generate(
    model: str,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.2,
) -> str:
    """
    Legacy function for backward compatibility.
    Generate text from Ollama without streaming.
    """
    return _client.generate(
        model=model,
        prompt=prompt,
        system=system,
        temperature=temperature,
    )
