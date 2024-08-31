import streamlit as st
from youtube_video_processing import YT2text
from github import Github
import openai
import os

# Set up Streamlit app
st.set_page_config(page_title="Video LMS", layout="wide")

# Set up the OpenAI API key
openai.api_key = st.secrets["openai"]["api_key"]

# Initialize GitHub client
g = Github(st.secrets["github"]["token"])
repo = g.get_repo("scooter7/your-repo-name")

# Function to transcribe a video
def transcribe_video(video_id, video_info=None):
    yt2text = YT2text()

    # Try to extract transcript using YT2text
    try:
        transcription = yt2text.extract(video_id=video_id)
        return transcription
    except Exception as e:
        st.warning(f"Initial transcription failed due to: {str(e)}. Trying Whisper...")
    
    # If transcription fails, use Whisper as fallback
    try:
        if video_info:
            transcription = yt2text.extract_content_from_youtube_video_without_transcription(
                video_id=video_id, video_info=video_info
            )
            return transcription
        else:
            st.error("Video info is required for Whisper transcription.")
            return None
    except Exception as e:
        st.error(f"Transcription failed with Whisper due to: {str(e)}")
        return None

# Function to retrieve top YouTube videos (modify this based on your video retrieval logic)
def get_top_videos(topic):
    # Implement your logic to retrieve top YouTube videos for the given topic
    # Make sure to filter videos that have transcripts enabled
    return []

# Main app interface
st.title("Video LMS - Learning Management System")

# Topic selection
topics = ["Time Management", "Communication Skills", "Conflict Resolution Skills"]
selected_topic = st.radio("Select a topic:", topics)

# Button to find videos
if st.button("Find Videos"):
    st.session_state["selected_topic"] = selected_topic
    st.session_state["videos"] = get_top_videos(selected_topic)
    st.session_state["watched_videos"] = [False] * len(st.session_state["videos"])

    if not st.session_state["videos"]:
        st.warning("No videos found with transcripts available. Please try a different topic or adjust the criteria.")
        st.stop()

# Display videos and allow the user to mark them as watched
if "videos" in st.session_state and st.session_state["videos"]:
    for i, video in enumerate(st.session_state["videos"]):
        st.video(video["link"])
        if st.checkbox(f"I've watched this video ({video['title']})", key=f"watched_{i}"):
            st.session_state["watched_videos"][i] = True

# Button to start transcription and quiz generation after watching all videos
if st.button("I've watched all videos"):
    if all(st.session_state["watched_videos"]):
        st.success("All videos watched! Transcribing and saving...")

        # Loop through each video, transcribe, and save the transcription
        for i, video in enumerate(st.session_state["videos"]):
            video_id = video["id"]
            video_info = video  # Add any additional video information needed for Whisper

            transcription = transcribe_video(video_id, video_info)

            if transcription:
                # Save transcription to GitHub
                file_path = f"Transcriptions/{selected_topic}/{video_id}_transcription.txt"
                repo.create_file(
                    path=file_path,
                    message=f"Add transcription for {video['title']}",
                    content=transcription,
                    branch="main"
                )
            else:
                st.error(f"Transcription failed for {video['title']}")

        st.success("Transcriptions saved to GitHub!")

        # Generate quiz questions
        st.write("Generating quiz questions...")
        for i, video in enumerate(st.session_state["videos"]):
            video_id = video["id"]

            if video_id in st.session_state:
                transcription = st.session_state[video_id]
                prompt = f"Based on the following content, create 10 quiz questions:\n\n{transcription}"
                completion = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt}
                    ]
                )
                quiz_questions = completion.choices[0].message["content"]
                st.write(f"Quiz for {video['title']}:")
                st.write(quiz_questions)
            else:
                st.error(f"Quiz generation failed for {video['title']} due to unavailable transcription.")

    else:
        st.warning("Please watch all videos before proceeding.")

# Display quiz interface if quizzes are generated
if "quiz_questions" in st.session_state:
    st.subheader("Take the Quiz")
    score = 0
    for i, question in enumerate(st.session_state["quiz_questions"]):
        answer = st.radio(f"Q{i+1}: {question['question']}", question["options"], key=f"quiz_{i}")
        if st.button(f"Submit Q{i+1}", key=f"submit_{i}"):
            if answer == question["correct_answer"]:
                score += 1
                st.success("Correct!")
            else:
                st.error("Incorrect.")
    st.write(f"Your final score: {score}/{len(st.session_state['quiz_questions'])}")
