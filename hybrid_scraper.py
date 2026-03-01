import os
import json
import cv2
import base64
import numpy as np
import easyocr
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv
from ultralytics import YOLO
from groq import Groq

load_dotenv()
PROJECT_ROOT = Path(__file__).resolve().parent
HEADSHOT_MATCH_THRESHOLD = float(os.getenv("HEADSHOT_MATCH_THRESHOLD", "0.50"))

# Initialize the Groq SDK (The Vision Agent)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute(): return path
    return PROJECT_ROOT / path

def ensure_gray(np_img: np.ndarray) -> np.ndarray:
    if np_img.ndim == 2: return np_img
    if np_img.ndim == 3 and np_img.shape[2] == 3: return cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
    if np_img.ndim == 3 and np_img.shape[2] == 4: return cv2.cvtColor(np_img, cv2.COLOR_RGBA2GRAY)
    return np_img

def enhance_for_ocr(roi_image):
    """Upscales and pads the image for better local OCR reading."""
    if roi_image.size == 0: return roi_image
    upscaled = cv2.resize(roi_image, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    padded = cv2.copyMakeBorder(upscaled, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=[0, 0, 0])
    return padded

print("🧠 Loading Autonomous Vision Agent (YOLO + EasyOCR + Llama 4 Scout Fallback)...")
yolo_model = YOLO(str(resolve_path("yolo26.pt")))

reader = easyocr.Reader(['en'], gpu=True)

try:
    template_path = resolve_path("headshot_template.png")
    headshot_template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
    headshot_template = ensure_gray(headshot_template)
except Exception as e:
    print(f"❌ ERROR: Could not load 'headshot_template.png'. {e}")
    exit()

def needs_escalation(text: str, confidence: float) -> bool:
    """The Gatekeeper: Evaluates EasyOCR's confidence score."""
    if not text or len(text) < 2: return True
    if confidence < 0.70: return True # If EasyOCR is less than 70% sure, escalate!
    
    suspicious_chars = ["|", "{", "}", "[", "]", "~", "`"]
    if any(char in text for char in suspicious_chars): return True
    return False

def ask_vision_agent(roi_image_array: np.ndarray, context: str) -> str:
    """Escalates a failed image crop to the Groq Llama 4 Vision Model."""
    _, buffer = cv2.imencode('.jpg', roi_image_array)
    base64_image = base64.b64encode(buffer).decode('utf-8')
    
    prompt = f"""
    You are an OCR corrector for an esports pipeline. Look at this tiny cropped image containing a gamer tag.
    The local OCR engine struggled with it. 
    Return ONLY the exact player name written in the image. Do not add quotes, punctuation, or conversational text.
    Context: It is the {context} name in a killfeed.
    """
    
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            model="meta-llama/llama-4-scout-17b-16e-instruct", # The brand new, active Groq model!
            temperature=0.0,
            max_tokens=20
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"      ⚠️ Groq Agent failed: {e}")
        return "Unknown"

def extract_hybrid_killfeed(image_path: str):
    resolved_image_path = resolve_path(image_path)
    
    try:
        img = Image.open(resolved_image_path)

        # 🔥 THE 5-LINE REPLAY SHIELD 🔥
        full_cv_img = np.array(img)
        h, w = full_cv_img.shape[:2]
        # Slice the bottom-right corner where the Replay text lives
        replay_roi = full_cv_img[int(h*0.8):h, int(w*0.7):w] 
        replay_text = " ".join(reader.readtext(replay_roi, detail=0)).upper()
        if "REPLAY" in replay_text:
            print("   ⏪ REPLAY DETECTED! Skipping frame to prevent double-counting.")
            return None
        
        # 🛠️ DATA ENGINEERING FIX: Crop to the top-right corner (Killfeed Area)
        left, top, right, bottom = int(w * 0.75), 0, w, int(h * 0.25)
        cropped_img = img.crop((left, top, right, bottom))
        open_cv_image = np.array(cropped_img)
        gray_image = ensure_gray(open_cv_image)
    except FileNotFoundError:
        print(f"❌ ERROR: Could not find '{resolved_image_path}'.")
        return None

    yolo_results = yolo_model(cropped_img, conf=0.5, verbose=False)
    boxes = yolo_results[0].boxes
    
    final_events = []
    if len(boxes) > 0:
        for i in range(len(boxes)):
            x1, y1, x2, y2 = map(int, boxes.xyxy[i].tolist())
            class_id = int(boxes.cls[i].item())
            weapon_name = yolo_model.names[class_id]
            
