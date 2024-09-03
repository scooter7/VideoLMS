import streamlit as st
import pandas as pd
import openai

openai.api_key = st.secrets["openai"]["api_key"]

@st.cache_data
def load_csv_from_github():
    url = "https://raw.githubusercontent.com/scooter7/VideoLMS/main/Transcripts/YouTube%20Transcripts%20-%20Sheet1.csv"
    df = pd.read_csv(url)
    return df

def chunk_text(text, max_chunk_size=3000):
    words = text.split()
    chunks = []
    current_chunk = []

    for word in words:
        if len(" ".join(current_chunk + [word])) <= max_chunk_size:
            current_chunk.append(word)
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

def generate_quiz_questions_for_chunk(chunk: str) -> list:
    prompt = f"""
    You are an expert quiz generator. Based on the following transcript, create three multiple-choice quiz questions and two true/false questions.
    Each correct answer must be accurate, logically consistent, and clearly derived from the content of the transcript.
    All multiple choice questions should have exactly 4 options and all true/false questions should only have two options (true and false).
    
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
    Answer: A) True
    Explanation: Paris is the capital of France.

    Generate exactly five questions.

    Transcript:
    {chunk}
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

                    options = [option.replace("-", "").replace("*", "").strip() for option in options]

                    for line in lines:
                        if line.startswith("Answer:"):
                            answer = line.split("Answer:")[1].strip()
                        if line.startswith("Explanation:"):
                            explanation = line.split("Explanation:")[1].strip()

                    if options and len(options) == 2:
                        parsed_questions.append({
                            "question": question_text,
                            "options": options,
                            "answer": answer,
                            "explanation": explanation
                        })
                    elif len(options) == 4:
                        parsed_questions.append({
                            "question": question_text,
                            "options": options,
                            "answer": answer,
                            "explanation": explanation
                        })

            return parsed_questions

        else:
            st.error("Failed to generate a valid response from the OpenAI API. The response might be incomplete or malformed.")
            return []

    except Exception as e:
        st.error(f"Failed to generate quiz questions: {e}")
        return []

def generate_combined_quiz_questions(transcript: str, num_questions: int = 5) -> list:
    chunks = chunk_text(transcript)
    all_questions = []

    for chunk in chunks:
        chunk_questions = generate_quiz_questions_for_chunk(chunk)
        all_questions.extend(chunk_questions)

    if len(all_questions) < num_questions:
        st.error("Failed to generate the required number of quiz questions. Please try again.")
        return []

    combined_questions = all_questions[:num_questions]

    for i, question in enumerate(combined_questions, 1):
        question["question"] = f"Question {i}: {question['question'].split(':')[-1].strip()}"

    return combined_questions

st.title("Transcript-based Quiz Generator")
st.markdown("Generate quizzes from transcripts in a CSV file hosted on GitHub.")

df = load_csv_from_github()

topic = st.selectbox("Select a Topic", df['Topic'].unique())

if topic:
    filtered_df = df[df['Topic'] == topic]

    total_score = 0
    total_questions = 0

    for index, row in filtered_df.iterrows():
        video_url = row['URL']
        transcript = row['Transcript']
        
        st.video(video_url)

        if f'quiz_submitted_{index}' not in st.session_state:
            st.session_state[f'quiz_submitted_{index}'] = False
        if f'quiz_scores_{index}' not in st.session_state:
            st.session_state[f'quiz_scores_{index}'] = 0
        if f'quiz_questions_{index}' not in st.session_state:
            st.session_state[f'quiz_questions_{index}'] = []
        if f'quiz_answers_{index}' not in st.session_state:
            st.session_state[f'quiz_answers_{index}'] = []

        if st.button(f"I've watched this video {index + 1}"):
            with st.spinner("Generating quiz..."):
                quiz_questions = generate_combined_quiz_questions(transcript)
                if quiz_questions:
                    st.session_state[f'quiz_questions_{index}'] = quiz_questions
                    st.session_state[f'quiz_answers_{index}'] = [None] * len(quiz_questions)
                    st.session_state[f'quiz_scores_{index}'] = 0
                    for idx, _ in enumerate(quiz_questions):
                        st.session_state[f'quiz_submitted_{index}_{idx}'] = False
                    st.success(f"Quiz generated for video {index + 1}!")
                else:
                    st.error(f"Failed to generate quiz for video {index + 1}.")

        if st.session_state.get(f'quiz_questions_{index}'):
            st.session_state['explanation_displayed'] = False
            st.subheader(f"Quiz for Video {index + 1}")

            for idx, question in enumerate(st.session_state[f'quiz_questions_{index}']):
                st.write(f"**{question['question']}**")

                if question["options"]:
                    user_answer = st.radio(f"Your answer for {question['question'].split(':')[0]}:", question["options"], key=f"q_{index}_{idx}")
                else:
                    st.warning("No options available for this question. Skipping...")
                    continue

                if not st.session_state[f'quiz_submitted_{index}_{idx}']:
                    if st.button(f"Submit Answer for {question['question'].split(':')[0]} - Video {index + 1}", key=f"submit_{index}_{idx}"):
                        if question["answer"] is None:
                            st.warning("No correct answer available for this question. Skipping...")
                            continue
                        
                        correct_answer_clean = question["answer"].strip().lower().replace(" ", "")
                        user_answer_clean = user_answer.strip().lower().replace(" ", "")

                        if user_answer_clean == correct_answer_clean:
                            st.success("Correct!")
                            st.session_state[f'quiz_scores_{index}'] += 1
                        else:
                            st.error(f"Incorrect. The correct answer was: {question['answer']}")

                        st.session_state[f'quiz_submitted_{index}_{idx}'] = True

                        if question.get('explanation'):
                            st.info(f"Explanation: {question['explanation']}")
                            st.session_state['explanation_displayed'] = True

                if st.session_state[f'quiz_submitted_{index}_{idx}'] and not st.session_state['explanation_displayed']:
                    st.info(f"Explanation: {question['explanation']}")
                    st.session_state['explanation_displayed'] = True

            st.write(f"Your score for Video {index + 1}: {st.session_state[f'quiz_scores_{index}']}/{len(st.session_state[f'quiz_questions_{index}'])}")

            total_score += st.session_state[f'quiz_scores_{index}']
            total_questions += len(st.session_state[f'quiz_questions_{index}'])

    if total_questions > 0:
        st.write(f"**Your total score across all videos: {total_score}/{total_questions}**")
