import streamlit as st
import json
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtubesearchpython import VideosSearch
import os
import openai
from github import Github, InputGitTreeElement
from streamlit_extras.stylable_container import stylable_container
import urllib.parse

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

# State management initialization
if "selected_topic" not in st.session_state:
    st.session_state["selected_topic"] = None
if "videos" not in st.session_state:
    st.session_state["videos"] = []
if "watched_videos" not in st.session_state:
    st.session_state["watched_videos"] = []

# Function to retrieve top YouTube videos with available transcripts
def get_top_videos(topic):
    search = VideosSearch(topic, limit=20)  # Increase limit to improve chances of finding suitable videos
    results = search.result()["result"]

    st.write("Raw search results:")
    st.write(results)  # Debugging: Show raw search results

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

        # Check for subtitles and video duration under 15 minutes
        if duration_seconds <= 900:  # 15 minutes
            try:
                # Attempt to retrieve the transcript; skip video if not available
                YouTubeTranscriptApi.get_transcript(video_id)
                filtered_videos.append(video)
                if len(filtered_videos) == 5:  # We only need 5 videos
                    break
            except (TranscriptsDisabled, NoTranscriptFound):
                continue

    st.write("Filtered videos with transcripts:")
    st.write(filtered_videos)  # Debugging: Show filtered videos

    return filtered_videos

# Function to sanitize and encode file names
def sanitize_filename(name):
    sanitized_name = name.replace(" ", "_").replace("/", "_")
    return urllib.parse.quote(sanitized_name, safe='')

# Topic selection
if st.session_state["selected_topic"] is None:
    selected_topic = st.radio("Select a topic:", topics)

    if st.button("Find Videos"):
        st.session_state["selected_topic"] = selected_topic
        st.session_state["videos"] = get_top_videos(selected_topic)
        st.session_state["watched_videos"] = [False] * len(st.session_state["videos"])

# Display videos and "Watched" buttons
if st.session_state["selected_topic"] is not None and st.session_state["videos"]:
    st.write(f"Topic: {st.session_state['selected_topic']}")
    for i, video in enumerate(st.session_state["videos"]):
        video_url = video["link"]
        st.video(video_url)
        if st.button(f"I've Watched: {video['title']}", key=f"watched_{i}"):
            st.session_state["watched_videos"][i] = True

    # Add "I've Watched All Videos" button to proceed
    if st.session_state["watched_videos"] and all(st.session_state["watched_videos"]):
        if st.button("I've Watched All Videos"):
            st.session_state["all_watched"] = True
else:
    st.write("No videos found for this topic. Please try a different topic or adjust the criteria.")

# Transcribe Videos and Save to GitHub
if st.session_state.get("all_watched", False):
    st.write("All videos watched! Transcribing and saving...")
    topic_folder = f"Transcripts/{sanitize_filename(st.session_state['selected_topic'])}/"
    
    # Create a tree element to create the folder
    tree_element = InputGitTreeElement(
        path=f"{topic_folder}.keep",
        mode="100644",  # regular file
        type="blob",
        content=""
    )
    
    # Get the base tree from the main branch
    base_tree = repo.get_git_tree(sha="main")
    
    # Create the tree with the folder and placeholder file
    tree = repo.create_git_tree([tree_element], base_tree)

    # Get the latest commit and convert it to a GitCommit object
    parent_commit = repo.get_commit(sha=repo.get_commits()[0].sha).commit

    # Create the commit
    commit = repo.create_git_commit(
        message="Create topic folder and .keep file",
        tree=tree,
        parents=[parent_commit]
    )

    # Save the transcriptions
    for i, video in enumerate(st.session_state["videos"]):
        video_id = video["id"]
        try:
            transcription = YouTubeTranscriptApi.get_transcript(video_id)
            transcription_text = " ".join([item['text'] for item in transcription])
            file_name = sanitize_filename(f"{video_id}_transcription.txt")
            file_path = f"{topic_folder}/{file_name}"
            repo.create_file(file_path, f"Add transcription for {video['title']}", transcription_text, branch="main")
        except TranscriptsDisabled:
            st.error(f"Transcription not available for video {video['title']}.")

    st.success("Transcriptions saved to GitHub!")

# Generate Quiz Questions
if st.session_state.get("all_watched", False):
    st.write("Generating quiz questions...")
    questions = []

    for i, video in enumerate(st.session_state["videos"]):
        video_id = video["id"]
        try:
            transcription = YouTubeTranscriptApi.get_transcript(video_id)
            transcription_text = " ".join([item['text'] for item in transcription])
            prompt = f"Based on the following content, create 10 quiz questions:\n\n{transcription_text}"
            client = openai.Client()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000
            )
            questions.append(response.choices[0].message['content'].strip())
        except (TranscriptsDisabled, NoTranscriptFound):
            st.error(f"Quiz generation failed for video {video['title']} due to unavailable transcription.")

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
