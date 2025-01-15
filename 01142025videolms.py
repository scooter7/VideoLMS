import streamlit as st
import pandas as pd
import requests
import openai
from googleapiclient.discovery import build

# API configurations
openai.api_key = st.secrets["openai"]["api_key"]
YOUTUBE_API_KEY = st.secrets["youtube"]["api_key"]

# State Initialization
if "selected_videos" not in st.session_state:
    st.session_state["selected_videos"] = []

if "quizzes" not in st.session_state:
    st.session_state["quizzes"] = {}

if "quiz_scores" not in st.session_state:
    st.session_state["quiz_scores"] = {}

# YouTube API Helper Functions
def search_youtube_videos(topic, max_results=10):
    """
    Search YouTube for videos based on a topic.
    Sorts results by views, likes, and comments.
    """
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

# Transcript Handling
def fetch_video_transcript(video_id):
    """
    Fetch video transcript using YouTube or other transcript services.
    Placeholder implementation provided.
    """
    # In production, replace this with an API call or scraping method.
    return f"This is a placeholder transcript for video {video_id}."

# Summarization
def summarize_transcript(transcript):
    """
    Summarize a video transcript using OpenAI.
    """
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

# Quiz Generation
def generate_quiz_from_summary(summary):
    """
    Generate a 5-question multiple-choice quiz from a summary.
    """
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
    """
    Parse OpenAI response text to extract questions, options, and correct answers.
    """
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
st.title("AI Video Quiz Generator")

topic = st.selectbox("Select a Topic", ["AI in Manufacturing", "AI in Healthcare", "AI in Insurance"])
if topic:
    # Fetch videos for the selected topic
    with st.spinner("Fetching videos..."):
        videos = search_youtube_videos(topic)
    
    st.write(f"### Videos for {topic}")
    video_selection = st.multiselect(
        "Select up to 5 videos to watch and quiz:",
        options=videos,
        format_func=lambda v: f"{v['title']} (Views: {v['views']}, Likes: {v['likes']}, Comments: {v['comments']})",
        key="video_selection"
    )

    if len(video_selection) > 5:
        st.error("You can only select up to 5 videos.")
    else:
        st.session_state["selected_videos"] = video_selection

    # Display selected videos
    if st.session_state["selected_videos"]:
        for video in st.session_state["selected_videos"]:
            st.video(video["url"])
            if st.button(f"I watched this! Quiz me! ({video['title']})", key=f"quiz_{video['id']}"):
                # Fetch transcript, summarize, and generate quiz
                transcript = fetch_video_transcript(video["id"])
                summary = summarize_transcript(transcript)
                quiz = generate_quiz_from_summary(summary)

                # Save quiz to session state
                st.session_state["quizzes"][video["id"]] = {
                    "title": video["title"],
                    "questions": quiz,
                    "answers": [None] * len(quiz),
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
                key=f"{video_id}_{i}"
            )
            quiz_data["answers"][i] = user_answer

        if st.button(f"Submit Quiz ({quiz_data['title']})", key=f"submit_{video_id}"):
            for i, correct_answer in enumerate(quiz_data["correct_answers"]):
                if quiz_data["answers"][i] == correct_answer:
                    total_correct += 1
                    st.success(f"Question {i + 1}: Correct!")
                else:
                    st.error(f"Question {i + 1}: Incorrect. Correct answer: {correct_answer}")
            st.write(f"Your Score: {total_correct} / {len(quiz_data['questions'])}")

            # Save the score
            st.session_state["quiz_scores"][video_id] = total_correct
