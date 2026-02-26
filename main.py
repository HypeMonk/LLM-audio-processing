import os
import re
import json
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from dotenv import load_dotenv

# Load variables from your .env file
load_dotenv()

app = FastAPI()

# Release the "crocs"! (Allowing all Cross-Origin requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (POST, GET, etc.)
    allow_headers=["*"], # Allows all headers
)

# 1. Data Models
class AskRequest(BaseModel):
    video_url: str
    topic: str

class AskResponse(BaseModel):
    timestamp: str
    video_url: str
    topic: str

# Helper Function: Extract the YouTube Video ID from the URL
def extract_video_id(url: str) -> str:
    # Handles both 'youtube.com/watch?v=ID' and 'youtu.be/ID'
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    return match.group(1)

# Helper Function: Convert seconds to HH:MM:SS
def seconds_to_hhmmss(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

@app.post("/ask", response_model=AskResponse)
def ask_video_topic(request: AskRequest):
    try:
        # Step 1: Get the Video ID
        video_id = extract_video_id(request.video_url)
        
        from youtube_transcript_api import TranscriptsDisabled, NoTranscriptFound

        # Step 2: Grab the transcript (the hack!)
        # Step 2: Grab the transcript (the hack!)
        try:
            # The new way: instantiate the API object and call fetch()
            fetched = YouTubeTranscriptApi().fetch(video_id)
            transcript_list = fetched.to_raw_data()
            
        except TranscriptsDisabled:
            raise HTTPException(status_code=400, detail="The creator disabled subtitles for this video. The text-hack won't work here!")
        except NoTranscriptFound:
            raise HTTPException(status_code=400, detail="No transcript found for this video.")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Transcript error: {str(e)}")

        # Step 3: Format the transcript into a readable text chunk with HH:MM:SS timestamps
        formatted_transcript = ""
        for item in transcript_list:
            time_str = seconds_to_hhmmss(item['start'])
            formatted_transcript += f"[{time_str}] {item['text']}\n"
            
        # Step 4: Prepare the request to your custom aipipe.org API
        ai_token = os.getenv("AI_API_TOKEN")
        chat_url = os.getenv("CHAT_URL")
        
        if not ai_token or not chat_url:
            raise HTTPException(status_code=500, detail="API credentials missing in .env file")

        # THE FIX: Better prompt, and we pass the ENTIRE transcript!
        user_prompt = f"""
        You are an API that ONLY outputs raw, valid JSON. Do not use markdown blocks like ```json.
        
        Here is the transcript of a video. Find the exact moment the speaker starts discussing the concept of: "{request.topic}".
        They might not use these exact words, so look for the meaning/context!
        
        Transcript:
        {formatted_transcript} 
        
        Return ONLY a JSON object with this exact structure:
        {{
            "timestamp": "HH:MM:SS"
        }}
        """
        
        headers = {
            "Authorization": f"Bearer {ai_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1 # Keep it focused!
        }
        
        # Step 5: Send it to aipipe.org
        response = requests.post(chat_url, headers=headers, json=payload)
        
        # IF IT FAILS: This will print the EXACT reason aipipe rejected it!
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"AIPipe Error: {response.text}")
        
        # Step 6: Parse the response
        ai_data = response.json()
        raw_content = ai_data["choices"][0]["message"]["content"]
        
        # Clean up markdown if the AI sneaks it in
        raw_content = raw_content.strip().strip("```json").strip("```").strip()
        
        try:
            # Parse what the AI gave us
            ai_dict = json.loads(raw_content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {raw_content}")
        
        # THE NEW FIX: Catch the explicit 'null' / 'None'
        ai_timestamp = ai_dict.get("timestamp")
        
        # If the AI returned null, None, or an empty string, we catch it here
        if not ai_timestamp:
            ai_timestamp = "00:00:00"
            
        result_dict = {
            "timestamp": str(ai_timestamp), # Forcing it to be a string, guaranteed!
            "video_url": request.video_url,
            "topic": request.topic
        }
        
        return result_dict

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))