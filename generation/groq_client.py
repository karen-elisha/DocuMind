import base64
from groq import Groq
from config import Config
from typing import Generator

client = Groq(api_key=Config.GROQ_API_KEY)

CHAT_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def chat(prompt: str, system: str = "You are a helpful assistant.", factual: bool = False) -> str:
    """Send a text prompt to Llama 3.3 70B via Groq and return the response."""
    try:
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0 if factual else 0.2,
            max_tokens=1024,
        )
        return response.choices[0].message.content
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate_limit" in msg.lower():
            import re as _re
            wait = _re.search(r'try again in ([\w.]+)', msg)
            wait_str = f" Please try again in {wait.group(1)}" if wait else ""
            return f"⚠️ Groq rate limit reached (free tier: 100K tokens/day).{wait_str}"
        raise


def chat_stream(prompt: str, system: str = "You are a helpful assistant.", factual: bool = False) -> Generator[str, None, None]:
    """Stream tokens from Llama 3.3 70B via Groq."""
    try:
        stream = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0 if factual else 0.2,
            max_tokens=1024,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as e:
        yield f"\n\n[Error: {str(e)}]"


def describe_image(image_bytes: bytes, prompt: str = "Describe this image in detail.") -> str:
    """Send an image to Llama 4 Scout Vision via Groq and return a description."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
        max_tokens=512,
    )
    try:
        return response.choices[0].message.content
    except Exception:
        return ""
