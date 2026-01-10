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
        use_cloud: bool = False,
        api_key: Optional[str] = None,
    ):
        """
        Initialize OllamaClient.
        
        Args:
            base_url: Base URL for Ollama API (default: http://localhost:11434)
            timeout: Request timeout in seconds (default: 120)
            use_cloud: Use Ollama Cloud service instead of localhost (default: False)
            api_key: API key for Ollama Cloud service
        """
        self.use_cloud = use_cloud
        
        if use_cloud:
            if not api_key:
                raise ValueError("api_key is required when use_cloud=True")
            # For Ollama Cloud, the base URL can be custom (provided by Ollama)
            # or default to the cloud service endpoint
            # Using the provided base_url if it looks like a cloud endpoint, otherwise use default
            if "ollama" in base_url.lower() or base_url.startswith("http"):
                self.base_url = base_url
            else:
                self.base_url = "http://localhost:11434"  # Default cloud endpoint
            self.headers = {"Authorization": f"Bearer {api_key}"}
            logger.info(f"OllamaClient initialized to use Ollama Cloud at {self.base_url}")
        else:
            self.base_url = base_url
            self.headers = {}
            logger.info(f"OllamaClient initialized with base_url={base_url}")
        
        self.timeout = timeout
        self.api_endpoint = f"{self.base_url}/api/generate"
        logger.info(f"OllamaClient ready - timeout={timeout}")

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
            r = requests.post(
                self.api_endpoint,
                json=payload,
                timeout=self.timeout,
                headers=self.headers,
            )
            r.raise_for_status()
            data = r.json()
            response = data.get("response", "")
            logger.debug(f"Generated {len(response)} characters")
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating from Ollama: {e}")
            raise


# Global client instance for backward compatibility
def _get_client() -> OllamaClient:
    """Get or create global client with settings from config."""
    from app.config import settings
    return OllamaClient(
        base_url=settings.ollama_base_url,
        timeout=120,
        use_cloud=settings.use_ollama_cloud,
        api_key=settings.ollama_api_key,
    )


_client = _get_client()


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
