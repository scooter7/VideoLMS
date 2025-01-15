import streamlit as st
import pandas as pd
import requests
import openai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, VideoUnavailable
import base64
import json

# API configurations
openai.api_key = st.secrets["openai"]["api_key"]
YOUTUBE_API_KEY = st.secrets["youtube"]["api_key"]

# GitHub Configurations
GITHUB_API_URL = "https://api.github.com"
REPO_OWNER = st.secrets["github"]["username"]
REPO_NAME = "VideoLMS"
USER_DATA_FILE_PATH = "UsersandScores/users.csv"
SCORES_DATA_FILE_PATH = "UsersandScores/scores.csv"
GITHUB_TOKEN = st.secrets["github"]["token"]

# State Initialization
if "username" not in st.session_state:
    st.session_state["username"] = None
if "role" not in st.session_state:
    st.session_state["role"] = None
if "selected_videos" not in st.session_state:
    st.session_state["selected_videos"] = []
if "confirmed_videos" not in st.session_state:
    st.session_state["confirmed_videos"] = []
if "quizzes" not in st.session_state:
    st.session_state["quizzes"] = {}
if "quiz_scores" not in st.session_state:
    st.session_state["quiz_scores"] = {}
if "view_as_user" not in st.session_state:
    st.session_state["view_as_user"] = False

# Helper Functions
def search_youtube_videos(topic, max_results=10):
    """Searches for YouTube videos using the YouTube Data API."""
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    search_response = youtube.search().list(
        q=topic,
        part="snippet",
        type="video",
        maxResults=max_results,
        order="viewCount",
        publishedAfter="2024-01-01T00:00:00Z"
    ).execute()

    video_ids = [item["id"]["videoId"] for item in search_response["items"]]

    video_details = youtube.videos().list(
        id=",".join(video_ids),
        part="snippet,contentDetails,statistics"
    ).execute()

    videos = []
    for video in video_details["items"]:
        views = int(video["statistics"].get("viewCount", 0))
        likes = int(video["statistics"].get("likeCount", 0))
        comments = int(video["statistics"].get("commentCount", 0))
        videos.append({
            "id": video["id"],
            "title": video["snippet"]["title"],
            "url": f"https://www.youtube.com/watch?v={video['id']}",
            "views": views,
            "likes": likes,
            "comments": comments
        })

    return sorted(videos, key=lambda x: (-x["views"], -x["likes"], -x["comments"]))
    
def get_video_id(url):
    """Extracts video ID from a YouTube URL."""
    if "watch?v=" in url:
        return url.split("watch?v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return None

def fetch_video_details(api_key, video_id):
    """Fetches video details using the YouTube Data API."""
    youtube = build("youtube", "v3", developerKey=api_key)
    request = youtube.videos().list(part="snippet", id=video_id)
    response = request.execute()

    if "items" in response and len(response["items"]) > 0:
        snippet = response["items"][0]["snippet"]
        title = snippet["title"]
        description = snippet["description"]
        return title, description
    return None, None

def fetch_transcript(video_id):
    """Fetches the transcript for a YouTube video."""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([entry["text"] for entry in transcript]), None
    except NoTranscriptFound:
        return None, "No transcript available for this video."
    except VideoUnavailable:
        return None, "Video is unavailable or restricted."
    except Exception as e:
        return None, f"Error fetching transcript: {str(e)}"

def summarize_transcript(transcript):
    if not transcript:
        return None
    
    prompt = f"Summarize the following transcript in 100-150 words:\n\n{transcript}"
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"Error summarizing transcript: {e}")
        return None

def generate_quiz_from_summary(summary):
    if not summary:
        return None
    
    prompt = f"""
    Based on the following summary, create a 5-question multiple-choice quiz.
    Each question should have 4 options, one of which is correct.

    Summary:
    {summary}

    Example format:
    Question: What is the capital of France?
    A) Paris
    B) London
    C) Berlin
    D) Madrid
    Correct Answer: A) Paris
    ---
    """
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.choices[0].message.content.strip()
        return parse_questions_from_response(response_text)
    except Exception as e:
        st.error(f"Error generating quiz: {e}")
        return []

def parse_questions_from_response(response_text):
    questions = []
    question_blocks = response_text.split("---")
    for block in question_blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 6:
            question = {
                "question": lines[0].replace("Question:", "").strip(),
                "options": [
                    lines[1].replace("A)", "").strip(),
                    lines[2].replace("B)", "").strip(),
                    lines[3].replace("C)", "").strip(),
                    lines[4].replace("D)", "").strip(),
                ],
                "answer": lines[5].replace("Correct Answer:", "").strip(),
            }
            questions.append(question)
    return questions

# Helper Functions
def load_users():
    url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{USER_DATA_FILE_PATH}"
    try:
        return pd.read_csv(url)
    except Exception as e:
        st.warning(f"Could not load users. Creating a new file: {e}")
        return pd.DataFrame(columns=["username", "password"])

