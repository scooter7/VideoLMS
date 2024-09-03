import streamlit as st
import pandas as pd
import requests
import json
import base64
import openai
import re

openai.api_key = st.secrets["openai"]["api_key"]

GITHUB_API_URL = "https://api.github.com"
REPO_OWNER = st.secrets["github"]["username"]
REPO_NAME = "VideoLMS"
USER_DATA_FILE_PATH = "UsersandScores/users.csv"
SCORES_DATA_FILE_PATH = "UsersandScores/scores.csv"
GITHUB_TOKEN = st.secrets["github"]["token"]

def get_file_sha(file_path):
    url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("sha", None)
    return None

def upload_file_to_github(file_path, content, message):
    url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }
    sha = get_file_sha(file_path)
    data = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "branch": "main"
    }
    if sha:
        data["sha"] = sha

    response = requests.put(url, headers=headers, data=json.dumps(data))
    if response.status_code in [200, 201]:
        st.success(f"Successfully updated {file_path} in the GitHub repository.")
    else:
        st.error(f"Failed to update {file_path} in the GitHub repository: {response.text}")

def load_users():
    url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{USER_DATA_FILE_PATH}"
    try:
        return pd.read_csv(url)
    except Exception as e:
        st.warning(f"Could not load users. Creating a new file: {e}")
        return pd.DataFrame(columns=["username", "password"])

def load_scores():
    url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{SCORES_DATA_FILE_PATH}"
    try:
        return pd.read_csv(url)
    except Exception as e:
        st.warning(f"Could not load scores. Creating a new file: {e}")
        return pd.DataFrame(columns=["username", "video_id", "score"])

def save_user(username, password):
    users = load_users()
    new_user = pd.DataFrame({"username": [username], "password": [password]})
    users = pd.concat([users, new_user], ignore_index=True)
    content = users.to_csv(index=False)
    upload_file_to_github(USER_DATA_FILE_PATH, content, "Add new user")

def save_score(username, video_id, score):
    scores = load_scores()
    new_score = pd.DataFrame({"username": [username], "video_id": [video_id], "score": [score]})
    scores = pd.concat([scores, new_score], ignore_index=True)
    content = scores.to_csv(index=False)
    upload_file_to_github(SCORES_DATA_FILE_PATH, content, "Add new score")

def authenticate(username, password):
    if username == "james@shmooze.io" and password == "Conversations7!":
        return True
    users = load_users()
    user = users[(users['username'] == username) & (users['password'] == password)]
    return not user.empty

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

def clean_answer(answer):
    answer = answer.replace("Answer:", "").strip()  # Remove 'Answer:' prefix if it exists
    return re.sub(r'[^a-zA-Z0-9]', '', answer).strip().lower()

