import base64
import requests
import json
import os
import re
import ast
from PIL import Image
from ollama_vision import get_ollama_settings

# Optional backends (install via pip if you want extra leniency)
try:
    import json5       # pip install json5
except ImportError:
    json5 = None

try:
    import demjson3    # pip install demjson3
except ImportError:
    demjson3 = None


def smart_parse_json(raw: str):
    """Lenient JSON parser: json5 → demjson3 → ast.literal_eval → json.loads."""
    print("[DEBUG] smart_parse_json: starting cleanup")
    s = raw.replace("\r\n", "\n")
    s = "".join(ch for ch in s if ch in ("\n", "\t") or ord(ch) >= 32)
    s = re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"', lambda m: '"' + m.group(1).replace('"', r'\"') + '"', s)
    s = re.sub(r",\s*([}\]])", r"\1", s)

    if json5:
        try: return json5.loads(s)
        except Exception as e: print(f"[DEBUG] json5 failed: {e}")
    if demjson3:
        try: return demjson3.decode(s)
        except Exception as e: print(f"[DEBUG] demjson3 failed: {e}")
    try: return ast.literal_eval(s)
    except Exception as e: print(f"[DEBUG] ast.literal_eval failed: {e}")
    return json.loads(s)


def extract_json_substring(text: str) -> str:
    """Extract the first complete JSON object/array via brace matching."""
    print("[DEBUG] extract_json_substring: locating JSON start")
    start = next((i for i,ch in enumerate(text) if ch in "{["), None)
    if start is None:
        raise ValueError("No JSON object or array found")
    opening = text[start]
    closing = {"{":"}","[":"]"}[opening]
    depth = 0
    for i,ch in enumerate(text[start:], start):
        if ch == opening: depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                snippet = text[start:i+1]
                print(f"[DEBUG] extracted JSON substring ({len(snippet)} chars)")
                return snippet
    raise ValueError("Unmatched JSON braces/brackets")


def get_app_settings():
    """Load or create app_settings.json controlling image resizing."""
    path = os.path.join(os.path.dirname(__file__), "app_settings.json")
    default = {"resize_large_images": True}
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except:
            pass
    json.dump(default, open(path,"w"))
    return default


def resize_image_if_needed(image_path: str) -> str:
    """Resize image to max 1200px side if enabled in settings."""
    settings = get_app_settings()
    if not settings.get("resize_large_images", True):
        return image_path
    with Image.open(image_path) as img:
        w,h = img.size
        if w<=1200 and h<=1200:
            return image_path
        if w>h:
            nw,nh = 1200, int(h*1200/w)
        else:
            nh,nw = 1200, int(w*1200/h)
        resized = img.resize((nw,nh), Image.Resampling.LANCZOS)
        import tempfile
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        resized.save(tf.name); tf.close()
        return tf.name


def get_structured_analysis(image_path: str) -> str:
    """Step 1: Send image, receive streaming text analysis."""
    url, model = get_ollama_settings()
    proc = resize_image_if_needed(image_path)
    raw = open(proc,"rb").read()
    img_b64 = base64.b64encode(raw).decode()
    payload = {
        "model": model,
        "messages": [{
            "role":"user",
            "content":(
                "EXTRACT ALL TEXT from this screenshot. Read every single word, "
                "filename, label, and code blocks verbatim. Do not miss anything. "
                "Then describe the visual layout."
            ),
            "images":[img_b64]
        }],
        "stream":True, "keep_alive":"15m"
    }
    resp = requests.post(f"{url}/api/chat", json=payload,
                         headers={"Content-Type":"application/json"},
                         timeout=(60,600), stream=True)
    resp.raise_for_status()
    full = ""
    for line in resp.iter_lines():
        if not line: continue
        try:
            chunk = json.loads(line.decode())
            if "message" in chunk and "content" in chunk["message"]:
                full += chunk["message"]["content"]
                print(".", end="", flush=True)
        except json.JSONDecodeError:
            continue
    if proc!=image_path:
        try: os.unlink(proc)
        except: pass
    print("\n[DEBUG] Structured analysis complete")
    return full


def reformat_to_json(structured: str) -> str:
    """Step 2: Instruct model to produce JSON with text+visual fields."""
    url, model = get_ollama_settings()
    prompt = (
        "Extract ALL text content from this analysis and put it in JSON format. "
        "Format as:\n"
        '{"text": "...", "visual": "..."}\n\n'
        "Keep any markdown code fences (```…```) intact in the text field. "
        "Also provide a concise visual description in the \"visual\" field.\n\n"
        + structured
    )
    payload = {"model":model, "messages":[{"role":"user","content":prompt}],
               "stream":True,"keep_alive":"15m"}
    resp = requests.post(f"{url}/api/chat", json=payload,
                         headers={"Content-Type":"application/json"},
                         timeout=(60,600), stream=True)
    resp.raise_for_status()
    js=""
    for line in resp.iter_lines():
        if not line: continue
        try:
            chunk = json.loads(line.decode())
            if "message" in chunk and "content" in chunk["message"]:
                js += chunk["message"]["content"]
                print(".", end="", flush=True)
        except json.JSONDecodeError:
            continue
    print("\n[DEBUG] JSON reformat complete")
    return js


def extract_text_from_image(image_path: str):
    """
    Full pipeline: analysis → JSON → parse → extract.
    Returns (text, visual).
    """
    print("=== STEP 1 ===")
    structured = get_structured_analysis(image_path)
    print(f"\nRAW STRUCTURED:\n{structured}\n")

    print("=== STEP 2 ===")
    raw_json = reformat_to_json(structured)
    print(f"\nRAW JSON:\n{raw_json}\n")

    # Parse JSON blob
    json_str = extract_json_substring(raw_json)
    try:
        data = smart_parse_json(json_str)
    except Exception as e:
        print(f"[DEBUG] parser failed: {e}")
        data = {}

    text   = data.get("text")   if isinstance(data,dict) else None
    visual = data.get("visual","") if isinstance(data,dict) else ""

    # Fallback raw text
    if not text:
        m = re.search(r'"text"\s*:\s*"([\s\S]*?)"\s*(?:,|\})', json_str, re.DOTALL)
        if m: text = m.group(1).replace(r'\"','"')
    if not text:
        text = structured

    # Filename-based visual fallback
    if not visual.strip():
        files = re.findall(r'[- ]\s*([\w\-.]+\.(?:py|json|txt|png|ipynb|cfg))', structured)
        if files:
            visual = "Screenshot shows files: " + ", ".join(files[:8]) \
                     + (f", and {len(files)-8} more." if len(files)>8 else ".")
            print(f"[DEBUG] Built fallback visual from {len(files)} entries")

    print("[DEBUG] Extraction complete")
    return text, visual
