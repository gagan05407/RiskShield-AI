import os
import requests
from typing import List, Tuple, Optional, Dict, Any

# Recommended & Fallback Models Per Provider
FALLBACK_MODELS = {
    "Google Gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ],
    "Groq": [
        "openai/gpt-oss-120b",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "qwen-2.5-72b-instruct",
        "gemma2-9b-it",
        "deepseek-r1-distill-llama-70b"
    ],
    "OpenAI": [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4-turbo"
    ],
    "OpenRouter": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "deepseek/deepseek-r1:free"
    ]
}

DEFAULT_MODELS = {
    "Google Gemini": "gemini-2.5-flash",
    "Groq": "openai/gpt-oss-120b",
    "OpenAI": "gpt-4o-mini",
    "OpenRouter": "meta-llama/llama-3.3-70b-instruct:free"
}


def extract_text_from_response(res: Any) -> str:
    """
    Safely extracts clean string text from an LLM response object or content attribute.
    Handles strings, lists of content blocks/dicts, and LangChain message objects.
    Prevents 'list object has no attribute strip' crashes.
    """
    if hasattr(res, "content"):
        content = res.content
    else:
        content = res

    if isinstance(content, str):
        return content.strip()
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict):
                text_parts.append(str(part.get("text", str(part))))
            else:
                text_parts.append(str(part))
        return " ".join(text_parts).strip()
    else:
        return str(content).strip()


def validate_model_for_provider(provider: str, model_name: Optional[str]) -> Tuple[bool, str]:
    """
    Validates that model_name belongs to and is compatible with provider.
    """
    if not model_name or not str(model_name).strip():
        return False, "Model name cannot be empty."

    m_lower = str(model_name).lower().strip()
    
    if provider == "Groq":
        if "gemini" in m_lower:
            return False, f"Selected model '{model_name}' is a Gemini model and is NOT compatible with provider 'Groq'."
    elif provider == "Google Gemini":
        if "llama" in m_lower or "qwen" in m_lower or "gemma" in m_lower or "gpt-oss" in m_lower or "deepseek" in m_lower:
            return False, f"Selected model '{model_name}' is NOT compatible with provider 'Google Gemini'."
    elif provider == "OpenAI":
        if "gemini" in m_lower or "llama" in m_lower or "qwen" in m_lower or "gemma" in m_lower:
            return False, f"Selected model '{model_name}' is NOT compatible with provider 'OpenAI'."
            
    return True, ""


