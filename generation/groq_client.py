import base64
import requests
from openai import OpenAI
from config import Config

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = Config.NVIDIA_API_KEY_CHAT
)

CHAT_MODEL = "meta/llama-3.3-70b-instruct"
VISION_MODEL = "meta/llama-3.2-11b-vision-instruct"


def chat(prompt: str, system: str = "You are a helpful assistant.", factual: bool = False) -> str:
    """Send a text prompt to Llama 3.3 70B and return the response."""
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0 if factual else 0.2,
        top_p=0.7,
        max_tokens=1024,
        stream=False
    )
    return response.choices[0].message.content


def describe_image(image_bytes: bytes, prompt: str = "Describe this image in detail.") -> str:
    """Send an image to Llama 3.2 Vision 11B and return a description."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    
    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {Config.NVIDIA_API_KEY_VISION}",
        "Accept": "application/json"
    }
    
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]
            }
        ],
        "max_tokens": 512,
        "temperature": 1.00,
        "top_p": 1.00,
        "stream": False
    }
    
    response = requests.post(invoke_url, headers=headers, json=payload)
    response_data = response.json()
    try:
        return response_data["choices"][0]["message"]["content"]
    except KeyError:
        return ""
