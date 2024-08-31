import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from yt_dlp import YoutubeDL
from github import Github
import openai
import random

# Initialize GitHub client
g = Github(st.secrets["github"]["token"])
repo = g.get_repo("scooter7/VideoLMS")

# Function to fetch transcript using youtube_transcript_api
def fetch_transcript(video_id: str) -> str:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        formatter = TextFormatter()
        formatted_transcript = formatter.format_transcript(transcript)
        return formatted_transcript
    except Exception as e:
        if "No transcript found" in str(e):
            st.error("No transcript found for this video.")
        else:
            st.error(f"Failed to fetch transcript: {e}")
        return None

# Function to get video information using yt-dlp
def get_video_info(video_url: str) -> tuple:
    opts = {}
    with YoutubeDL(opts) as yt:
        info = yt.extract_info(video_url, download=False)
        title = info.get("title", "")
        description = info.get("description", "")
        thumbnails = info.get("thumbnails", [])
        thumbnail_url = thumbnails[-1]["url"] if thumbnails else None
        return title, description, thumbnail_url

# Function to save the transcript to GitHub
def save_transcript_to_github(repo, video_title, video_id, transcript_text):
    file_path = f"Transcripts/{video_title.replace(' ', '_')}_{video_id}_transcription.txt"
    try:
        existing_file = None
        try:
            existing_file = repo.get_contents(file_path)
        except:
            pass  # File doesn't exist

        if existing_file:
            # Update the existing file
            repo.update_file(
                file_path,
                f"Update transcription for {video_title}",
                transcript_text,
                sha=existing_file.sha
            )
        else:
            # Create a new file
            repo.create_file(
                file_path,
                f"Add transcription for {video_title}",
                transcript_text
            )
        st.success(f"Transcription saved to GitHub at {file_path}")
    except Exception as e:
        st.error(f"Failed to save transcription to GitHub: {e}")

# Function to search for videos based on a topic using yt-dlp
def search_videos(topic: str):
    opts = {
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch5',  # Search for top 5 results
    }
    with YoutubeDL(opts) as yt:
        results = yt.extract_info(f"ytsearch5:{topic}", download=False)['entries']
        videos = []
        for entry in results:
            if entry['duration'] <= 1200 and entry.get('subtitles'):
                videos.append({
                    'title': entry['title'],
                    'url': entry['webpage_url'],
                    'duration': entry['duration'],
                    'video_id': entry['id']
                })
        return videos

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
topic = st.text_input("Enter Topic to Search Videos:")

if st.button("Find Videos"):
    if topic:
        videos = search_videos(topic)
        if videos:
            st.session_state['videos'] = videos
            for idx, video in enumerate(videos):
                st.write(f"**{idx + 1}. {video['title']}** - {video['duration']//60} minutes")
                st.video(video['url'])
        else:
            st.warning("No videos found with transcripts available. Please try a different topic or adjust the criteria.")
    else:
        st.warning("Please enter a topic to search.")

# If videos are found and selected
if 'videos' in st.session_state:
    selected_video_idx = st.selectbox("Select a video to proceed:", range(len(st.session_state['videos'])), format_func=lambda x: st.session_state['videos'][x]['title'])
    
    if st.button("Fetch Video Info"):
        selected_video = st.session_state['videos'][selected_video_idx]
        video_id = selected_video['video_id']
        title, description, thumbnail_url = get_video_info(selected_video['url'])
        
        st.write(f"**Title:** {title}")
        st.write(f"**Description:** {description}")
        if thumbnail_url:
            st.image(thumbnail_url)

        transcript = fetch_transcript(video_id)
        if transcript:
            st.subheader("Transcript")
            st.write(transcript)
            
            save_transcript_to_github(repo, title, video_id, transcript)

            st.subheader("Generate Quiz")
            if st.button("Generate Quiz"):
                questions = generate_quiz_from_transcript(transcript)
                if questions:
                    st.subheader("Quiz Questions")
                    for question in questions:
                        st.write(question['question'])
                        if question['type'] == "multiple_choice":
                            for idx, option in enumerate(question['options']):
                                st.write(f"{idx + 1}. {option}")
                        else:
                            st.write("Answer: True/False")

