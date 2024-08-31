import streamlit as st
import openai
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

# Function to generate quiz questions using GPT-4o-mini
def generate_quiz_questions(transcript: str, num_questions: int = 5) -> list:
    questions = []

    prompt = f"""
    You are an expert quiz generator. Based on the following transcript, create {num_questions} quiz questions.
    Each question should be either a multiple-choice question (with 4 options) or a true/false question.
    Provide the correct answer for each question.

    Transcript:
    {transcript}
    """

    try:
        client = openai.Client(api_key=st.secrets["openai"]["api_key"])
        
        completions = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                      {"role": "user", "content": prompt}],
            max_tokens=500,
        )

        # Check if choices exist in the response
        if not completions.choices:
            st.error("No response received from the API. Check the model or input.")
            return []

        # Extract the content from the response
        completion_content = completions.choices[0].message.content.strip()
        st.write("API Response:", completion_content)  # Log the response content for debugging
        questions = completion_content.split("\n\n")

        parsed_questions = []
        for q in questions:
            if "True/False" in q:
                parsed_questions.append({
                    "type": "true_false",
                    "question": q.split("\n")[0],
                    "options": ["True", "False"],
                    "answer": "True" if "True" in q else "False"
                })
            else:
                parts = q.split("\n")
                if len(parts) >= 5:  # Ensure there are enough parts to form a valid question
                    parsed_questions.append({
                        "type": "mcq",
                        "question": parts[0],
                        "options": parts[1:5],
                        "answer": parts[5].split(":")[1].strip()  # Assuming format: "Answer: Correct Option"
                    })
                else:
                    st.warning(f"Skipping invalid question format: {q}")

        return parsed_questions

    except IndexError as e:
        st.error("Failed to generate quiz questions: The API response was incomplete or malformed.")
        st.error(f"Details: {e}")
        return []
    except Exception as e:
        st.error(f"Failed to generate quiz questions: {e}")
        return []

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

# Generate quiz questions
if "transcript" in st.session_state:
    if st.button("Generate Quiz"):
        with st.spinner("Generating quiz..."):
            quiz_questions = generate_quiz_questions(st.session_state["transcript"])
            st.session_state.quiz_questions = quiz_questions
            st.success("Quiz generated!")

# Display the generated quiz questions interactively
if "quiz_questions" in st.session_state:
    st.subheader("Generated Quiz")

    for idx, question in enumerate(st.session_state.quiz_questions):
        st.write(f"**Question {idx+1}:** {question['question']}")
        user_answer = st.radio(f"Your answer for Question {idx+1}:", question["options"], key=f"q{idx}")

        if st.button(f"Submit Answer for Question {idx+1}", key=f"submit{idx}"):
            # Clean the correct answer and user's selected answer
            correct_answer_clean = question["answer"].replace("**", "").strip().lower()
            selected_answer_clean = user_answer.replace("**", "").strip().lower()

            if selected_answer_clean == correct_answer_clean:
                st.success("Correct!")
            else:
                st.error(f"Incorrect. The correct answer was: **{question['answer'].replace('**', '').strip()}**")
        st.write("---")
