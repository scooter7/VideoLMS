import streamlit as st
import openai
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from github import Github
import yt_dlp

# Set your OpenAI and GitHub API keys in Streamlit secrets
openai.api_key = st.secrets["openai"]["api_key"]
github_token = st.secrets["github"]["token"]

# Initialize GitHub client
g = Github(github_token)
repo = g.get_repo("scooter7/VideoLMS")

# Function to fetch transcript using youtube-transcript-api
def fetch_transcript(video_id: str) -> str:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        formatter = TextFormatter()
        formatted_transcript = formatter.format_transcript(transcript)
        return formatted_transcript
    except Exception as e:
        st.error(f"Failed to fetch transcript: {e}")
        return None

# Function to save transcript to GitHub
def save_transcript_to_github(filename: str, content: str):
    try:
        contents = repo.get_contents(filename)
        repo.update_file(contents.path, f"Update {filename}", content, contents.sha)
    except:
        repo.create_file(filename, f"Create {filename}", content)

# Function to generate quiz questions from the transcript
def generate_quiz(transcript):
    sentences = transcript.split('.')
    questions = []

    for sentence in sentences[:5]:  # Limiting to 5 questions for simplicity
        question = {
            "type": "mcq",
            "question": f"What does this statement imply? '{sentence.strip()}'",
            "options": ["True", "False", "Not Sure", "Maybe"],
            "answer": "True"
        }
        questions.append(question)

    return questions

# Streamlit UI
st.title("YouTube Video Transcription and Quiz Generator")

video_url = st.text_input("Enter YouTube Video URL:")
transcript = None

if video_url and st.button("Fetch Transcript"):
    video_id = video_url.split("v=")[-1]
    transcript = fetch_transcript(video_id)

    if transcript:
        st.success("Transcript fetched successfully!")
        st.text_area("Transcript:", transcript, height=300)
        save_transcript_to_github(f"{video_id}_transcript.txt", transcript)
    else:
        st.error("Failed to fetch or generate a transcript.")

if st.button("Generate Quiz") and transcript:
    questions = generate_quiz(transcript)
    st.write("Generated Quiz Questions:")
    for i, question in enumerate(questions):
        st.write(f"Q{i+1}: {question['question']}")
        for option in question['options']:
            st.write(f"- {option}")
else:
    st.info("You need to fetch the transcript first before generating the quiz.")
