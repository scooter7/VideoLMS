import streamlit as st
import pandas as pd
import requests
import openai
from googleapiclient.discovery import build

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
if "quizzes" not in st.session_state:
    st.session_state["quizzes"] = {}
if "quiz_scores" not in st.session_state:
    st.session_state["quiz_scores"] = {}
if "view_as_user" not in st.session_state:
    st.session_state["view_as_user"] = False

# Helper Functions for GitHub
def get_file_sha(file_path):
    url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("sha", None)
    return None

def upload_file_to_github(file_path, content, message):
    url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Content-Type": "application/json"}
    sha = get_file_sha(file_path)
    data = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "branch": "main"
    }
    if sha:
        data["sha"] = sha

    response = requests.put(url, headers=headers, data=json.dumps(data))
    if response.status_code not in [200, 201]:
        st.error(f"Failed to update {file_path} in GitHub: {response.text}")

# User Management
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

# Authentication
def authenticate(username, password):
    if username == "james@shmooze.io" and password == "Conversations7!":
        return "admin"
    users = load_users()
    user = users[(users["username"] == username) & (users["password"] == password)]
    return "user" if not user.empty else None

# YouTube Helper Functions
def search_youtube_videos(topic, max_results=10):
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

# Transcript and Quiz Generation
def fetch_video_transcript(video_id):
    # Placeholder for actual transcript fetching
    return f"Placeholder transcript for video {video_id}."

def summarize_transcript(transcript):
    prompt = f"Summarize the following transcript:\n\n{transcript}"
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
    prompt = f"""
    Based on the following summary, create a 5-question multiple-choice quiz.
    Each question should include 4 options, one of which is correct.

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

# Streamlit App
st.sidebar.title("Login / Register")
if st.session_state["username"] is None:
    option = st.sidebar.radio("Choose an option", ["Login", "Register"])
    if option == "Login":
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login"):
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

if st.session_state["role"] == "admin" and not st.session_state["view_as_user"]:
    st.write("### Admin Dashboard")
    st.checkbox("View as User", key="view_as_user")
    st.write("**All Users**")
    st.dataframe(load_users())

# User Features
if st.session_state["username"]:
    topic = st.selectbox("Select a Topic", ["AI in Manufacturing", "AI in Healthcare", "AI in Insurance"])
    if topic:
        with st.spinner("Fetching videos..."):
            videos = search_youtube_videos(topic)

        for video in videos[:10]:
            st.video(video["url"], format="YouTube")
            checked = st.checkbox(f"Select {video['title']}", key=f"select_{video['id']}")
            if checked:
                st.session_state["selected_videos"].append(video)
            else:
                st.session_state["selected_videos"] = [
                    v for v in st.session_state["selected_videos"] if v["id"] != video["id"]
                ]

        if st.session_state["selected_videos"]:
            st.write("### Selected Videos")
            for video in st.session_state["selected_videos"]:
                st.write(f"- {video['title']} (Views: {video['views']}, Likes: {video['likes']})")
