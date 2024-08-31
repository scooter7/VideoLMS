import streamlit as st
import json
import os
import openai
from github import Github
from youtubesearchpython import VideosSearch
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from streamlit_extras.stylable_container import stylable_container

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

# Function to retrieve top YouTube videos
def get_top_videos(topic):
    search = VideosSearch(topic, limit=50)  # Increase the limit to 50
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

        if duration_seconds <= 1200:  # Now under 20 minutes
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

# Topic selection
if "selected_topic" not in st.session_state:
    st.session_state["selected_topic"] = None

if "videos" not in st.session_state:
    st.session_state["videos"] = []

if "watched_videos" not in st.session_state:
    st.session_state["watched_videos"] = []

selected_topic = st.radio("Select a topic:", topics)

if st.button("Find Videos"):
    st.session_state["selected_topic"] = selected_topic
    st.session_state["videos"] = get_top_videos(selected_topic)
    st.session_state["watched_videos"] = [False] * len(st.session_state["videos"])
    if not st.session_state["videos"]:
        st.stop()

# Display videos
if st.session_state["videos"]:
    for i, video in enumerate(st.session_state["videos"]):
        st.video(video["link"])
        if st.button(f"Watched: {video['title']}", key=f"watched_{i}"):
            st.session_state["watched_videos"][i] = True

            # Transcribe video immediately after being watched
            try:
                transcription = YouTubeTranscriptApi.get_transcript(video["id"])
                transcription_text = " ".join([item['text'] for item in transcription])
                file_path = f"Transcripts/{st.session_state['selected_topic'].replace(' ', '_')}/{video['id']}_transcription.txt"
                repo.create_file(file_path, f"Add transcription for {video['title']}", transcription_text)
                st.success(f"Transcription saved for {video['title']}")
            except Exception as e:
                st.error(f"Transcription failed for {video['title']} due to: {str(e)}")
                transcription_text = None
            
            # Generate quiz questions
            if transcription_text:
                try:
                    prompt = f"Based on the following content, create 10 quiz questions:\n\n{transcription_text}"
                    response = openai.Completion.create(
                        model="gpt-4o-mini",
                        prompt=prompt,
                        max_tokens=1000
                    )
                    questions = response.choices[0].text.strip().split("\n")
                    st.session_state[f"questions_{i}"] = questions
                    st.success(f"Quiz questions generated for {video['title']}")
                except Exception as e:
                    st.error(f"Quiz generation failed for {video['title']} due to: {str(e)}")

# Provide Quiz Interface and Scoring
if all(st.session_state["watched_videos"]):
    st.write("Take the quiz")
    for i, video in enumerate(st.session_state["videos"]):
        if f"questions_{i}" in st.session_state:
            st.write(f"Quiz for {video['title']}")
            questions = st.session_state[f"questions_{i}"]
            score = 0
            for j, question in enumerate(questions):
                answer = st.radio(f"Q{j+1}: {question}", options=["Option 1", "Option 2", "Option 3", "Option 4"], key=f"answer_{i}_{j}")
                if st.button(f"Submit Q{j+1} for {video['title']}", key=f"submit_{i}_{j}"):
                    # Logic to check the correct answer goes here
                    score += 1  # This should be updated with actual checking logic
            st.write(f"Your score for {video['title']}: {score}/{len(questions)}")

st.stop()
