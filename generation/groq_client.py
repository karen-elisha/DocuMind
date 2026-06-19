import base64
from groq import Groq
from config import Config

client = Groq(api_key=Config.GROQ_API_KEY)

CHAT_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "llama-3.2-11b-vision-preview"


def chat(prompt: str, system: str = "You are a helpful assistant.") -> str:
    """Send a text prompt to Llama 3.3 70B and return the response."""
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def describe_image(image_bytes: bytes, prompt: str = "Describe this image in detail.") -> str:
    """Send an image to Llama 3.2 Vision 11B and return a description."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return response.choices[0].message.content
