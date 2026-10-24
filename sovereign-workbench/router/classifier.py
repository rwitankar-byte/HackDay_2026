"""
Model Router and Request Classifier for Karyalaya AI.
Routes incoming requests to the appropriate local Ollama model based on task type.
Strictly local, no internet fallback.
"""

import os
import yaml
import requests
import json
from typing import Dict, Any, Tuple

# Path to model registry yaml
REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "model_registry.yaml")

class ModelRouter:
    def __init__(self, config_path: str = REGISTRY_PATH):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Loads model definitions from YAML config."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Model registry configuration not found at {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def classify_request(self, text_input: str, has_image: bool = False) -> Tuple[str, Dict[str, Any], str]:
        """
        Classifies request into 'code', 'vision', or 'document'.
        Returns (task_type, model_config, rationale).
        """
        if has_image:
            task_type = "vision"
            rationale = "Image/scan upload detected. Routing to vision pipeline."
        else:
            code_keywords = [
                "python", "code", "script", "function", "def ", "class ", "import ",
                "docker", "sql", "html", "css", "js", "bug", "refactor", "syntax", "api"
            ]
            text_lower = text_input.lower()
            if any(kw in text_lower for kw in code_keywords):
                task_type = "code"
                rationale = "Code/programming keywords identified in user prompt."
            else:
                task_type = "document"
                rationale = "Document reasoning/SOP/approval task identified."

        model_config = self.config["models"].get(task_type, self.config["models"]["document"])
        log_entry = f"[MODEL ROUTER] Task: '{task_type}' | Model: '{model_config['name']}' | Rationale: {rationale}"
        print(log_entry)
        return task_type, model_config, log_entry

    def generate(self, model_name: str, prompt: str, system_prompt: str = None, temperature: float = 0.2) -> str:
        """
        Queries the local Ollama HTTP endpoint directly.
        Raises RuntimeError if local Ollama fails (strictly air-gapped, no fallback).
        """
        url = f"{self.config.get('default_endpoint', 'http://localhost:11434')}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Local Ollama server call failed for model '{model_name}': {e}. Ensure 'ollama serve' is running.")


if __name__ == "__main__":
    # Self-test classifier
    router = ModelRouter()
    _, cfg, log = router.classify_request("Write a python script to parse CSV files")
    print(log)
    _, cfg, log = router.classify_request("Draft an inspection approval note per SOP")
    print(log)
