import json
import requests


class CopilotClient:
    def __init__(self, token: str):
        self.token = token
        self.url = "https://api.githubcopilot.com/chat/completions"

    def chat(self, model: str, messages, extra=None):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
        }

        # Merge tags/extra parameters (temperature, top_p, etc.)
        if extra:
            payload.update(extra)

        # Perform request
        resp = requests.post(self.url, headers=headers, data=json.dumps(payload))

        # Raise HTTP errors with full context
        try:
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(
                f"GitHub Copilot API error: {resp.status_code} {resp.text}"
            ) from e

        # Parse JSON
        try:
            return resp.json()
        except Exception as e:
            raise RuntimeError(
                f"GitHub Copilot returned invalid JSON: {resp.text}"
            ) from e
