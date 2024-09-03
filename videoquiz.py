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
    Ensure that each correct answer is accurate, logically consistent, and clearly derived from the content of the transcript.
    Also, explain briefly why the correct answer is correct.

    Transcript:
    {transcript}
    """

    try:
        completions = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract the content from the completion response
        if completions.choices and completions.choices[0].message.content:
            completion_content = completions.choices[0].message.content.strip()
            questions = completion_content.split("\n\n")

            parsed_questions = []
            for q in questions:
                lines = q.split("\n")
                if len(lines) >= 2:
                    question_text = lines[0].strip()
                    options = [line.strip() for line in lines[1:] if line.strip()]

                    # Handle True/False questions properly
                    if len(options) == 1 and ("True" in options[0] or "False" in options[0]):
                        options = ["True", "False"]
                        answer = "True" if "True" in options[0] else "False"
                    else:
                        # Extract the correct answer for multiple-choice questions
                        answer = None
                        if "Answer:" in options[-1]:
                            answer = options[-1].split("Answer:")[1].strip("*").strip()
                            options = options[:-1]

                    # Adding a brief explanation to verify consistency
                    explanation = ""
                    if "Explanation:" in options[-1]:
                        explanation = options[-1].split("Explanation:")[1].strip()

                    parsed_questions.append({
                        "question": question_text,
                        "options": options,
                        "answer": answer,
                        "explanation": explanation
                    })

            if not parsed_questions:
                st.error("No valid quiz questions could be generated. Please try again with a different video.")
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

        # "Watched Video" button to trigger quiz generation
        if st.button(f"I've watched this video {index + 1}"):
            with st.spinner("Generating quiz..."):
                quiz_questions = generate_quiz_questions(transcript)
                st.session_state[f'quiz_questions_{index}'] = quiz_questions
                st.session_state[f'quiz_answers_{index}'] = [None] * len(quiz_questions)
                st.session_state[f'quiz_scores_{index}'] = 0  # Initialize score for this quiz
                if quiz_questions:
                    st.success(f"Quiz generated for video {index + 1}!")
                else:
                    st.error(f"Failed to generate quiz for video {index + 1}.")

        # Display the generated quiz questions interactively
        if f'quiz_questions_{index}' in st.session_state:
            st.subheader(f"Quiz for Video {index + 1}")

            # Make sure score is initialized
            video_score = st.session_state.get(f'quiz_scores_{index}', 0)
            
            for idx, question in enumerate(st.session_state[f'quiz_questions_{index}']):
                st.write(f"**Question {idx + 1}:** {question['question']}")

                # Display radio buttons for multiple-choice or True/False questions
                if question["options"]:
                    user_answer = st.radio(f"Your answer for Question {idx + 1}:", question["options"], key=f"q_{index}_{idx}")
                else:
                    st.warning("No options available for this question. Skipping...")
                    continue

                # Store the user's answer
                st.session_state[f'quiz_answers_{index}'][idx] = user_answer

                if st.button(f"Submit Answer for Question {idx + 1} - Video {index + 1}", key=f"submit_{index}_{idx}"):
                    # Check if the answer is None and handle appropriately
                    if question["answer"] is None:
                        st.warning("No correct answer available for this question. Skipping...")
                        continue
                    
                    # Normalize both answers for comparison
                    correct_answer_clean = question["answer"].strip().lower().replace(" ", "")
                    user_answer_clean = user_answer.strip().lower().replace(" ", "")

                    # Ensure no extra characters like hyphens are present
                    user_answer_clean = user_answer_clean.lstrip('-')

                    # Compare user answer with correct answer
                    if user_answer_clean == correct_answer_clean:
                        st.success("Correct!")
                        video_score += 1  # Increment score for this video
                    else:
                        st.error(f"Incorrect. The correct answer was: {question['answer']}")

                # Update the score for this video in session state
                st.session_state[f'quiz_scores_{index}'] = video_score

            st.write(f"Your score for Video {index + 1}: {video_score}/{len(st.session_state[f'quiz_questions_{index}'])}")
            
            # Update the total score and total questions count
            total_score += st.session_state[f'quiz_scores_{index}']
            total_questions += len(st.session_state[f'quiz_questions_{index}'])

    # Display total score across all quizzes
    if total_questions > 0:
        st.write(f"**Your total score across all videos: {total_score}/{total_questions}**")
