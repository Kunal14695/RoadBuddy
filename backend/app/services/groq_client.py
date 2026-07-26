import json
import re
import httpx
import asyncio
from app.core.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"


async def call_groq_native(messages: list[dict], temperature: float = 0.7, max_tokens: int = 3000, json_mode: bool = False) -> str:
    """
    Directly calls the Groq completions API using the configured Groq API Key and Llama model.
    """
    api_key = settings.groq_api_key.strip() if settings.groq_api_key else ""
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}


    last_exc = None
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            try:
                res = await client.post(GROQ_URL, headers=headers, json=payload)
                if res.status_code == 429 or 500 <= res.status_code < 600:
                    await asyncio.sleep((attempt + 1) * 3)
                    continue
                res.raise_for_status()
                content = res.json()["choices"][0]["message"]["content"].strip()
                return content
            except Exception as e:
                last_exc = e
                await asyncio.sleep((attempt + 1) * 1)
    raise RuntimeError(f"Groq native call failed after 3 retries: {last_exc}") from last_exc


async def call_gemini_native(messages_or_prompt, system_prompt=None, temperature=0.7, max_tokens=4000) -> str:
    """
    Backup native Gemini generation endpoint.
    """
    api_key = settings.gemini_api_key.strip() if settings.gemini_api_key else ""
    if not api_key:
        api_key = settings.groq_api_key.strip() if settings.groq_api_key else ""
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GROQ_API_KEY is not set")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    contents = []
    system_instr = system_prompt

    if isinstance(messages_or_prompt, str):
        contents.append({"role": "user", "parts": [{"text": messages_or_prompt}]})
    elif isinstance(messages_or_prompt, list):
        for msg in messages_or_prompt:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_instr = content
            else:
                gemini_role = "model" if role in ["assistant", "model"] else "user"
                contents.append({"role": gemini_role, "parts": [{"text": content}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }
    }
    if system_instr:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instr}]
        }

    last_exc = None
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            try:
                res = await client.post(url, json=payload)
                if res.status_code == 429:
                    await asyncio.sleep((attempt + 1) * 3)
                    continue
                res.raise_for_status()
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return text
            except Exception as e:
                last_exc = e
                await asyncio.sleep((attempt + 1) * 1)
    raise RuntimeError(f"Gemini call failed after 3 retries: {last_exc}") from last_exc


async def call_groq(prompt: str, system_prompt: str = None, temperature: float = 0.5, max_tokens: int = 3000, max_retries: int = 3):
    """
    Unified JSON generator helper. First tries Groq API, and falls back to Gemini.
    """
    content = ""
    # Try Groq first if key is available
    if settings.groq_api_key.strip():
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            content = await call_groq_native(messages, temperature, max_tokens, json_mode=True)
        except Exception as e:
            print(f"Groq JSON call failed ({e}). Falling back to Gemini.")
            content = ""

    # Fallback to Gemini if Groq failed or key is not set
    if not content:
        content = await call_gemini_native(prompt, system_prompt, temperature, max_tokens)
    
    # Strip markdown block formatting if present anywhere in content
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if m:
        content = m.group(1).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Fallback: find outer braces
        m2 = re.search(r"(\{[\s\S]*\})", content)
        if m2:
            raw_json = m2.group(1)
            # Clean trailing commas before closing braces/brackets
            cleaned = re.sub(r",\s*([\}\]])", r"\1", raw_json)
            return json.loads(cleaned)
        raise

