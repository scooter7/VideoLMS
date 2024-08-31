import streamlit as st
import pandas as pd
import requests
import openai
from io import StringIO

# Load secrets
openai_api_key = st.secrets["openai"]["api_key"]
github_token = st.secrets["github"]["token"]

# Initialize the OpenAI client
client = openai

# Function to generate a quiz using GPT-4o-mini
def generate_quiz(transcript):
    client.api_key = openai_api_key
    prompt = (
        f"Based on the following transcript, please generate a quiz with 5 questions. "
        f"The quiz should include a mix of multiple-choice and true/false questions. "
        f"Each question should have options, and indicate the correct answer:\n\n{transcript}"
    )
    
    completions = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    
    quiz_text = completions.choices[0].message.content
    st.write("Raw GPT-4o-mini Response:")  # Debugging step
    st.write(quiz_text)  # Output the raw text to help diagnose
    
    return quiz_text

# Function to parse the quiz text into a structured format
def parse_quiz(quiz_text):
    questions = []
    current_question = None
    lines = quiz_text.split("\n")
    
    for line in lines:
        line = line.strip()
        if line.lower().startswith("question"):
            if current_question:
                questions.append(current_question)
            current_question = {"question": line, "options": [], "correct": None}
        elif line.lower().startswith(("a)", "b)", "c)", "d)")):
            if current_question:
                current_question["options"].append(line)
        elif "correct answer:" in line.lower():
            if current_question:
                current_question["correct"] = line.split("Correct Answer: ")[1].strip()
    
    if current_question and current_question["options"]:  # Ensure last question is appended
        questions.append(current_question)
    
    return questions

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
videos = df[df['Topic'] == topic]['URL']
for i, video in enumerate(videos):
    st.video(video)
    if st.button(f"I've watched this video {i+1}"):
        # Generate quiz
        transcript = df[df['URL'] == video]['Transcript'].values[0]
        quiz_text = generate_quiz(transcript)
        questions = parse_quiz(quiz_text)
        
        # Display the quiz interactively
        if questions:
            st.write("Quiz Generated from the Transcript:")
            user_answers = {}
            for idx, q in enumerate(questions):
                st.write(q["question"])
                user_answers[idx] = st.radio(f"Question {idx+1}", q["options"], key=f"q{idx}")
            
            if st.button("Submit Quiz"):
                score = 0
                for idx, q in enumerate(questions):
                    correct_answer = q["correct"]
                    if user_answers[idx].endswith(correct_answer):
                        st.success(f"Question {idx+1}: Correct!")
                        score += 1
                    else:
                        st.error(f"Question {idx+1}: Incorrect. The correct answer is {correct_answer}.")
                st.write(f"Your total score: {score}/{len(questions)}")
        else:
            st.write("No quiz could be generated from the transcript.")
