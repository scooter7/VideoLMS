import streamlit as st
import pandas as pd
import requests
import json
import base64
import openai
import re
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

# GitHub Helper Functions
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

# Quiz Score Management
def load_scores():
    url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{SCORES_DATA_FILE_PATH}"
    try:
        return pd.read_csv(url)
    except Exception as e:
        st.warning(f"Could not load scores. Creating a new file: {e}")
        return pd.DataFrame(columns=["username", "video_id", "score"])

def save_score(username, video_id, score):
    scores = load_scores()
    new_score = pd.DataFrame({"username": [username], "video_id": [video_id], "score": [score]})
    scores = pd.concat([scores, new_score], ignore_index=True)
    upload_file_to_github(SCORES_DATA_FILE_PATH, scores.to_csv(index=False), "Add new score")

# Authentication
def authenticate(username, password):
    if username == "james@shmooze.io" and password == "Conversations7!":
        return "admin"
    users = load_users()
    user = users[(users["username"] == username) & (users["password"] == password)]
    return "user" if not user.empty else None

# YouTube Search Functionality
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
    return [
        {"id": item["id"]["videoId"], "title": item["snippet"]["title"]}
        for item in search_response["items"]
    ]

# Transcript Summarization and Quiz Generation
def summarize_transcript(transcript):
    prompt = f"Summarize the following transcript:\n\n{transcript}"
    response = openai.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content.strip()

def generate_quiz(summary):
    prompt = f"Generate five multiple-choice questions from this summary:\n\n{summary}"
    response = openai.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content.strip()

# Ensure session state variables are initialized
if "view_as_user" not in st.session_state:
    st.session_state["view_as_user"] = False

if "selected_videos" not in st.session_state:
    st.session_state["selected_videos"] = []

if "quizzes" not in st.session_state:
    st.session_state["quizzes"] = {}

if "quiz_scores" not in st.session_state:
    st.session_state["quiz_scores"] = {}

# Streamlit App
st.title("AI Video Quiz Generator")

# Login / Registration Workflow
if "username" not in st.session_state:
    st.sidebar.title("Login / Register")
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

# Admin Features
if "username" in st.session_state and st.session_state["role"] == "admin":
    st.write("### Admin Dashboard")

    # Toggle to view user features
    st.session_state["view_as_user"] = st.checkbox("View as User", value=st.session_state["view_as_user"])

    if not st.session_state["view_as_user"]:
        # Admin Features
        st.write("**All Users**")
        st.dataframe(load_users())
        st.write("**Quiz Scores**")
        st.dataframe(load_scores())
    else:
        st.write("### User Features")

# User Features
if "username" in st.session_state:
    topic = st.selectbox("Select a Topic", ["AI in Manufacturing", "AI in Healthcare", "AI in Insurance"])
    if topic:
        # Search Videos for Selected Topic
        videos = search_youtube_videos(topic)
        st.write(f"### Videos for {topic}")
        for video in videos:
            st.video(f"https://www.youtube.com/watch?v={video['id']}")
            if st.button(f"I watched this! Quiz me! ({video['title']})", key=f"quiz_{video['id']}"):
                transcript = f"Transcript for video {video['id']}"  # Placeholder for actual transcript ingestion
                summary = summarize_transcript(transcript)
                quiz = generate_quiz_from_summary(summary)

                # Save quiz in session state
                st.session_state["quizzes"][video["id"]] = {
                    "title": video["title"],
                    "questions": quiz,
                    "answers": [None] * 5,  # Placeholder for user answers
                    "correct_answers": [q["answer"] for q in quiz]
                }

    # Display Quizzes
    if st.session_state["quizzes"]:
        st.write("### Take Your Quizzes")
        for video_id, quiz_data in st.session_state["quizzes"].items():
            st.write(f"#### Quiz for {quiz_data['title']}")
            total_correct = 0
            for i, question in enumerate(quiz_data["questions"]):
                st.write(f"**Question {i + 1}:** {question['question']}")
                user_answer = st.radio(
                    f"Select your answer for Question {i + 1}:",
                    options=question["options"],
                    key=f"answer_{video_id}_{i}"
                )
                quiz_data["answers"][i] = user_answer

                # Submit button for each quiz
            if st.button(f"Submit Quiz ({quiz_data['title']})", key=f"submit_{video_id}"):
                for i, correct_answer in enumerate(quiz_data["correct_answers"]):
                    if quiz_data["answers"][i] == correct_answer:
                        total_correct += 1
                        st.success(f"Question {i + 1}: Correct!")
                    else:
                        st.error(f"Question {i + 1}: Incorrect. Correct answer: {correct_answer}")
                st.write(f"Your Score: {total_correct} / 5")

                # Save score to session state and GitHub
                st.session_state["quiz_scores"][video_id] = total_correct
                save_score(st.session_state["username"], video_id, total_correct)
