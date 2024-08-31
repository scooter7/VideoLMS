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
        completion_content = completions.choices[0].message.content.strip()

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
    # Filter the DataFrame for the selected topic
    filtered_df = df[df['Topic'] == topic]

    # Initialize score tracking
    total_score = 0
    total_questions = 0

    # Display all videos for the selected topic
    for index, row in filtered_df.iterrows():
        video_url = row['URL']
        transcript = row['Transcript']
        
        # Display the embedded video
        st.video(video_url)

        # "Watched Video" button to trigger quiz generation
        if st.button(f"I've watched this video {index + 1}"):
            with st.spinner("Generating quiz..."):
                quiz_questions = generate_quiz_questions(transcript)
                st.session_state[f'quiz_questions_{index}'] = quiz_questions
                st.success(f"Quiz generated for video {index + 1}!")

        # Display the generated quiz questions interactively
        if f'quiz_questions_{index}' in st.session_state:
            st.subheader(f"Quiz for Video {index + 1}")

            video_score = 0
            for idx, question in enumerate(st.session_state[f'quiz_questions_{index}']):
                st.write(f"**Question {idx + 1}:** {question['question']}")
                user_answer = st.radio(f"Your answer for Question {idx + 1}:", question["options"], key=f"q_{index}_{idx}")

                if st.button(f"Submit Answer for Question {idx + 1} - Video {index + 1}", key=f"submit_{index}_{idx}"):
                    # Clean and normalize both user answer and correct answer
                    correct_answer_clean = question["answer"].strip().lower()
                    user_answer_clean = user_answer.strip().lower()

                    # Compare user answer with correct answer
                    if user_answer_clean == correct_answer_clean:
                        st.success("Correct!")
                        video_score += 1
                    else:
                        st.error(f"Incorrect. The correct answer was: {question['answer']}")

            st.write(f"Your score for Video {index + 1}: {video_score}/{len(st.session_state[f'quiz_questions_{index}'])}")
            
            # Update the total score and total questions count
            total_score += video_score
            total_questions += len(st.session_state[f'quiz_questions_{index}'])

    # Display total score across all quizzes
    if total_questions > 0:
        st.write(f"**Your total score across all videos: {total_score}/{total_questions}**")
