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
    You are an expert quiz generator. Based on the following transcript, create three multiple-choice quiz questions and two true/false questions.
    Each correct answer must be accurate, logically consistent, and clearly derived from the content of the transcript.
    All multiple choice questions should have exactly 4 options.
    
    Example of a valid multiple-choice question:
    Question: What is the capital of France?
    A) Paris
    B) London
    C) Berlin
    D) Madrid
    Answer: A) Paris
    Explanation: Paris is the capital of France.

    Example of a valid true/false question:
    Question: Paris is the capital of France.
    A) True
    B) False
    Answer: A) PTrue
    Explanation: Paris is the capital of France.

    Generate exactly five questions.

    Transcript:
    {transcript}
    """

    try:
        completions = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        if completions.choices and completions.choices[0].message.content:
            completion_content = completions.choices[0].message.content.strip()
            questions = completion_content.split("\n\n")

            parsed_questions = []
            for q in questions:
                lines = [line.strip() for line in q.split("\n") if line.strip()]
                if len(lines) >= 2:
                    question_text = lines[0]
                    options = [line for line in lines[1:] if line and not line.startswith("Answer:") and not line.startswith("Explanation:")]
                    answer = None
                    explanation = None

                    # Clean and format options
                    options = [option.replace("-", "").replace("*", "").strip() for option in options]

                    # Extract answer and explanation
                    for line in lines:
                        if line.startswith("Answer:"):
                            answer = line.split("Answer:")[1].strip()
                        if line.startswith("Explanation:"):
                            explanation = line.split("Explanation:")[1].strip()

                    if len(options) == 4:
                        parsed_questions.append({
                            "question": question_text,
                            "options": options,
                            "answer": answer,
                            "explanation": explanation
                        })

            # Ensure we have exactly 5 questions
            if len(parsed_questions) < num_questions:
                st.error("Failed to generate the required number of quiz questions. Please try again.")
                return []

            # Properly number the questions sequentially
            for i, question in enumerate(parsed_questions, 1):
                question["question"] = f"Question {i}: {question['question'].split(':')[-1].strip()}"

            return parsed_questions

        else:
            st.error("Failed to generate a valid response from the OpenAI API. The response might be incomplete or malformed.")
            return []

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

        # Initialize session state variables if they don't exist
        if f'quiz_submitted_{index}' not in st.session_state:
            st.session_state[f'quiz_submitted_{index}'] = False
        if f'quiz_scores_{index}' not in st.session_state:
            st.session_state[f'quiz_scores_{index}'] = 0
        if f'quiz_questions_{index}' not in st.session_state:
            st.session_state[f'quiz_questions_{index}'] = []
        if f'quiz_answers_{index}' not in st.session_state:
            st.session_state[f'quiz_answers_{index}'] = []

        # "Watched Video" button to trigger quiz generation
        if st.button(f"I've watched this video {index + 1}"):
            with st.spinner("Generating quiz..."):
                quiz_questions = generate_quiz_questions(transcript)
                st.session_state[f'quiz_questions_{index}'] = quiz_questions
                st.session_state[f'quiz_answers_{index}'] = [None] * len(quiz_questions)
                st.session_state[f'quiz_scores_{index}'] = 0  # Initialize score for this quiz
                if quiz_questions:
                    for idx, _ in enumerate(quiz_questions):
                        # Initialize submission tracking for each question
                        st.session_state[f'quiz_submitted_{index}_{idx}'] = False
                    st.success(f"Quiz generated for video {index + 1}!")
                else:
                    st.error(f"Failed to generate quiz for video {index + 1}.")

        # Display the generated quiz questions interactively
        if st.session_state[f'quiz_questions_{index}']:
            st.subheader(f"Quiz for Video {index + 1}")

            for idx, question in enumerate(st.session_state[f'quiz_questions_{index}']):
                st.write(f"**{question['question']}**")

                # Display radio buttons for multiple-choice or True/False questions
                if question["options"]:
                    user_answer = st.radio(f"Your answer for {question['question'].split(':')[0]}:", question["options"], key=f"q_{index}_{idx}")
                else:
                    st.warning("No options available for this question. Skipping...")
                    continue

                # Store the user's answer
                st.session_state[f'quiz_answers_{index}'][idx] = user_answer

                # Show the Submit Answer button for each question
                if not st.session_state[f'quiz_submitted_{index}_{idx}']:
                    if st.button(f"Submit Answer for {question['question'].split(':')[0]} - Video {index + 1}", key=f"submit_{index}_{idx}"):
                        # Check if the answer is None and handle appropriately
                        if question["answer"] is None:
                            st.warning("No correct answer available for this question. Skipping...")
                            continue
                        
                        # Normalize both answers for comparison
                        correct_answer_clean = question["answer"].strip().lower().replace(" ", "")
                        user_answer_clean = user_answer.strip().lower().replace(" ", "")

                        # Compare user answer with correct answer
                        if user_answer_clean == correct_answer_clean:
                            st.success("Correct!")
                            st.session_state[f'quiz_scores_{index}'] += 1  # Increment score for this video
                        else:
                            st.error(f"Incorrect. The correct answer was: {question['answer']}")

                        # Mark the quiz as submitted
                        st.session_state[f'quiz_submitted_{index}_{idx}'] = True

                        # Show explanation after the answer is submitted
                        if question.get('explanation'):
                            st.info(f"Explanation: {question['explanation']}")

            st.write(f"Your score for Video {index + 1}: {st.session_state[f'quiz_scores_{index}']}/{len(st.session_state[f'quiz_questions_{index}'])}")
            
            # Update the total score and total questions count
            total_score += st.session_state[f'quiz_scores_{index}']
            total_questions += len(st.session_state[f'quiz_questions_{index}'])

    # Display total score across all quizzes
    if total_questions > 0:
        st.write(f"**Your total score across all videos: {total_score}/{total_questions}**")