# --- 🎯 MULTI-SCALE HEADSHOT MATCHER ---
            # Create the padded slice to search inside
            y1_pad, y2_pad = max(0, int(y1) - 10), min(gray_image.shape[0], int(y2) + 10)
            row_slice = gray_image[y1_pad:y2_pad, :]
            
            is_headshot = False
            
            # Only proceed if the slice is large enough
            if row_slice.shape[0] > 10 and row_slice.shape[1] > 10:
                # Test 4 different sizes to perfectly counter YouTube resolution drops!
                for scale in [0.6, 0.8, 1.0, 1.2]:
                    target_h = int(headshot_template.shape[0] * scale)
                    target_w = int(headshot_template.shape[1] * scale)
                    
                    # Ensure the scaled template physically fits inside our video slice
                    if 0 < target_h < row_slice.shape[0] and 0 < target_w < row_slice.shape[1]:
                        scaled_template = cv2.resize(headshot_template, (target_w, target_h))
                        res = cv2.matchTemplate(row_slice, scaled_template, cv2.TM_CCOEFF_NORMED)
                        
                        # 🔥 The 0.55 Threshold: Forgives YouTube compression artifacts 🔥
                        if float(res.max()) >= 0.55:
                            is_headshot = True
                            break # Found it! Stop searching and move on.
            # ----------------------------------------------
            
            # Geometric Split (Passing color images this time!)
            killer_roi = open_cv_image[y1_pad:y2_pad, :max(0, x1 - 5)]
            victim_roi = open_cv_image[y1_pad:y2_pad, min(open_cv_image.shape[1], x2 + 5):]
            
            enhanced_killer = enhance_for_ocr(killer_roi)
            enhanced_victim = enhance_for_ocr(victim_roi)
            
            # 1. PRIMARY EXTRACTION (Local EasyOCR WITH Confidence Details)
            k_res = reader.readtext(enhanced_killer, detail=1)
            v_res = reader.readtext(enhanced_victim, detail=1)
            
            # Extract text strings and calculate average confidence
            killer_name = " ".join([res[1] for res in k_res]).strip() if k_res else ""
            k_conf = sum([res[2] for res in k_res]) / len(k_res) if k_res else 0.0
            
            victim_name = " ".join([res[1] for res in v_res]).strip() if v_res else ""
            v_conf = sum([res[2] for res in v_res]) / len(v_res) if v_res else 0.0
            
            # 2. THE AUTONOMOUS AGENT ESCALATION
            if needs_escalation(killer_name, k_conf):
                print(f"   🤖 Local OCR low confidence ({k_conf:.2f}) on Killer ('{killer_name}'). Escalating to Groq...")
                killer_name = ask_vision_agent(killer_roi, "killer")
                
            if needs_escalation(victim_name, v_conf):
                print(f"   🤖 Local OCR low confidence ({v_conf:.2f}) on Victim ('{victim_name}'). Escalating to Groq...")
                victim_name = ask_vision_agent(victim_roi, "victim")
            
            final_events.append({
                "y_coord": y1, 
                "killer_name": killer_name,
                "victim_name": victim_name,
                "weapon_used": weapon_name,
                "is_headshot": is_headshot
            })
            
        final_events = sorted(final_events, key=lambda b: b["y_coord"])
        for event in final_events: del event["y_coord"] 
        
        return final_events
    else:
        return None