import os
import subprocess
import sys
from flask import Flask, render_template, jsonify, request
from supabase import create_client, Client
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = Flask(__name__)

# Keep a reference to the background process
watcher_process = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
def start_pipeline():
    global watcher_process
    stream_url = request.json.get("url", "test_stream.mp4")
    
    # If a pipeline is already running, kill it before starting a new one
    if watcher_process:
        watcher_process.terminate()
        
    print(f"🚀 UI COMMAND RECEIVED: Starting Pipeline for {stream_url}")
    
    # Launch the watcher in the background with the URL as an argument
    watcher_process = subprocess.Popen([sys.executable, "live_watcher.py", stream_url])
    
    return jsonify({"status": "success", "message": "AI Pipeline Initialized."})

@app.route('/api/kills')
def get_kills():
    try:
        response = supabase.table("kill_feed").select("*").execute()
        all_data = response.data
        if not all_data: return jsonify({"status": "success", "total_kills": 0, "headshots": 0, "hs_percentage": 0, "kills": [], "top_fraggers": []})
            
        all_data = all_data[::-1]
        
        latest_session = None
        for row in all_data:
            if row.get("session_id"):
                latest_session = row["session_id"]
                break
                
        match_data = [row for row in all_data if row.get("session_id") == latest_session] if latest_session else all_data

        total_kills = len(match_data)
        headshots = sum(1 for kill in match_data if kill.get('is_headshot'))
        hs_percentage = round((headshots / total_kills) * 100, 1) if total_kills > 0 else 0
        
        player_kills = {}
        for kill in match_data:
            killer = kill.get('killer_name', 'Unknown')
            if killer != "Unknown":
                player_kills[killer] = player_kills.get(killer, 0) + 1
        
        top_fraggers = [{"name": k, "kills": v} for k, v in sorted(player_kills.items(), key=lambda item: item[1], reverse=True)]

        return jsonify({"status": "success", "total_kills": total_kills, "headshots": headshots, "hs_percentage": hs_percentage, "kills": match_data, "top_fraggers": top_fraggers})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ask', methods=['POST'])
def ask_agent():
    user_query = request.json.get("query", "Summarize the current match state.")
    
    try:
        # 1. Grab data safely
        response = supabase.table("kill_feed").select("*").execute()
        all_data = response.data
        
        # 2. Filter for only the current live session
        latest_session = None
        for row in reversed(all_data):
            if row.get("session_id"):
                latest_session = row["session_id"]
                break
                
        match_data = [row for row in all_data if row.get("session_id") == latest_session] if latest_session else all_data
        
        # 3. CONTEXT WINDOW PROTECTION: Only send the 30 most recent kills
        recent_kills = match_data[-30:] 
        
        # 4. The Engineered Prompt
        prompt = f"""
        You are an elite Valorant esports Data Analyst and Shoutcaster.
        Here is the live telemetry JSON for the current match: {recent_kills}
        
        The user asks: "{user_query}"
        
        Answer the user's question directly using ONLY the data provided. Use exactly 1 or 2 short, punchy sentences. 
        DO NOT use markdown, asterisks, or bolding, as your exact text will be read aloud by a Text-to-Speech engine.
        """
        
        # 5. Call the active, blazing-fast Groq model
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant", # The updated, active Groq model!
            temperature=0.5,
            max_tokens=150
        )
        answer = chat_completion.choices[0].message.content.strip()
        return jsonify({"status": "success", "answer": answer})
        
    except Exception as e:
        print(f"❌ Narrator Agent Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
