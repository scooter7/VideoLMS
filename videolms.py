import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from openai import OpenAI
from github import Github
import yt_dlp
import openai
import random

# Initialize OpenAI and GitHub clients
client = openai.Client(api_key=st.secrets["openai"]["api_key"])
g = Github(st.secrets["github"]["token"])
repo = g.get_repo("scooter7/VideoLMS")

def fetch_transcript(video_id: str) -> str:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        formatted_transcript = " ".join([entry['text'] for entry in transcript])
        return formatted_transcript
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        st.error(f"Failed to fetch transcript: {str(e)}")
        return None

def save_transcript_to_github(transcript: str, video_id: str):
    try:
        path = f"transcripts/{video_id}.txt"
        repo.create_file(path, f"Add transcript for {video_id}", transcript)
        st.success("Transcript saved to GitHub successfully!")
    except Exception as e:
        st.error(f"Failed to save transcript to GitHub: {str(e)}")

def generate_quiz(transcript: str):
    prompt = f"Generate 5 quiz questions (either multiple choice or true/false) based on the following transcript: {transcript}"
    try:
        completions = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                      {"role": "user", "content": prompt}]
        )
        quiz_data = completions.choices[0].message["content"]
        return quiz_data
    except Exception as e:
        st.error(f"Failed to generate quiz questions: {str(e)}")
        return None

def process_quiz(quiz_data):
    questions = quiz_data.split("\n\n")
    for i, question in enumerate(questions):
        st.write(f"Question {i+1}: {question.split(':')[1].strip()}")
        options = ["a", "b", "c", "d"]
        selected_option = st.radio(f"Your answer for Question {i+1}:", options)
        correct_answer = [line for line in question.split('\n') if line.startswith("Correct answer:")][0].split(":")[1].strip()

        if selected_option in correct_answer:
            st.success("Correct!")
        else:
            st.error(f"Incorrect. The correct answer was: {correct_answer}")

# Streamlit App Interface
st.title("Video Quiz Generator")
video_url = st.text_input("Enter YouTube Video URL:")

if video_url:
    video_id = video_url.split("v=")[-1]
    transcript = fetch_transcript(video_id)

    if transcript:
        # Comment out or remove this line to hide the transcript
        # st.write(transcript)

        save_transcript_to_github(transcript, video_id)

        if st.button("Generate Quiz"):
            quiz_data = generate_quiz(transcript)
            if quiz_data:
                process_quiz(quiz_data)
