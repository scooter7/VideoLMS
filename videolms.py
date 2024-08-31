import streamlit as st
import openai
import yt_dlp
import os

# Set OpenAI API key
openai.api_key = st.secrets["openai"]["api_key"]

# Function to download video/audio using yt-dlp
def download_audio_from_youtube(youtube_url):
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
        try:
            ydl.download([youtube_url])
            return 'temp_audio.mp3'
        except Exception as e:
            st.error(f"Failed to download audio: {e}")
            return None

# Function to transcribe audio using Whisper
def transcribe_with_whisper(audio_file_path):
    try:
        with open(audio_file_path, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
        return transcript['text']
    except Exception as e:
        st.error(f"Failed to transcribe audio using Whisper: {e}")
        return None

# Streamlit UI
st.title("YouTube Video Transcription with Whisper")

youtube_url = st.text_input("Enter YouTube Video URL")

if st.button("Generate Transcript"):
    if youtube_url:
        st.info("Downloading audio from YouTube...")
        audio_file_path = download_audio_from_youtube(youtube_url)
        
        if audio_file_path:
            st.success("Audio downloaded successfully!")
            st.info("Transcribing audio with Whisper...")
            transcript = transcribe_with_whisper(audio_file_path)
            
            if transcript:
                st.success("Transcript generated successfully!")
                st.text_area("Transcript:", transcript, height=300)
                
                # Optionally, you can add functionality to save the transcript to GitHub
                
            # Clean up the temporary audio file
            os.remove(audio_file_path)
        else:
            st.error("Failed to download audio.")
    else:
        st.warning("Please enter a YouTube URL.")
