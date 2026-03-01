import os
import json
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

# Load API keys from .env
load_dotenv()

client = genai.Client()

def extract_killfeed_data(image_path: str):
    print(f"👀 Loading and pre-processing {image_path}...")
    
    try:
        img = Image.open(image_path)
        
        # 🛠️ DATA ENGINEERING FIX: Crop to the top-right corner (Killfeed Area)
        # This assumes a standard 16:9 resolution (like 1920x1080)
        width, height = img.size
        left = int(width * 0.75)  # Start 75% across the screen
        top = 0                   # Start at the very top
        right = width             # Go all the way to the right edge
        bottom = int(height * 0.25) # Go 25% down the screen
        
        # Crop the image so the AI only sees the killfeed
        cropped_img = img.crop((left, top, right, bottom))
        
        # Optional: Save the crop just so you can see what the AI is looking at
        cropped_img.save("debug_cropped_killfeed.png")
        print("✂️ Image cropped successfully. Sending to Gemini...")

    except FileNotFoundError:
        print(f"❌ ERROR: Could not find '{image_path}'.")
        return None
    
    # 🛠️ PROMPT FIX: Give it a strict list of allowed weapons
    prompt = """
    You are an expert Valorant data extractor. Look at this cropped image of the top-right killfeed.
    Extract the most recent kill event. 
    
    CRITICAL INSTRUCTION FOR WEAPON: 
    The weapon is an icon. You MUST identify the weapon strictly from this list:
    [Classic, Shorty, Frenzy, Ghost, Sheriff, Stinger, Spectre, Bucky, Judge, Bulldog, Guardian, Phantom, Vandal, Marshal, Outlaw, Operator, Ares, Odin, Melee, Ability]
    
    Schema required:
    {
        "killer_name": "string",
        "victim_name": "string",
        "weapon_used": "string",
        "is_headshot": boolean
    }
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[cropped_img, prompt], # Pass the CROPPED image, not the full one
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0 # Zero creativity, purely factual
            )
        )
        
        data = json.loads(response.text)
        
        print("✅ Data Extracted Successfully:")
        print(json.dumps(data, indent=2))
            
        return data

    except Exception as e:
        print(f"❌ Failed to process image or parse JSON: {e}")
        return None

if __name__ == "__main__":
    # Change the file name here to match whatever your image is called!
    extract_killfeed_data("test_frame.png")