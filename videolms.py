import streamlit as st
import json
import yt2text
from youtubesearchpython import VideosSearch
import os
import openai
from github import Github
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# Set up Streamlit
st.set_page_config(page_title="Video Learning App", layout="wide")

# Set OpenAI API Key
openai.api_key = st.secrets["openai"]["api_key"]

# GitHub authentication
github = Github(st.secrets["github"]["token"])
repo_name = "scooter7/VideoLMS"
repo = github.get_repo(repo_name)

# Define available topics
topics = ["Communication Skills", "Conflict Resolution Skills", "Time Management Skills"]

# Initialize session state
if "selected_topic" not in st.session_state:
    st.session_state["selected_topic"] = None
if "videos" not in st.session_state:
    st.session_state["videos"] = []
if "watched_videos" not in st.session_state:
    st.session_state["watched_videos"] = []
if "all_watched" not in st.session_state:
    st.session_state["all_watched"] = False
if "transcription_errors" not in st.session_state:
    st.session_state["transcription_errors"] = False

# Topic selection
if st.session_state["selected_topic"] is None:
    selected_topic = st.radio("Select a topic:", topics)

    if st.button("Find Videos"):
        st.session_state["selected_topic"] = selected_topic
        st.session_state["videos"] = get_top_videos(selected_topic)
        st.session_state["watched_videos"] = [False] * len(st.session_state["videos"])
        if not st.session_state["videos"]:
            st.session_state["transcription_errors"] = True

# Function to retrieve top YouTube videos
def get_top_videos(topic):
    search = VideosSearch(topic, limit=30)
    results = search.result()["result"]

    filtered_videos = []

    for video in results:
        video_duration = video.get("duration")
        video_link = video.get("link")
        video_id = video_link.split("v=")[-1]

        # Convert video duration to seconds
        duration_parts = video_duration.split(":")
        if len(duration_parts) == 2:  # Format MM:SS
            duration_seconds = int(duration_parts[0]) * 60 + int(duration_parts[1])
        elif len(duration_parts) == 3:  # Format HH:MM:SS
            duration_seconds = int(duration_parts[0]) * 3600 + int(duration_parts[1]) * 60 + int(duration_parts[2])
        else:
            continue

        if duration_seconds <= 900:  # Under 15 minutes
            try:
                # Check if transcript is available
                YouTubeTranscriptApi.get_transcript(video_id)
                filtered_videos.append(video)
                if len(filtered_videos) == 5:
                    break
            except (TranscriptsDisabled, NoTranscriptFound):
                continue

    if len(filtered_videos) < 5:
        st.error("Not enough videos with transcripts available. Please try a different topic or adjust the criteria.")
        return []

    return filtered_videos

# Video Display and Watch Handling
if st.session_state["selected_topic"] and not st.session_state["transcription_errors"]:
    st.header(f"Topic: {st.session_state['selected_topic']}")
    for i, video in enumerate(st.session_state["videos"]):
        if not st.session_state["watched_videos"][i]:
            st.video(video["link"])
            if st.button(f"Watched: {video['title']}", key=f"watched_{i}"):
                st.session_state["watched_videos"][i] = True

                # Transcribe the video immediately after watching
                video_id = video["id"]
                try:
                    transcript = YouTubeTranscriptApi.get_transcript(video_id)
                    transcription_text = " ".join([item['text'] for item in transcript])

                    # Save transcription to GitHub
                    topic_folder = f"{st.session_state['selected_topic'].replace(' ', '_')}"
                    file_path = f"Transcripts/{topic_folder}/{video_id}_transcription.txt"
                    repo.create_file(file_path, f"Add transcription for {video['title']}", transcription_text)

                    # Generate quiz questions based on the transcript
                    prompt = f"Based on the following content, create 10 quiz questions:\n\n{transcription_text}"
                    client = openai.Client()
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "system", "content": prompt}],
                        max_tokens=1000
                    )
                    questions = response.choices[0].message['content'].strip().split("\n")
                    st.session_state[f"questions_{i}"] = questions

                    st.success(f"Transcription saved and quiz generated for {video['title']}!")
                except Exception as e:
                    st.error(f"Transcription failed for {video['title']} due to: {e}")
        else:
            st.write(f"{video['title']} - Watched and processed.")

    # Check if all videos are watched
    if all(st.session_state["watched_videos"]):
        st.session_state["all_watched"] = True

# Provide Quiz Interface and Scoring
if st.session_state.get("all_watched", False):
    st.write("Take the quiz")
    score = 0
    total_questions = 0
    for i, video in enumerate(st.session_state["videos"]):
        questions = st.session_state.get(f"questions_{i}", [])
        for j, question in enumerate(questions):
            answer = st.radio(f"Q{total_questions+1}: {question}", options=["Option 1", "Option 2", "Option 3", "Option 4"])
            total_questions += 1
            if st.button(f"Submit Q{total_questions}", key=f"submit_{total_questions}"):
                # Placeholder logic for checking correct answers
                # Increment score if correct
                score += 1

    st.write(f"Your final score: {score}/{total_questions}")
