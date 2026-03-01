import cv2
import time
import uuid
import sys
import difflib
from hybrid_scraper import extract_hybrid_killfeed, yolo_model
from db_loader import insert_kills
import yt_dlp

# 🔥 THE DYNAMIC SELF-LEARNING ROSTER 🔥
# We disable self-learning and force the AI to anchor to reality.
MATCH_ROSTER = [
    "FNC Boaster", "FNC Chronicle", "FNC Alfajer", "FNC Derke", "FNC Crashies",
    "NRG mada", "NRG s0m", "NRG Ethan", "NRG brawk", "NRG skuba"
]
DYNAMIC_ROSTER = MATCH_ROSTER.copy()

def fuzzy_match_player(ocr_name):
    """Normalizes text before fuzzy matching to guarantee a hit."""
    if not ocr_name or str(ocr_name).strip() == "Unknown": 
        return "Unknown"
    
    # 1. Normalize the messy AI input (lowercase, strip extra spaces)
    messy_input = str(ocr_name).lower().strip()
    
    # 2. Normalize the Master Roster for a fair comparison
    normalized_roster = [player.lower() for player in MATCH_ROSTER]
    
    # 3. Find the match (cutoff 0.3 allows for heavy OCR typos)
    matches = difflib.get_close_matches(messy_input, normalized_roster, n=1, cutoff=0.3)
    
    if matches:
        # 4. Map it back to the original, correctly capitalized proper noun!
        match_index = normalized_roster.index(matches[0])
        return MATCH_ROSTER[match_index]
        
    return ocr_name

def start_stream_watcher(source_url):
    print(f"📡 Received Target URL: {source_url}")
    
    # 🔥 RESOLVE YOUTUBE LINKS DIRECTLY TO OPENCV 🔥
    if "youtube.com" in source_url or "youtu.be" in source_url:
        print("🔗 Resolving YouTube video stream...")
        try:
             # 🔥 FORCE 1080p VIDEO TRACK 🔥
            ydl_opts = {
                'format': 'bestvideo[height<=1080][ext=mp4]/bestvideo[ext=mp4]/best',
                'noplaylist': True,
                'quiet': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(source_url, download=False)
                source_url = info['url']
            print("✅ YouTube Stream resolved. Piping into OpenCV...")
        except Exception as e:
            print(f"❌ Failed to resolve YouTube stream: {e}")
            return
            
    cap = cv2.VideoCapture(source_url)
    CURRENT_SESSION_ID = str(uuid.uuid4())
    print(f"🔑 Match Session ID: {CURRENT_SESSION_ID}")
    
    if not cap.isOpened():
        print("❌ ERROR: Could not open video stream.")
        return

    fps = int(cap.get(cv2.CAP_PROP_FPS))
    if fps == 0: fps = 30 
    
    frames_to_skip = fps 
    recent_kills_memory = set()
    previous_weapon_count = 0
    frame_count = 0
    
    print("🟢 Engine LIVE. Watching stream...")
    
    while True:
        ret, frame = cap.read()
        if not ret: break
            
        frame_count += 1
        if frame_count % frames_to_skip != 0: continue
            
        h, w, _ = frame.shape
        cropped_frame = frame[0:int(h*0.25), int(w*0.75):w]
        
        results = yolo_model(cropped_frame, conf=0.5, verbose=False)
        current_weapon_count = len(results[0].boxes)
        
        if current_weapon_count > 0 and current_weapon_count != previous_weapon_count:
            print(f"\n⚡ [00:{frame_count // fps:02d}] STATE CHANGE DETECTED. Extracting...")
            
            cv2.imwrite("live_temp_frame.jpg", frame)
            extracted_events = extract_hybrid_killfeed("live_temp_frame.jpg")
            
            if extracted_events:
                new_kills_to_insert = []
                for kill in extracted_events:
                    raw_killer = kill.get('killer_name', 'unknown')
                    raw_victim = kill.get('victim_name', 'unknown')
                    
                    if raw_killer not in DYNAMIC_ROSTER and len(raw_killer) > 3:
                        DYNAMIC_ROSTER.append(raw_killer)
                    if raw_victim not in DYNAMIC_ROSTER and len(raw_victim) > 3:
                        DYNAMIC_ROSTER.append(raw_victim)
                    
                    clean_killer = fuzzy_match_player(raw_killer)
                    clean_victim = fuzzy_match_player(raw_victim)
                    weapon = kill.get('weapon_used', 'unknown')
                    
                    kill_signature = f"{clean_killer}-{clean_victim}-{weapon}"
                    
                    if kill_signature not in recent_kills_memory:
                        recent_kills_memory.add(kill_signature)
                        kill['killer_name'] = clean_killer
                        kill['victim_name'] = clean_victim
                        kill['session_id'] = CURRENT_SESSION_ID 
                        new_kills_to_insert.append(kill)
                
                if new_kills_to_insert:
                    insert_kills(new_kills_to_insert)
            
            time.sleep(1)
        
        previous_weapon_count = current_weapon_count

if __name__ == "__main__":
    # Allow URL to be passed via command line
    target = sys.argv[1] if len(sys.argv) > 1 else "test_stream.mp4" 
    start_stream_watcher(target)