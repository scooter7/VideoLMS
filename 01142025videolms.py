import streamlit as st
import pandas as pd
import openai
import re
from googleapiclient.discovery import build

# API configurations
openai.api_key = st.secrets["openai"]["api_key"]
YOUTUBE_API_KEY = st.secrets["youtube"]["api_key"]

# Authenticate User
def authenticate(username, password):
    if username == "james@shmooze.io" and password == "Conversations7!":
        return "admin"
    users = load_users()
    user = users[(users['username'] == username) & (users['password'] == password)]
    return "user" if not user.empty else None

# Load users from GitHub
def load_users():
    url = "https://raw.githubusercontent.com/YOUR_REPO/VideoLMS/main/UsersandScores/users.csv"
    try:
        return pd.read_csv(url)
    except Exception:
        return pd.DataFrame(columns=["username", "password"])

# Load quiz scores from GitHub
def load_scores():
    url = "https://raw.githubusercontent.com/YOUR_REPO/VideoLMS/main/UsersandScores/scores.csv"
    try:
        return pd.read_csv(url)
    except Exception:
        return pd.DataFrame(columns=["username", "video_id", "score"])

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

    video_ids = [item["id"]["videoId"] for item in search_response["items"]]

    video_details = youtube.videos().list(
        id=",".join(video_ids),
        part="snippet,contentDetails,statistics"
    ).execute()

    filtered_videos = []
    for video in video_details["items"]:
        duration = video["contentDetails"]["duration"]
        minutes = parse_iso_duration(duration)
        if minutes >= 10:
            filtered_videos.append({
                "id": video["id"],
                "title": video["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={video['id']}",
                "views": int(video["statistics"].get("viewCount", 0)),
                "likes": int(video["statistics"].get("likeCount", 0)),
                "comments": int(video["statistics"].get("commentCount", 0))
            })

    return sorted(filtered_videos, key=lambda x: (-x["views"], -x["likes"], -x["comments"]))

def parse_iso_duration(duration):
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    return hours * 60 + minutes

# Transcript Summarization and Quiz Generation
def summarize_transcript(transcript):
    prompt = f"Summarize the following transcript:\n\n{transcript}"
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def generate_quiz_from_summary(summary):
    prompt = f"Generate five quiz questions based on the following summary:\n\n{summary}"
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# Streamlit App
st.title("AI Video Quiz Generator")

# Login and Session Management
if "username" not in st.session_state:
    st.sidebar.title("Login")
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
else:
    st.sidebar.write(f"Logged in as {st.session_state['username']} ({st.session_state['role']})")
    if st.sidebar.button("Logout"):
        del st.session_state["username"]
        del st.session_state["role"]
        st.experimental_rerun()

# Main Logic Based on Role
if "username" in st.session_state:
    if st.session_state["role"] == "admin":
        st.sidebar.title("Admin Panel")
        st.write("### Admin Features")
        st.write("#### All Users")
        st.dataframe(load_users())
        st.write("#### Quiz Scores")
        st.dataframe(load_scores())

        # Add a toggle for the admin to switch to user view
        if st.sidebar.checkbox("Switch to User Features"):
            st.sidebar.title("Choose a Topic")
            topic = st.sidebar.radio("Select a Topic", ["AI in Manufacturing", "AI in Healthcare", "AI in Insurance"])

            if topic:
                st.write(f"### Videos for {topic}")
                with st.spinner("Searching for top videos..."):
                    videos = search_youtube_videos(topic)

                if videos:
                    selected_videos = st.multiselect(
                        "Select up to 5 videos to watch:",
                        videos,
                        format_func=lambda x: f"{x['title']} (Views: {x['views']}, Likes: {x['likes']}, Comments: {x['comments']})",
                        key="selected_videos"
                    )

                    if len(selected_videos) > 5:
                        st.warning("You can select up to 5 videos only.")

                    if st.button("Confirm Selection"):
                        st.session_state["selected_videos"] = selected_videos

            if "selected_videos" in st.session_state:
                for video in st.session_state["selected_videos"]:
                    st.video(video["url"])
                    if st.button(f"I watched this video: {video['title']}", key=f"watched_{video['id']}"):
                        transcript = f"Dummy transcript for video {video['id']}."
                        summary = summarize_transcript(transcript)
                        quiz = generate_quiz_from_summary(summary)

                        st.write(f"**Quiz for {video['title']}**")
                        st.write(quiz)
