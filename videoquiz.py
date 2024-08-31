import streamlit as st
import pandas as pd
import openai

# Set your OpenAI API key
openai.api_key = st.secrets["openai"]["api_key"]

# Function to load the CSV from GitHub
@st.cache_data
def load_csv_from_github():
    url = "https://raw.githubusercontent.com/scooter7/VideoLMS/main/Transcripts/YouTube%20Transcripts%20-%20Sheet1.csv"
    df = pd.read_csv(url)
    return df

# Function to generate quiz questions using GPT-4o-mini
def generate_quiz_questions(transcript: str, num_questions: int = 5) -> list:
    prompt = f"""
    You are an expert quiz generator. Based on the following transcript, create {num_questions} quiz questions.
    Each question should be either a multiple-choice question (with 4 options) or a true/false question.
    Provide the correct answer for each question.

    Transcript:
    {transcript}
    """

    try:
        completions = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract the content from the completion response
        completion_content = completions.choices[0].message['content'].strip()

        questions = completion_content.split("\n\n")

        parsed_questions = []
        for q in questions:
            if "True or False" in q:
                parsed_questions.append({
                    "type": "true_false",
                    "question": q.split("\n")[0],
                    "options": ["True", "False"],
                    "answer": "True" if "True" in q else "False"
                })
            else:
                parts = q.split("\n")
                if len(parts) >= 5:  # Ensure there are enough parts to form a valid question
                    parsed_questions.append({
                        "type": "mcq",
                        "question": parts[0],
                        "options": parts[1:5],
                        "answer": parts[5].split(":")[1].strip("*").strip()  # Remove asterisks and whitespace
                    })

        return parsed_questions

    except Exception as e:
        st.error(f"Failed to generate quiz questions: {e}")
        return []

# Streamlit App
st.title("Transcript-based Quiz Generator")
st.markdown("Generate quizzes from transcripts in a CSV file hosted on GitHub.")

# Load the CSV file from GitHub
df = load_csv_from_github()

# Topic Selection
topic = st.selectbox("Select a Topic", df['Topic'].unique())

if topic:
    transcript = df[df['Topic'] == topic]['Transcript'].values[0]
    video_url = df[df['Topic'] == topic]['URL'].values[0]

    # Display the embedded video
    st.video(video_url)

    # "Watched Video" button to trigger quiz generation
    if st.button("I've watched this video"):
        with st.spinner("Generating quiz..."):
            quiz_questions = generate_quiz_questions(transcript)
            st.session_state.quiz_questions = quiz_questions
            st.success("Quiz generated!")

# Display the generated quiz questions interactively
if "quiz_questions" in st.session_state:
    st.subheader("Generated Quiz")

    score = 0
    for idx, question in enumerate(st.session_state.quiz_questions):
        st.write(f"**Question {idx+1}:** {question['question']}")
        user_answer = st.radio(f"Your answer for Question {idx+1}:", question["options"], key=f"q{idx}")

        if st.button(f"Submit Answer for Question {idx+1}", key=f"submit{idx}"):
            # Compare user answer with correct answer
            if user_answer.strip() == question["answer"].strip():
                st.success("Correct!")
                score += 1
            else:
                st.error(f"Incorrect. The correct answer was: {question['answer']}")

    st.write(f"Your total score: {score}/{len(st.session_state.quiz_questions)}")
