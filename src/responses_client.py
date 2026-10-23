"""Original Responses request builder and credential-safe standard-library transport."""
from __future__ import annotations
import json
import urllib.error
import urllib.request

class OpenAIResponsesAPIError(RuntimeError):
    """A deliberately small, credential-safe representation of an API error."""

    def __init__(self, diagnostic: dict):
        self.diagnostic = diagnostic
        super().__init__(diagnostic["message"])


def _extract_output_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str) and response["output_text"].strip():
        return response["output_text"]
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
            if content.get("type") == "refusal":
                raise ValueError("OpenAI model returned a refusal instead of structured output")
    raise ValueError("OpenAI response contains no output_text message")


def _contains_tool_output(response: dict) -> bool:
    allowed_types = {"message", "reasoning"}
    return any(item.get("type") not in allowed_types for item in response.get("output", []))


def build_model_input(prompt_template: str, model_id: str, jd_text: str) -> str:
    """Build the only model input; labels/profile/adapter fields are never included."""
    return (
        prompt_template.replace("{{MODEL_PROVIDER}}", "OpenAI")
        .replace("{{MODEL_ID}}", model_id)
        .replace("{{JD_TEXT}}", jd_text)
    )


def build_request_payload(context: dict) -> dict:
    config = context["config"]
    model_input = build_model_input(context["prompt"], config["model_id"], context["record"]["full_jd_text"])
    forbidden = ("historical_tracker_decision", "proposed_gold", "human gold", "gold label")
    if any(term in model_input.casefold() for term in forbidden):
        raise ValueError("Refusing to send a prompt that contains evaluation-label identifiers")
    return {
        "model": config["model_id"],
        "reasoning": {"effort": config["reasoning"]["effort"]},
        "input": model_input,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "job_requirement_extraction_v1",
                "strict": True,
                "schema": context["schema"],
            }
        },
        "max_output_tokens": config["model_parameters"]["max_output_tokens"],
        "store": config["model_parameters"]["store"],
    }


def non_sensitive_request_configuration(payload: dict) -> dict:
    """Return only request fields that are safe to display in diagnostics."""
    text_format = payload.get("text", {}).get("format", {})
    return {
        "model": payload.get("model"),
        "reasoning_effort": payload.get("reasoning", {}).get("effort"),
        "temperature_sent": "temperature" in payload,
        "max_output_tokens": payload.get("max_output_tokens"),
        "structured_output": {
            "parameter_path": "text.format",
            "type": text_format.get("type"),
            "name": text_format.get("name"),
            "strict": text_format.get("strict"),
        },
        "tools_sent": "tools" in payload,
    }


def _safe_http_error_diagnostic(exc: urllib.error.HTTPError) -> dict:
    """Extract only OpenAI's structured error fields; never expose headers/body wholesale."""
    parsed = {}
    try:
        body = exc.read().decode("utf-8")
        decoded = json.loads(body)
        parsed = decoded.get("error", {}) if isinstance(decoded, dict) else {}
    except (UnicodeDecodeError, json.JSONDecodeError, OSError):
        pass
    if not isinstance(parsed, dict):
        parsed = {}
    request_id = exc.headers.get("x-request-id") if exc.headers else None
    request_id = request_id or parsed.get("request_id")
    message = parsed.get("message")
    if not isinstance(message, str) or not message.strip():
        message = f"OpenAI Responses API returned HTTP {exc.code}"
    return {
        "status_code": exc.code,
        "type": parsed.get("type"),
        "code": parsed.get("code"),
        "param": parsed.get("param"),
        "message": message,
        "request_id": request_id,
    }


def _post_openai_response(endpoint: str, api_key: str, payload: dict) -> dict:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        diagnostic = _safe_http_error_diagnostic(exc)
        # Do not rely on a provider error message to keep credentials out of output.
        diagnostic["message"] = diagnostic["message"].replace(api_key, "[REDACTED]")
        raise OpenAIResponsesAPIError(diagnostic) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("OpenAI Responses API request failed before a response was received") from exc
