import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from yt_dlp import YoutubeDL
from github import Github
import re

# Initialize GitHub client
g = Github(st.secrets["github"]["token"])
repo = g.get_repo("scooter7/VideoLMS")

# Function to fetch transcript using youtube_transcript_api
def fetch_transcript(video_id: str) -> str:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        formatter = TextFormatter()
        formatted_transcript = formatter.format_transcript(transcript)
        return formatted_transcript
    except Exception as e:
        if "No transcript found" in str(e):
            st.error("No transcript found for this video.")
        else:
            st.error(f"Failed to fetch transcript: {e}")
        return None

# Function to get video information using yt-dlp
def get_video_info(video_url: str) -> tuple:
    opts = {}
    with YoutubeDL(opts) as yt:
        info = yt.extract_info(video_url, download=False)
        title = info.get("title", "")
        description = info.get("description", "")
        thumbnails = info.get("thumbnails", [])
        thumbnail_url = thumbnails[-1]["url"] if thumbnails else None
        return title, description, thumbnail_url

# Function to save the transcript to GitHub
def save_transcript_to_github(repo, video_title, video_id, transcript_text):
    try:
        file_path = f"Transcripts/{video_title.replace(' ', '_')}_{video_id}_transcription.txt"
        repo.create_file(
            file_path,
            f"Add transcription for {video_title}",
            transcript_text
        )
        st.success(f"Transcription saved to GitHub at {file_path}")
    except Exception as e:
        st.error(f"Failed to save transcription to GitHub: {e}")

# Streamlit app interface
st.header("YouTube Video Transcription and Quiz Generator")
youtube_url = st.text_input("Enter YouTube URL:")

if st.button("Fetch Video Info"):
    if youtube_url:
        video_id = re.search(r"v=([^&]+)", youtube_url).group(1)
        title, description, thumbnail_url = get_video_info(youtube_url)
        
        st.write(f"**Title:** {title}")
        st.write(f"**Description:** {description}")
        if thumbnail_url:
            st.image(thumbnail_url)

        transcript = fetch_transcript(video_id)
        if transcript:
            st.subheader("Transcript")
            st.write(transcript)
            
            save_transcript_to_github(repo, title, video_id, transcript)

            st.subheader("Generate Quiz")
            if st.button("Generate Quiz"):
                prompt = f"Based on the following content, create 10 quiz questions:\n\n{transcript}"
                client = OpenAI(api_key=st.secrets["openai"]["api_key"])
                try:
                    completion = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    questions = completion.choices[0].message["content"].strip()
                    st.write(questions)
                except Exception as e:
                    st.error(f"Failed to generate quiz: {e}")
    else:
        st.warning("Please enter a valid YouTube URL.")
