import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
from yt_dlp import YoutubeDL
import openai
from github import Github
import json
import random

# Initialize OpenAI and GitHub
openai.api_key = st.secrets["openai"]["api_key"]
g = Github(st.secrets["github"]["token"])
repo = g.get_repo("scooter7/VideoLMS")

# Function to fetch transcript using youtube_transcript_api
def fetch_transcript(video_id: str) -> str:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return "\n".join([t['text'] for t in transcript])
    except NoTranscriptFound:
        return None
    except Exception as e:
        st.error(f"Failed to fetch transcript: {e}")
        return None

# Function to save transcript to GitHub
def save_transcript_to_github(video_id: str, transcript: str):
    try:
        content = repo.get_contents(f"transcripts/{video_id}.txt")
        repo.update_file(content.path, "Update transcript", transcript, content.sha)
    except:
        repo.create_file(f"transcripts/{video_id}.txt", "Add transcript", transcript)

# Function to generate quiz from transcript
def generate_quiz(transcript: str) -> list:
    questions = []
    sentences = transcript.split('\n')
    for _ in range(5):  # Generate 5 questions
        sentence = random.choice(sentences).strip()
        if not sentence or len(sentence.split()) < 5:
            continue
        question_type = random.choice(["mcq", "tf"])
        if question_type == "mcq":
            question = {"type": "mcq", "question": f"What does this statement imply? '{sentence}'", "options": ["True", "False", "Not Sure", "Maybe"], "answer": "True"}
        else:
            question = {"type": "tf", "question": f"True or False: '{sentence}'", "answer": "True"}
        questions.append(question)
    return questions

# App interface
st.title("Video LMS")
st.header("Manual YouTube URL Input")

video_url = st.text_input("Enter YouTube Video URL", "")
if st.button("Fetch Transcript and Generate Quiz"):
    if not video_url:
        st.error("Please provide a YouTube video URL.")
    else:
        video_id = video_url.split("v=")[-1]
        
        with st.spinner("Fetching transcript..."):
            transcript = fetch_transcript(video_id)
        
        if transcript:
            st.success("Transcript fetched successfully!")
            st.text_area("Transcript", transcript, height=300)
            
            with st.spinner("Saving transcript to GitHub..."):
                save_transcript_to_github(video_id, transcript)
                st.success("Transcript saved to GitHub!")
            
            with st.spinner("Generating quiz..."):
                quiz = generate_quiz(transcript)
                st.success("Quiz generated successfully!")
                st.write(quiz)
        else:
            st.error("Failed to fetch or generate a transcript.")
