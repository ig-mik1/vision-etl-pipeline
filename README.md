# 🎯 Vision-ETL Pipeline: Live Esports Telemetry

An autonomous, Edge-AI telemetry pipeline that extracts real-time match data from live YouTube/Twitch esports broadcasts using Computer Vision, bypassing rate-limited official APIs.

## 🚀 Architecture overview
1. **Edge Ingestion:** `yt-dlp` pipes live 1080p video directly into OpenCV memory.
2. **YOLO Gatekeeper:** Filters dead frames, ensuring the expensive OCR engine only runs when the killfeed is active on-screen (saving 90% compute).
3. **Primary Extraction:** EasyOCR runs locally to extract raw text with confidence scores.
4. **Agentic Fallback:** If OCR confidence drops below 70%, the system converts the cropped frame to Base64 and autonomously escalates to **Groq's Llama Vision** model for correction.
5. **Master Data Management:** `difflib` normalizes AI hallucinations, snapping messy OCR text directly to the active match roster.
6. **Live Dashboard:** A Flask + Tailwind CSS web app that polls a normalized PostgreSQL (Supabase) database in real-time.
7. **Voice Narrator Agent:** An integrated Web Speech API that answers natural language questions about live match data using Llama 3.1 8B.

## 🛠️ Tech Stack
* **Backend:** Python, Flask
* **Computer Vision:** OpenCV, Ultralytics (YOLO), EasyOCR
* **AI/LLMs:** Groq API (Llama Vision & Llama 3.1 8B)
* **Database:** Supabase (PostgreSQL)
* **Frontend:** HTML/JS, Tailwind CSS, AJAX Polling

## ⚙️ How to Run Locally
1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Rename `.env.example` to `.env` and add your Supabase and Groq keys.
4. Start the server: `python app.py`
5. Open `http://localhost:5000`, paste a YouTube VOD link, and click **Initialize AI**.