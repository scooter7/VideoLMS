import streamlit as st
import openai
import random
import os
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import yt_dlp

# Set your OpenAI API key
openai.api_key = st.secrets["openai"]["api_key"]

# Function to fetch transcript using youtube_transcript_api
def fetch_transcript(video_id: str) -> str:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([entry['text'] for entry in transcript])
        return transcript_text
    except (TranscriptsDisabled, NoTranscriptFound):
        return None

# Function to download video audio and transcribe using Whisper
def transcribe_with_whisper(video_url: str) -> str:
    try:
        # Download video audio
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'temp_audio.mp3',
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Transcribe with Whisper
        with open("temp_audio.mp3", "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
        
        os.remove("temp_audio.mp3")  # Clean up
        return transcript["text"]
    except Exception as e:
        st.error(f"Failed to transcribe video using Whisper: {e}")
        return None

# Function to generate quiz questions from transcript
def generate_quiz_questions(transcript: str, num_questions: int = 5) -> list:
    questions = []
    sentences = transcript.split(". ")
    
    for _ in range(num_questions):
        sentence = random.choice(sentences).strip()
        
        if random.choice([True, False]):
            # True/False question
            question = {
                "type": "true_false",
                "question": f"Is the following statement true or false? '{sentence}'",
                "options": ["True", "False"],
                "answer": "True"
            }
        else:
            # Multiple choice question
            wrong_options = [
                "Not Sure",
                "Maybe",
                "Unrelated",
                "None of the above"
            ]
            correct_answer = "True"
            question = {
                "type": "mcq",
                "question": f"What does this statement imply? '{sentence}'",
                "options": ["True", "False"] + random.sample(wrong_options, 2),
                "answer": correct_answer
            }
        
        questions.append(question)
    
    return questions

# Streamlit App
st.title("YouTube Video Transcript and Quiz Generator")
st.markdown("Generate transcripts and quiz questions from YouTube videos.")

# Input YouTube URL
video_url = st.text_input("Enter YouTube Video URL", "")

if st.button("Fetch Transcript"):
    if video_url:
        video_id = video_url.split("v=")[-1]
        
        with st.spinner("Fetching transcript..."):
            transcript = fetch_transcript(video_id)
        
        if transcript:
            st.success("Transcript fetched successfully!")
            st.session_state["transcript"] = transcript
        else:
            st.warning("No transcript available, trying Whisper...")
            with st.spinner("Transcribing with Whisper..."):
                transcript = transcribe_with_whisper(video_url)
                if transcript:
                    st.success("Transcription successful using Whisper!")
                    st.session_state["transcript"] = transcript
                else:
                    st.error("Failed to fetch or generate a transcript.")
    else:
        st.error("Please enter a valid YouTube URL.")

# Display the transcript if available
if "transcript" in st.session_state:
    st.subheader("Transcript")
    st.write(st.session_state["transcript"])

    if st.button("Generate Quiz"):
        with st.spinner("Generating quiz..."):
            quiz_questions = generate_quiz_questions(st.session_state["transcript"])
            st.session_state.quiz_questions = quiz_questions
            st.success("Quiz generated!")

# Display the generated quiz questions
if "quiz_questions" in st.session_state:
    st.subheader("Generated Quiz Questions")
    
    for idx, question in enumerate(st.session_state.quiz_questions, start=1):
        st.write(f"**Question {idx}:** {question['question']}")
        for option in question["options"]:
            st.write(f"- {option}")
        st.write(f"**Answer:** {question['answer']}")
        st.write("---")

