import streamlit as st
import os
import openai
from github import Github, GithubException
from pytube import Search
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript

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

# Function to retrieve top YouTube videos using pytube and ensure they have transcripts
def get_top_videos(topic):
    search = Search(topic)
    results = search.results

    filtered_videos = []

    for video in results:
        video_id = video.video_id
        video_details = video.vid_info.get('videoDetails', {})

        if 'lengthSeconds' in video_details:
            video_duration = int(video_details['lengthSeconds'])
            
            # Ensure the video duration is under 30 minutes (1800 seconds)
            if video_duration <= 1800:
                try:
                    # First, try to find manually created transcripts
                    transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
                    try:
                        transcript = transcripts.find_manually_created_transcript(['en'])
                    except NoTranscriptFound:
                        # Fallback to auto-generated transcript if manually created one is not available
                        transcript = transcripts.find_generated_transcript(['en'])
                    
                    video_link = f"https://www.youtube.com/watch?v={video_id}"
                    filtered_videos.append({
                        "title": video.title,
                        "link": video_link,
                        "id": video_id
                    })
                    
                    if len(filtered_videos) == 5:
                        break
                except (TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript):
                    st.warning(f"Transcription not available for video {video.title}. Skipping this video.")
                    continue

    if len(filtered_videos) < 5:
        st.error("Not enough videos with transcripts available. Please try a different topic or adjust the criteria.")
        return []

    return filtered_videos

# Function to create or update a file on GitHub
def create_or_update_file(repo, path, message, content):
    try:
        # Check if the file already exists
        file = repo.get_contents(path)
        # If it exists, update the file
        repo.update_file(file.path, message, content, file.sha)
    except GithubException as e:
        if e.status == 404:
            # If the file does not exist, create it
            repo.create_file(path, message, content)
        else:
            raise

# Initialize Streamlit session state
if "selected_topic" not in st.session_state:
    st.session_state["selected_topic"] = None

if "videos" not in st.session_state:
    st.session_state["videos"] = []

if "watched_videos" not in st.session_state:
    st.session_state["watched_videos"] = []

# Topic selection
selected_topic = st.radio("Select a topic:", topics)

# Button to find videos
if st.button("Find Videos"):
    st.session_state["selected_topic"] = selected_topic
    st.session_state["videos"] = get_top_videos(selected_topic)
    st.session_state["watched_videos"] = [False] * len(st.session_state["videos"])
    if not st.session_state["videos"]:
        st.stop()

# Display videos if available
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
                create_or_update_file(repo, file_path, f"Add transcription for {video['title']}", transcription_text)
                st.success(f"Transcription saved for {video['title']}")
            except Exception as e:
                st.error(f"Transcription failed for {video['title']} due to: {str(e)}")
                transcription_text = None
            
            # Generate quiz questions
            if transcription_text:
                try:
                    prompt = f"Based on the following content, create 10 quiz questions:\n\n{transcription_text}"
                    client = openai.Client()
                    completion = client.chat.completions.create(
                        model="gpt-4o-mini",
                        prompt=prompt,
                        max_tokens=1000
                    )
                    questions = completion.choices[0].text.strip().split("\n")
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
