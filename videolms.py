import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import openai
import yt_dlp

# Set OpenAI API key
openai.api_key = st.secrets["openai"]["api_key"]

# Function to fetch transcript using youtube_transcript_api
def fetch_transcript(video_id: str):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([entry['text'] for entry in transcript])
        return transcript_text
    except TranscriptsDisabled:
        st.error("Transcripts are disabled for this video.")
        return None
    except NoTranscriptFound:
        st.error("No transcript found for this video.")
        return None
    except Exception as e:
        st.error(f"Failed to fetch transcript: {e}")
        return None

# Function to download video and transcribe using Whisper
def transcribe_with_whisper(video_url: str):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'temp_audio.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        transcript = None
        with open("temp_audio.mp3", "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
        
        return transcript['text'] if transcript else None
    except Exception as e:
        st.error(f"Failed to transcribe video using Whisper: {e}")
        return None

# Streamlit UI
st.title("YouTube Video Transcript Generator")

video_url = st.text_input("Enter YouTube video URL:")
if st.button("Generate Transcript"):
    if video_url:
        video_id = video_url.split("v=")[-1]

        # Try fetching the transcript using YouTubeTranscriptApi first
        transcript = fetch_transcript(video_id)
        
        if not transcript:
            # If the transcript is not available, try using Whisper
            st.info("Fetching transcript using Whisper...")
            transcript = transcribe_with_whisper(video_url)
        
        if transcript:
            st.success("Transcript generated successfully!")
            st.text_area("Transcript:", transcript, height=300)
        else:
            st.error("Failed to fetch or generate a transcript.")
    else:
        st.error("Please enter a valid YouTube video URL.")