def parse_questions_from_response(response_text):
    questions = []

    sections = response_text.split("\n\nTrue/False Questions:\n\n")

    if len(sections) == 2:
        mcq_section, tf_section = sections
    else:
        mcq_section = sections[0]
        tf_section = ""

    mcq_parts = mcq_section.split("\n\n")
    for part in mcq_parts:
        lines = part.split("\n")
        if len(lines) >= 7:  # Ensure there are enough lines for a question, 4 options, answer, and explanation
            question = {
                "question": lines[0].strip(),
                "options": [lines[1].strip(), lines[2].strip(), lines[3.strip(), lines[4].strip()],
                "answer": lines[5].strip(),
                "explanation": lines[6].strip()
            }
            questions.append(question)

    tf_parts = tf_section.split("\n\n")
    for part in tf_parts:
        lines = part.split("\n")
        if len(lines) >= 3:  # Ensure there are enough lines for a question, answer, and explanation
            question = {
                "question": lines[0].strip(),
                "options": ["True", "False"],
                "answer": lines[1].strip(),
                "explanation": lines[2].strip()
            }
            questions.append(question)

    if len(questions) > 5:
        questions = questions[:5]

    return questions

# The function you provided, integrated into the full code
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
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

        if completions.choices and completions.choices[0].message.content:
            response_text = completions.choices[0].message.content.strip()

            questions = parse_questions_from_response(response_text)

            return questions
    except Exception as e:
        st.error(f"Error generating quiz questions: {e}")
    return []

def generate_combined_quiz_questions(transcript: str) -> list:
    chunks = chunk_text(transcript)
    all_questions = []
    for chunk in chunks:
        questions = generate_quiz_questions_for_chunk(chunk)
        all_questions.extend(questions)
        if len(all_questions) >= 5:
            break  # Stop once we have 5 questions total
    return all_questions[:5]  # Ensure only 5 questions are returned

st.title("Video Quiz Generator")

if "username" not in st.session_state:
    st.sidebar.title("Login / Register")

    choice = st.sidebar.selectbox("Choose an option", ["Login", "Register"])

    if choice == "Login":
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")

        if st.sidebar.button("Login"):
            if authenticate(username, password):
                st.session_state["username"] = username
                st.session_state["is_admin"] = (username == "james@shmooze.io" and password == "Conversations7!")
                st.sidebar.success("Logged in successfully!")
            else:
                st.sidebar.error("Invalid credentials. Please try again.")

    elif choice == "Register":
        new_username = st.sidebar.text_input("Create a Username")
        new_password = st.sidebar.text_input("Create a Password", type="password")
        confirm_password = st.sidebar.text_input("Confirm Password", type="password")

        if st.sidebar.button("Register"):
            if new_password == confirm_password:
                save_user(new_username, new_password)
                st.sidebar.success("Registration successful! You can now log in.")
            else:
                st.sidebar.error("Passwords do not match. Please try again.")
else:
    st.sidebar.write(f"Welcome, {st.session_state['username']}!")
    if st.sidebar.button("Logout"):
        del st.session_state["username"]
        del st.session_state["is_admin"]
        st.sidebar.success("Logged out successfully!")
        st.experimental_rerun()

if "is_admin" in st.session_state and st.session_state["is_admin"]:
    st.sidebar.title("Admin Page")
    st.sidebar.success("Admin access granted!")
    users = load_users()
    scores = load_scores()

    st.write("### All Users")
    st.dataframe(users)

    st.write("### Quiz Scores")
    st.dataframe(scores)

if "username" in st.session_state:
    st.title("Transcript-based Quiz Generator")
    st.markdown("Generate quizzes from transcripts in a CSV file hosted on GitHub.")

    df = pd.read_csv("https://raw.githubusercontent.com/scooter7/VideoLMS/main/Transcripts/YouTube%20Transcripts%20-%20Sheet1.csv")

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
                st.subheader(f"Quiz for Video {index + 1}")

                for idx, question in enumerate(st.session_state[f'quiz_questions_{index}']):
                    st.write(f"**Question {total_questions + idx + 1}: {question['question'].split(':')[-1].strip()}**")

                    if question["options"]:
                        user_answer = st.radio(f"Your answer for Question {total_questions + idx + 1}:", question["options"], key=f"q_{index}_{idx}")
                    else:
                        st.warning("No options available for this question. Skipping...")
                        continue

                    if not st.session_state[f'quiz_submitted_{index}_{idx}']:
                        if st.button(f"Submit Answer for Question {total_questions + idx + 1} - Video {index + 1}", key=f"submit_{index}_{idx}"):
                            if question["answer"] is None:
                                st.warning("No correct answer available for this question. Skipping...")
                                continue

                            correct_answer_clean = clean_answer(question["answer"])
                            user_answer_clean = clean_answer(user_answer)

                            if user_answer_clean == correct_answer_clean:
                                st.success("Correct!")
                                st.session_state[f'quiz_scores_{index}'] += 1
                            else:
                                st.error(f"Incorrect. The correct answer was: {question['answer']}")

                            st.session_state[f'quiz_submitted_{index}_{idx}'] = True

                    if st.session_state[f'quiz_submitted_{index}_{idx}']:
                        if question.get('explanation'):
                            st.info(f"Explanation: {question['explanation']}")

                total_score += st.session_state[f'quiz_scores_{index}']
                total_questions += len(st.session_state[f'quiz_questions_{index}'])

                save_score(st.session_state['username'], video_url, st.session_state[f'quiz_scores_{index}'])

        if total_questions > 0:
            st.write(f"**Your total score across all videos: {total_score}/{total_questions}**")

    st.write("### Your Watched Videos and Scores")
    user_scores = load_scores()
    user_scores = user_scores[user_scores['username'] == st.session_state['username']]
    st.dataframe(user_scores)
