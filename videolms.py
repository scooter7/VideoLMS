import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from github import Github
import openai
import random

# Initialize GitHub client
g = Github(st.secrets["github"]["token"])
repo = g.get_repo("scooter7/VideoLMS")

# Function to fetch transcript using youtube_transcript_api
def fetch_transcript(video_id: str) -> str:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        formatted_transcript = " ".join([item['text'] for item in transcript])
        return formatted_transcript
    except Exception as e:
        if "No transcript found" in str(e):
            st.error("No transcript found for this video.")
        else:
            st.error(f"Failed to fetch transcript: {e}")
        return None

# Function to save the transcript to GitHub
def save_transcript_to_github(repo, video_title, video_id, transcript_text):
    file_path = f"Transcripts/{video_title.replace(' ', '_')}_{video_id}_transcription.txt"
    try:
        existing_file = None
        try:
            existing_file = repo.get_contents(file_path)
        except:
            pass  # File doesn't exist

        if existing_file:
            # Update the existing file
            repo.update_file(
                file_path,
                f"Update transcription for {video_title}",
                transcript_text,
                sha=existing_file.sha
            )
        else:
            # Create a new file
            repo.create_file(
                file_path,
                f"Add transcription for {video_title}",
                transcript_text
            )
        st.success(f"Transcription saved to GitHub at {file_path}")
    except Exception as e:
        st.error(f"Failed to save transcription to GitHub: {e}")

# Function to generate quiz from transcript
def generate_quiz_from_transcript(transcript):
    def create_question(text):
        question_type = random.choice(["multiple_choice", "true_false"])
        if question_type == "multiple_choice":
            return {
                "type": "multiple_choice",
                "question": f"What is the correct answer based on the following content: {text}",
                "options": [
                    f"Correct answer from {text}",
                    "Incorrect answer 1",
                    "Incorrect answer 2",
                    "Incorrect answer 3"
                ],
                "answer": 0  # index of the correct answer
            }
        else:
            return {
                "type": "true_false",
                "question": f"True or False: {text}",
                "answer": random.choice([True, False])
            }

    sentences = transcript.split('.')
    questions = []
    for _ in range(5):
        sentence = random.choice(sentences).strip()
        if sentence:
            questions.append(create_question(sentence))

    return questions

# Streamlit app interface
st.header("YouTube Video Transcription and Quiz Generator")
video_url = st.text_input("Enter YouTube Video URL:")

if st.button("Fetch Transcript and Generate Quiz"):
    if video_url:
        video_id = video_url.split("v=")[-1]
        transcript = fetch_transcript(video_id)
        if transcript:
            st.subheader("Transcript")
            st.write(transcript)
            
            save_transcript_to_github(repo, "Video Title", video_id, transcript)

            st.subheader("Generate Quiz")
            questions = generate_quiz_from_transcript(transcript)
            if questions:
                st.subheader("Quiz Questions")
                for question in questions:
                    st.write(question['question'])
                    if question['type'] == "multiple_choice":
                        for idx, option in enumerate(question['options']):
                            st.write(f"{idx + 1}. {option}")
                    else:
                        st.write("Answer: True/False")
    else:
        st.warning("Please enter a valid YouTube video URL.")