def get_available_models(provider: str, api_key: Optional[str] = None) -> List[str]:
    """
    Dynamically fetches currently available text-generation models from the provider API if an API key is provided.
    Filters out non-text models (audio, embedding, tts, vision-only).
    Falls back to a curated list of modern production text models if API query fails or key is missing.
    """
    base_fallbacks = list(FALLBACK_MODELS.get(provider, ["default"]))

    if not api_key or not str(api_key).strip():
        return base_fallbacks

    api_key = str(api_key).strip()

    try:
        if provider == "Groq":
            headers = {"Authorization": f"Bearer {api_key}"}
            res = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                models = []
                for m in data.get("data", []):
                    m_id = m.get("id", "") if isinstance(m, dict) else str(m)
                    if m_id and not m_id.startswith("whisper"):
                        models.append(m_id)
                active_models = [m for m in models if "mixtral-8x7b-32768" not in m]
                if "openai/gpt-oss-120b" not in active_models:
                    active_models.insert(0, "openai/gpt-oss-120b")
                if active_models:
                    return active_models

        elif provider == "Google Gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                models = []
                for m in data.get("models", []):
                    if isinstance(m, dict):
                        name = m.get("name", "").replace("models/", "")
                        methods = m.get("supportedGenerationMethods", [])
                    else:
                        name = str(m).replace("models/", "")
                        methods = ["generateContent"]

                    name_lower = name.lower()
                    # Filter ONLY text generation models compatible with RiskShield chat/investigation workflow
                    if "gemini" in name_lower and not any(non_text in name_lower for non_text in ["embedding", "imagen", "veo", "tts", "stt", "bison", "aqa"]):
                        if not methods or "generateContent" in methods:
                            models.append(name)

                if models:
                    models.sort(key=lambda x: ("2.5" in x or "1.5" in x or "2.0" in x), reverse=True)
                    return models

        elif provider == "OpenAI":
            headers = {"Authorization": f"Bearer {api_key}"}
            res = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                models = [m.get("id", "") for m in data.get("data", []) if isinstance(m, dict) and "gpt" in m.get("id", "")]
                if models:
                    return sorted(models)

        elif provider == "OpenRouter":
            headers = {"Authorization": f"Bearer {api_key}"}
            res = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                models = [m.get("id", "") for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
                if models:
                    return models[:25]

    except Exception:
        pass

    return base_fallbacks


def test_api_connection(provider: str, api_key: str, model_name: Optional[str] = None) -> Tuple[bool, str, str]:
    """
    Tests API key connection by executing a minimal text generation request against the selected model.
    Returns: (success: bool, user_friendly_message: str, technical_details: str)
    Never leaks API keys in error output.
    """
    if not api_key or not str(api_key).strip():
        return False, "API key cannot be empty.", "No API key was provided in the input field."

    api_key = str(api_key).strip()
    target_model = model_name or DEFAULT_MODELS.get(provider, "default")

    # Validate model compatibility
    is_valid_model, val_msg = validate_model_for_provider(provider, target_model)
    if not is_valid_model:
        return False, f"Incompatible model selection: {val_msg}", val_msg

    try:
        if provider == "Google Gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(google_api_key=api_key, model=target_model, temperature=0.0)
            res = llm.invoke("Reply only with: API connection successful.")
            res_text = extract_text_from_response(res)
            return True, f"Connected to Google Gemini ({target_model})", f"Response: {res_text}"

        elif provider == "Groq":
            from langchain_groq import ChatGroq
            llm = ChatGroq(groq_api_key=api_key, model=target_model, temperature=0.0)
            res = llm.invoke("Reply only with: API connection successful.")
            res_text = extract_text_from_response(res)
            return True, f"Connected to Groq ({target_model})", f"Response: {res_text}"

        elif provider == "OpenAI":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(openai_api_key=api_key, model=target_model, temperature=0.0)
            res = llm.invoke("Reply only with: API connection successful.")
            res_text = extract_text_from_response(res)
            return True, f"Connected to OpenAI ({target_model})", f"Response: {res_text}"

        elif provider == "OpenRouter":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                openai_api_key=api_key,
                openai_api_base="https://openrouter.ai/api/v1",
                model=target_model,
                temperature=0.0
            )
            res = llm.invoke("Reply only with: API connection successful.")
            res_text = extract_text_from_response(res)
            return True, f"Connected to OpenRouter ({target_model})", f"Response: {res_text}"

        else:
            return False, f"Unsupported provider: {provider}", "Provider name not recognized."

    except Exception as e:
        err_raw = str(e)
        if api_key in err_raw:
            err_raw = err_raw.replace(api_key, "[REDACTED]")

        if "401" in err_raw or "Unauthenticated" in err_raw or "invalid_api_key" in err_raw or "Invalid API Key" in err_raw:
            user_msg = "Invalid API Key. Please verify your credentials."
        elif "403" in err_raw or "PermissionDenied" in err_raw or "access_denied" in err_raw:
            user_msg = "Permission Denied. Check your API key permissions or account billing status."
        elif "404" in err_raw or "NOT_FOUND" in err_raw or "model_not_found" in err_raw or "decommissioned" in err_raw:
            user_msg = f"Model '{target_model}' is unavailable or decommissioned. Click 'Refresh Available Models' to select an active model."
        elif "429" in err_raw or "RESOURCE_EXHAUSTED" in err_raw or "rate_limit" in err_raw:
            user_msg = "Rate limit or quota exceeded. Please wait a moment or check your API quota."
        elif "500" in err_raw or "503" in err_raw or "UNAVAILABLE" in err_raw:
            user_msg = "Provider service is temporarily unavailable. Please try again shortly."
        elif "timeout" in err_raw.lower() or "connection error" in err_raw.lower():
            user_msg = "Network connection timeout. Check your network connection."
        else:
            user_msg = "Connection failed. See technical details below."

        return False, user_msg, err_raw
