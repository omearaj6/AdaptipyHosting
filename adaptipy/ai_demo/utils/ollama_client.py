import os
import requests

def ollama_generate(prompt: str) -> str:
    base_url = os.environ.get("OLLAMA_URL")
    api_key = os.environ.get("OLLAMA_API_KEY")
    model = os.getenv("OLLAMA_MODEL", "codellama:7b")

    if not base_url or not api_key:
        raise Exception("OLLAMA_URL or OLLAMA_API_KEY not set")

    base_url = base_url.rstrip("/")

    r = requests.post(
        f"{base_url}/api/generate",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=120,
    )

    r.raise_for_status()

    data = r.json()

    if "response" not in data:
        raise Exception(f"Ollama returned unexpected response: {data}")

    return data["response"]