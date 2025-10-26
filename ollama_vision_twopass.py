import os
import json
import base64
import requests
import time
from PIL import Image as PILImage

# Try to use ollama library for better performance
try:
    import ollama
    HAS_OLLAMA_LIB = True
except ImportError:
    HAS_OLLAMA_LIB = False

def get_ollama_settings():
    ollama_url = "http://127.0.0.1:11434"
    ollama_model = "qwen2.5vl:3b"
    keep_alive = "10m"
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            cfg = json.load(f)
            ollama_url = cfg.get("ollama_url", ollama_url)
            ollama_model = cfg.get("ollama_default_model", ollama_model)
            keep_alive = cfg.get("keep_alive", keep_alive)
    return ollama_url, ollama_model, keep_alive

class OllamaSession:
    def __init__(self, model=None):
        self.url, default_model, self.keep_alive = get_ollama_settings()
        self.model = model or default_model
        self.messages = []
        self.session = requests.Session() if not HAS_OLLAMA_LIB else None

    def ask(self, content, images=None, callback=None):
        msg = {"role": "user", "content": content}
        if images:
            msg["images"] = images
        self.messages.append(msg)
        
        if HAS_OLLAMA_LIB:
            # Use ollama library with custom host
            client = ollama.Client(host=self.url)
            response = client.chat(
                model=self.model,
                messages=self.messages,
                stream=False,
                keep_alive=self.keep_alive
            )
            reply = response['message']['content']
        else:
            # Fallback to requests
            payload = {
                "model": self.model,
                "messages": self.messages,
                "stream": False,
                "keep_alive": self.keep_alive
            }
            resp = self.session.post(
                f"{self.url}/api/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=(30, 300)
            )
            resp.raise_for_status()
            reply = resp.json()["message"]["content"]
        
        # Add assistant's reply to context
        self.messages.append({"role": "assistant", "content": reply})
        return reply
    
    def close(self):
        if self.session:
            self.session.close()

def query_ollama_vision_twopass(image_path, progress_callback=None):
    """Two-pass approach: first extract text, then describe visual elements"""
    
    session = OllamaSession()
    
    # Get image dimensions
    from PIL import Image as PILImage
    with PILImage.open(image_path) as img:
        img_width, img_height = img.size
    
    # Use direct path if ollama library available, otherwise base64
    if HAS_OLLAMA_LIB:
        image_input = image_path
        print(f">>> Using model: {session.model} (ollama library)")
        print(f">>> Image dimensions: {img_width}x{img_height}")
    else:
        with open(image_path, "rb") as f:
            raw = f.read()
        image_input = base64.b64encode(raw).decode()
        print(f">>> Using model: {session.model} (requests)")
        print(f">>> Image dimensions: {img_width}x{img_height}")
        print(f">>> Image size: {len(raw)} bytes, base64 size: {len(image_input)}")
    
    try:
        start_time = time.time()
        
        # First pass: Extract all text
        print("\n>>> First pass: Extracting text...")
        if progress_callback:
            progress_callback("Extracting text...")
        
        text_prompt = (
            "If you find text in this image, please read the entire text carefully, neatly formatted. "
            "Don't miss out any words. Don't hallucinate, or dont rely on your memory about the subject in the text. "
            "Stay grounded to the text in the image."
            "By text I mean all text, typed, hand writtend, photographed, painted, drawn and all text variations"
            "Don't provide any explanations of what you see,only provide the extracted the text. "
            "Your job is to extract text just similar to a good OCR app"
        )
        
        first_start = time.time()
        first_pass_response = session.ask(text_prompt, images=[image_input])
        first_duration = time.time() - first_start
        print(f"\n\n{'='*80}")
        print(f"[DEBUG] FIRST PASS - {first_duration:.2f}s - {len(first_pass_response)} chars")
        print(f"{'='*80}")
        print(first_pass_response)
        print(f"{'='*80}\n\n")
        
        # Second pass: Describe visual layout
        print(">>> Second pass: Describing visual elements...")
        if progress_callback:
            progress_callback("Describing visual elements...")
        
        visual_prompt = (
            "Now focus only on the visual aspects - describe the layout, colors, objects, and spatial relationships. "
            "Do NOT repeat any text content from your previous response."
        )
        
        second_start = time.time()
        second_pass_response = session.ask(visual_prompt)
        second_duration = time.time() - second_start
        print(f"\n\n{'#'*80}")
        print(f"[DEBUG] SECOND PASS - {second_duration:.2f}s - {len(second_pass_response)} chars")
        print(f"{'#'*80}")
        print(second_pass_response)
        print(f"{'#'*80}\n\n")
        
        # Process responses
        text_content = first_pass_response  # Direct use for now
        visual_description = second_pass_response  # Direct use for now
        print(f"\n\n{'-'*80}")
        print(f"[DEBUG] PROCESSED RESULTS")
        print(f"{'-'*80}")
        print(f"Text ({len(text_content)} chars): {text_content[:150]}...")
        print(f"Visual ({len(visual_description)} chars): {visual_description[:150]}...")
        print(f"{'-'*80}\n\n")
        
        total_duration = time.time() - start_time
        print(f"{'*'*80}")
        print(f"[DEBUG] TOTAL TIME: {total_duration:.2f}s (First: {first_duration:.2f}s, Second: {second_duration:.2f}s)")
        print(f"{'*'*80}\n\n")
        
        return {
            "text": text_content,
            "visual": visual_description,
            "combined": f"TEXT CONTENT:\n{text_content}\n\nVISUAL DESCRIPTION:\n{visual_description}"
        }
    finally:
        session.close()