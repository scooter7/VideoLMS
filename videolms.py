import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from yt_dlp import YoutubeDL
import openai
from github import Github

# Set up Streamlit app
st.set_page_config(page_title="Video LMS", layout="wide")

# Set up API keys
openai.api_key = st.secrets["openai"]["api_key"]

# Initialize GitHub client
g = Github(st.secrets["github"]["token"])
repo = g.get_repo("scooter7/your-repo-name")

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

# Main app interface
st.title("Video LMS - Learning Management System")

# Video URL input
video_url = st.text_input("Enter the YouTube video URL:")

# Button to fetch video info and transcript
if st.button("Fetch Video Info and Transcript"):
    if not video_url:
        st.warning("Please enter a YouTube video URL.")
        st.stop()

    try:
        # Extract video ID from the URL
        video_id = re.search(r"(?<=v=)[^&#]+", video_url).group(0)
        title, description, thumbnail_url = get_video_info(video_url)
        st.write(f"**Title:** {title}")
        st.write(f"**Description:** {description}")
        if thumbnail_url:
            st.image(thumbnail_url)

        transcript = fetch_transcript(video_id)
        if transcript:
            st.write("### Transcript:")
            st.text_area("Transcript", transcript, height=300)

            # Save transcript to GitHub
            file_path = f"Transcriptions/{video_id}_transcription.txt"
            repo.create_file(
                path=file_path,
                message=f"Add transcription for {title}",
                content=transcript,
                branch="main"
            )
            st.success("Transcript saved to GitHub!")

            # Generate quiz questions
            st.write("### Generating quiz questions...")
            prompt = f"Based on the following content, create 10 quiz questions:\n\n{transcript}"
            completion = openai.Completion.create(
                model="text-davinci-003",
                prompt=prompt,
                max_tokens=150
            )
            quiz_questions = completion.choices[0].text.strip()
            st.write("### Quiz Questions:")
            st.write(quiz_questions)

    except Exception as e:
        st.error(f"Error processing the video: {e}")

# Display quiz interface if quizzes are generated
if "quiz_questions" in st.session_state:
    st.subheader("Take the Quiz")
    score = 0
    for i, question in enumerate(st.session_state["quiz_questions"]):
        answer = st.radio(f"Q{i+1}: {question['question']}", question["options"], key=f"quiz_{i}")
        if st.button(f"Submit Q{i+1}", key=f"submit_{i}"):
            if answer == question["correct_answer"]:
                score += 1
                st.success("Correct!")
            else:
                st.error("Incorrect.")
    st.write(f"Your final score: {score}/{len(st.session_state['quiz_questions'])}")
