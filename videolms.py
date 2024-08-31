import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from github import Github
import openai
import random
import requests

# Initialize GitHub client
g = Github(st.secrets["github"]["token"])
repo = g.get_repo("scooter7/VideoLMS")

# YouTube Data API setup
YOUTUBE_API_KEY = st.secrets["youtube"]["api_key"]
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"

# Function to search for videos using YouTube Data API
def search_videos(topic: str):
    search_url = f"{YOUTUBE_API_URL}/search"
    params = {
        'part': 'snippet',
        'q': topic,
        'type': 'video',
        'maxResults': 10,
        'key': YOUTUBE_API_KEY
    }
    response = requests.get(search_url, params=params)
    results = response.json()
    
    videos = []
    for item in results.get('items', []):
        video_id = item['id']['videoId']
        title = item['snippet']['title']
        url = f"https://www.youtube.com/watch?v={video_id}"
        videos.append({
            'id': video_id,
            'title': title,
            'url': url
        })
    return videos

# Function to fetch transcript using youtube_transcript_api
def fetch_transcript(video_id: str) -> str:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        formatted_transcript = " ".join([item['text'] for item in transcript])
        return formatted_transcript
    except Exception as e:
        st.error(f"Failed to fetch transcript: {e}")
        return None

# Function to save transcript to GitHub
def save_transcript_to_github(repo, title, video_id, transcript):
    try:
        file_path = f"{video_id}_transcription.txt"
        repo.create_file(
            path=file_path,
            message=f"Add transcription for {title}",
            content=transcript,
            branch="main"
        )
        st.success(f"Transcription saved to GitHub as {file_path}")
    except Exception as e:
        st.error(f"Failed to save transcription to GitHub: {e}")

# Function to generate quiz from transcript
def generate_quiz_from_transcript(transcript):
    def create_question(text):
        question_type = random.choice(["multiple_choice", "true_false"])
        if question_type == "multiple_choice":
            return {
                "type": "multiple_choice",
                "question": f"What is the correct answer based on the following content: {text}",
                "options": [
                    f"Correct answer from {text}",
                    "Incorrect answer 1",
                    "Incorrect answer 2",
                    "Incorrect answer 3"
                ],
                "answer": 0  # index of the correct answer
            }
        else:
            return {
                "type": "true_false",
                "question": f"True or False: {text}",
                "answer": random.choice([True, False])
            }

    sentences = transcript.split('.')
    questions = []
    for _ in range(5):
        sentence = random.choice(sentences).strip()
        if sentence:
            questions.append(create_question(sentence))

    return questions

# Streamlit app interface
st.header("YouTube Video Transcription and Quiz Generator")
topic = st.text_input("Enter a topic to search for videos:")

if st.button("Search Videos"):
    if topic:
        videos = search_videos(topic)
        if videos:
            st.session_state.videos = videos
        else:
            st.warning("No videos found for this topic. Please try a different topic or adjust the criteria.")
    else:
        st.warning("Please enter a topic to search for videos.")

if "videos" in st.session_state:
    for video in st.session_state.videos:
        st.write(f"**Title:** {video['title']}")
        st.write(f"[Watch Video]({video['url']})")
        if st.button(f"Generate Quiz for {video['title']}", key=video['id']):
            transcript = fetch_transcript(video['id'])
            if transcript:
                st.subheader("Transcript")
                st.write(transcript)
                
                save_transcript_to_github(repo, video['title'], video['id'], transcript)

                st.subheader("Quiz Questions")
                questions = generate_quiz_from_transcript(transcript)
                for question in questions:
                    st.write(question['question'])
                    if question['type'] == "multiple_choice":
                        for idx, option in enumerate(question['options']):
                            st.write(f"{idx + 1}. {option}")
                    else:
                        st.write("Answer: True/False")
        st.write("---")
