import streamlit as st
import json
from youtube_video_processing import YT2text
from youtubesearchpython import VideosSearch
import os
import openai
from github import Github
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

# Topic selection
selected_topic = st.radio("Select a topic:", topics)

# Button to start the video retrieval process
if st.button("Find Videos"):
    # Logic to search for YouTube videos goes here
    st.session_state["selected_topic"] = selected_topic
    videos = get_top_videos(selected_topic)
    for video in videos:
        video_url = video["link"]
        st.video(video_url)
        if st.button(f"Watched: {video['title']}", key=video["id"]):
            st.session_state[f"watched_{video['id']}"] = True

    # Check if all videos have been watched
    if all([st.session_state.get(f"watched_{video['id']}", False) for video in videos]):
        st.session_state["all_watched"] = True

# Function to retrieve top YouTube videos
def get_top_videos(topic):
    search = VideosSearch(topic, limit=5)
    results = search.result()["result"]
    return results

# Transcribe Videos and Save to GitHub
if st.session_state.get("all_watched", False):
    st.write("All videos watched! Transcribing and saving...")
    topic_folder = f"{st.session_state['selected_topic'].replace(' ', '_')}"
    repo.create_git_tree([f"Transcripts/{topic_folder}/.keep"], repo.get_branch("main").commit)
    
    for video in videos:
        video_id = video["id"]
        transcription = YT2text().extract(video_id=video_id)
        file_path = f"Transcripts/{topic_folder}/{video_id}_transcription.txt"
        repo.create_file(file_path, f"Add transcription for {video['title']}", transcription)

    st.success("Transcriptions saved to GitHub!")

# Generate Quiz Questions
if st.session_state.get("all_watched", False):
    st.write("Generating quiz questions...")
    questions = []

    for video in videos:
        transcription = YT2text().extract(video_id=video["id"])
        prompt = f"Based on the following content, create 10 quiz questions:\n\n{transcription}"
        response = openai.Completion.create(
            model="gpt-4o-mini",
            prompt=prompt,
            max_tokens=1000
        )
        questions.append(response.choices[0].text.strip())

    st.write("Here are your quiz questions:")
    for i, question in enumerate(questions):
        st.write(f"Q{i+1}: {question}")

# Provide Quiz Interface and Scoring
if st.session_state.get("all_watched", False):
    st.write("Take the quiz")
    score = 0
    for i, question in enumerate(questions):
        answer = st.radio(f"Q{i+1}: {question}", options=["Option 1", "Option 2", "Option 3", "Option 4"])
        if st.button(f"Submit Q{i+1}", key=f"submit_{i}"):
            # Logic to check the correct answer goes here
            # Increment score if correct
            score += 1

    st.write(f"Your final score: {score}/{len(questions)}")
