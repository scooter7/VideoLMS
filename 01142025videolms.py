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

# YouTube Transcript Fetcher
def fetch_youtube_transcript(video_id):
    return f"This is a dummy transcript for video ID: {video_id}."

# Transcript Summarization and Quiz Generation
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
        if response.choices and response.choices[0].message.content:
            response_text = response.choices[0].message.content.strip()
            return parse_questions_from_response(response_text)
    except Exception as e:
        st.error(f"Error generating quiz: {e}")
        return []

# Streamlit App Logic
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
        st.experimental_rerun()

# Display Videos and Quizzes
if "username" in st.session_state:
    st.title("AI Video Quiz Generator")
    topic = st.selectbox("Select a Topic", ["AI in Manufacturing", "AI in Healthcare", "AI in Insurance"])
    if topic:
        videos = [{"id": f"video{i}", "title": f"Video {i} for {topic}"} for i in range(1, 6)]
        for video in videos:
            st.video(f"https://www.youtube.com/watch?v={video['id']}")
            if st.button(f"I watched this! Quiz me! ({video['title']})", key=f"quiz_{video['id']}"):
                transcript = fetch_youtube_transcript(video["id"])
                summary = summarize_transcript(transcript)
                quiz = generate_quiz_from_summary(summary)
                st.session_state["quizzes"] = {
                    video["id"]: {"questions": quiz}
                }

    if st.session_state.get("quizzes"):
        for video_id, quiz_data in st.session_state["quizzes"].items():
            st.write(f"### Quiz for {video_id}")
            for q in quiz_data["questions"]:
                st.write(q["question"])
                st.radio("Options", q["options"], key=f"{video_id}_{q['question']}")
