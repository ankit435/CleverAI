"""Tool 3: AI Image Generator for creating visual artwork, UI mockups, and illustrations."""
import time
import urllib.parse
from typing import Any, Dict, Optional
from langchain_core.tools import tool

def generate_ai_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    seed: Optional[int] = None
) -> Dict[str, Any]:
    """Generate high-definition AI image URL and metadata from prompt."""
    start_time = time.time()
    cleaned_prompt = prompt.strip()
    encoded = urllib.parse.quote_plus(cleaned_prompt)

    seed_param = f"&seed={seed}" if seed is not None else ""
    image_url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true{seed_param}"

    duration_ms = int((time.time() - start_time) * 1000)
    formatted = f"![{cleaned_prompt}]({image_url})\n\n*Generated image for: \"{cleaned_prompt}\"*"

    return {
        "prompt": cleaned_prompt,
        "image_url": image_url,
        "width": width,
        "height": height,
        "execution_time_ms": duration_ms,
        "formatted": formatted
    }

@tool
def generate_image(prompt: str) -> str:
    """
    Generate an AI artwork, illustration, photograph, logo, or UI mockup from a descriptive visual prompt.
    Args:
        prompt: Detailed visual description of what to draw/render.
    """
    data = generate_ai_image(prompt)
    return data["formatted"]