def save_user(username, password):
    users = load_users()
    if username in users["username"].values:
        st.warning("Username already exists. Choose another username.")
        return
    new_user = pd.DataFrame({"username": [username], "password": [password]})
    users = pd.concat([users, new_user], ignore_index=True)
    upload_file_to_github(USER_DATA_FILE_PATH, users.to_csv(index=False), "Add new user")

# Streamlit App
st.sidebar.title("Login / Register")
if st.session_state["username"] is None:
    option = st.sidebar.radio("Choose an option", ["Login", "Register"])
    if option == "Login":
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login"):
            if username == "james@shmooze.io" and password == "Conversations7!":
                st.session_state["username"] = username
                st.session_state["role"] = "admin"
                st.sidebar.success("Welcome, Admin!")
            else:
                role = authenticate(username, password)
                if role:
                    st.session_state["username"] = username
                    st.session_state["role"] = role
                    st.sidebar.success(f"Welcome, {username}!")
                else:
                    st.sidebar.error("Invalid credentials.")
    elif option == "Register":
        new_username = st.sidebar.text_input("Create a Username")
        new_password = st.sidebar.text_input("Create a Password", type="password")
        if st.sidebar.button("Register"):
            save_user(new_username, new_password)
else:
    st.sidebar.write(f"Logged in as: {st.session_state['username']} ({st.session_state['role']})")
    if st.sidebar.button("Logout"):
        del st.session_state["username"]
        del st.session_state["role"]
        del st.session_state["view_as_user"]
        st.experimental_rerun()

# Admin Area
if st.session_state["role"] == "admin" and not st.session_state["view_as_user"]:
    st.write("### Admin Dashboard")
    st.checkbox("View as User", key="view_as_user")
    st.write("**All Users**")
    st.dataframe(load_users())

# User Area
if st.session_state["username"]:
    topic = st.selectbox("Select a Topic", ["AI in Manufacturing", "AI in Healthcare", "AI in Insurance"])
    
    if topic:
        st.write("### Available Videos")
        videos = search_youtube_videos(topic)
        
        for video in videos[:10]:
            st.video(video["url"])
            checked = st.checkbox(f"Select {video['title']}", key=f"select_{video['id']}")
            
            if checked:
                st.session_state["selected_videos"].append(video)
            else:
                st.session_state["selected_videos"] = [
                    v for v in st.session_state["selected_videos"] if v["id"] != video["id"]
                ]

        if st.button("Confirm Selected Videos"):
            st.session_state["confirmed_videos"] = st.session_state["selected_videos"]

# Display confirmed videos and allow users to generate quizzes
if st.session_state["confirmed_videos"]:
    st.write("### Confirmed Videos")
    for idx, video in enumerate(st.session_state["confirmed_videos"]):
        st.video(video["url"])
        if st.button(f"I watched this! Quiz me! ({video['title']})", key=f"quiz_{video['id']}_{idx}"):
            transcript, error = fetch_transcript(video["id"])
            if transcript:
                summary = summarize_transcript(transcript)
                if summary:
                    quiz = generate_quiz_from_summary(summary)
                    if quiz:
                        st.session_state["quizzes"][video["id"]] = quiz
                        st.success(f"Quiz generated for {video['title']}")
                    else:
                        st.error("Failed to generate quiz questions.")
                else:
                    st.error("Failed to summarize the transcript.")
            else:
                st.warning(error)

# Display generated quizzes
for video_id, quiz in st.session_state["quizzes"].items():
    st.write(f"#### Quiz for Video ID: {video_id}")
    for q_idx, q in enumerate(quiz):
        st.write(f"**Question {q_idx + 1}:** {q['question']}")
        user_answer = st.radio(
            f"Select your answer for Question {q_idx + 1}:",
            options=[
                f"A) {q['options'][0]}",
                f"B) {q['options'][1]}",
                f"C) {q['options'][2]}",
                f"D) {q['options'][3]}"
            ],
            key=f"{video_id}_q{q_idx}_radio"
        )
        # Check answer
        if st.button(f"Submit Answer for Question {q_idx + 1}", key=f"{video_id}_submit_q{q_idx}"):
            correct_answer = q["answer"]
            # Ensure answer validation compares only the letter (A, B, C, D)
            if user_answer.split(")")[0] == correct_answer.split(")")[0]:
                st.success(f"Correct! The answer is {correct_answer}.")
            else:
                st.error(f"Incorrect! The correct answer is {correct_answer}.")

# Remove st.experimental_rerun()
# Use st.session_state.clear() for logout functionality if needed
if st.sidebar.button("Logout", key="logout_button"):
    st.session_state.clear()
    st.sidebar.success("Logged out successfully!")
