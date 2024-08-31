import streamlit as st
import pandas as pd
import requests
import openai
from io import StringIO  # Import StringIO from io module

# Load secrets
openai_api_key = st.secrets["openai"]["api_key"]
github_token = st.secrets["github"]["token"]

# Function to load the CSV from GitHub
@st.cache_data
def load_csv_from_github():
    url = "https://raw.githubusercontent.com/scooter7/VideoLMS/main/Transcripts/YouTube%20Transcripts%20-%20Sheet1.csv"
    headers = {"Authorization": f"token {github_token}"}
    response = requests.get(url, headers=headers)
    return pd.read_csv(StringIO(response.text))  # Use StringIO to read the text response as a CSV

# Load the CSV file
df = load_csv_from_github()

# Topic Selection
topic = st.radio("Select a Topic", df['Topic'].unique())

# Display Video URLs
videos = df[df['Topic'] == topic]['Video URL']
for i, video in enumerate(videos):
    st.video(video)
    if st.button(f"I've watched this video {i+1}"):
        # Generate quiz
        transcript = df[df['Video URL'] == video]['Transcript'].values[0]
        quiz = generate_quiz(transcript)
        st.write(quiz)

# Function to generate quiz using GPT-4o-mini
def generate_quiz(transcript):
    openai.api_key = openai_api_key
    prompt = f"Create a quiz with 5 questions based on this transcript: {transcript}"
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}]
    )
    quiz = response.choices[0].message["content"]
    return quiz
