import streamlit as st
import pandas as pd
import requests
import json
import base64

openai.api_key = st.secrets["openai"]["api_key"]

# Constants
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
        return response.json()["sha"]
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
    if response.status_code == 200:
        st.success(f"Successfully updated {file_path} in the GitHub repository.")
    else:
        st.error(f"Failed to update {file_path} in the GitHub repository: {response.text}")

def load_users():
    url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{USER_DATA_FILE_PATH}"
    return pd.read_csv(url)

def load_scores():
    url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{SCORES_DATA_FILE_PATH}"
    return pd.read_csv(url)

def save_user(username, password):
    users = load_users()
    new_user = pd.DataFrame({"username": [username], "password": [password]})
    users = pd.concat([users, new_user], ignore_index=True)
    csv_content = users.to_csv(index=False)
    upload_file_to_github(USER_DATA_FILE_PATH, csv_content, "Add new user")

def save_score(username, video_id, score):
    scores = load_scores()
    new_score = pd.DataFrame({"username": [username], "video_id": [video_id], "score": [score]})
    scores = pd.concat([scores, new_score], ignore_index=True)
    csv_content = scores.to_csv(index=False)
    upload_file_to_github(SCORES_DATA_FILE_PATH, csv_content, "Add new score")

def authenticate(username, password):
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

# User Authentication
if "username" not in st.session_state:
    st.sidebar.title("Login / Register")

    choice = st.sidebar.selectbox("Choose an option", ["Login", "Register"])

    if choice == "Login":
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")

        if st.sidebar.button("Login"):
            if authenticate(username, password):
                st.session_state["username"] = username
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
        st.sidebar.success("Logged out successfully!")

# Admin Page
if "username" in st.session_state and st.session_state["username"] == "james@shmooze.io":
    st.sidebar.title("Admin Page")
    admin_password = st.sidebar.text_input("Admin Password", type="password")
    if admin_password == "Conversations7!":
        st.sidebar.success("Admin access granted!")
        users = load_users()
        scores = load_scores()

        st.write("### All Users")
        st.dataframe(users)

        st.write("### Quiz Scores")
        st.dataframe(scores)
    else:
        st.sidebar.error("Invalid admin password.")

# Main Content
if "username" in st.session_state:
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

                    # Display the explanation only after submission
                    if st.session_state[f'quiz_submitted_{index}_{idx}']:
                        if question.get('explanation'):
                            st.info(f"Explanation: {question['explanation']}")

                st.write(f"Your score for Video {index + 1}: {st.session_state[f'quiz_scores_{index}']}/{len(st.session_state[f'quiz_questions_{index}'])}")

                total_score += st.session_state[f'quiz_scores_{index}']
                total_questions += len(st.session_state[f'quiz_questions_{index}'])

                save_score(st.session_state['username'], video_url, st.session_state[f'quiz_scores_{index}'])

        if total_questions > 0:
            st.write(f"**Your total score across all videos: {total_score}/{total_questions}**")
