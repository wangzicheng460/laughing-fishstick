#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnostics Learning System - Streamlit App
医学诊断学/听诊学习系统
"""

import streamlit as st
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse

# ===== Path Config =====
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
EXAM_DATA_FILE = os.path.join(DATA_DIR, "exam_data.json")
TINGZHEN_DATA_FILE = os.path.join(DATA_DIR, "tingzhen_data.json")
API_KEY_FILE = os.path.join(DATA_DIR, "api_key.txt")

# ===== AI Backend Config =====
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DOUBAO_MODEL = "doubao-1-5-pro-32k-250515"
DOUBAO_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
OLLAMA_MODEL = "qwen2.5"
OLLAMA_URL = "http://localhost:11434/api/generate"

# ===== Page Config =====
st.set_page_config(
    page_title="Medical Diagnostics Learning",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== Custom CSS =====
st.markdown("""
<style>
    .exam-card {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 12px;
        transition: box-shadow 0.2s;
    }
    .exam-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    }
    .correct-answer {
        background-color: #e8f5e9;
        border-left: 4px solid #4caf50;
        padding: 10px 16px;
        border-radius: 4px;
    }
    .wrong-answer {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
        padding: 10px 16px;
        border-radius: 4px;
    }
    .question-nav select {
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)


# ===== Data Loading =====
@st.cache_data
def load_exam_data():
    """Load diagnostics exam data."""
    with open(EXAM_DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


@st.cache_data
def load_tingzhen_data():
    """Load auscultation exam data."""
    with open(TINGZHEN_DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


# ===== AI Backend Functions (reused from ai_server.py) =====
def load_api_key():
    """Load API key from session state or file."""
    if st.session_state.get('api_key'):
        return st.session_state.api_key
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    st.session_state.api_key = line
                    return line
    return ""


def build_prompt(question, options_list, answer, user_answer=None):
    """Build the explanation prompt for AI."""
    opts = "\n".join(options_list)
    parts = [
        "You are a medical diagnostics exam tutor. Please explain the following question in detail.",
        "Requirements:",
        "1. Analyze each option one by one, explaining why it's correct or incorrect",
        "2. Point out the core knowledge point being tested",
        "3. Provide easy-to-remember memory tips or problem-solving techniques",
        "4. Use English for your response, be professional but easy to understand",
        "",
        f"[Question] {question}",
        "",
        "[Options]",
        opts,
        "",
        f"[Correct Answer] {answer}",
    ]
    if user_answer:
        parts.append(f"[User's Answer] {user_answer}")
        parts.append("Please identify why the user got it wrong (or right), and how to avoid similar mistakes.")
    parts.append("")
    parts.append("Please provide your explanation:")
    return "\n".join(parts)


def call_deepseek(prompt, api_key):
    """Call DeepSeek API."""
    data = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "You are a medical diagnostics exam expert, skilled at explaining medical multiple-choice questions."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2000
    }).encode("utf-8")

    req = urllib.request.Request(
        DEEPSEEK_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read().decode("utf-8"))
    return result["choices"][0]["message"]["content"].strip()


def call_doubao(prompt, api_key):
    """Call Doubao (Volcengine) API."""
    data = json.dumps({
        "model": DOUBAO_MODEL,
        "messages": [
            {"role": "system", "content": "You are a medical diagnostics exam expert, skilled at explaining medical multiple-choice questions."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2000
    }).encode("utf-8")

    req = urllib.request.Request(
        DOUBAO_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read().decode("utf-8"))
    return result["choices"][0]["message"]["content"].strip()


def call_ollama(prompt):
    """Call local Ollama model."""
    data = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3}
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read().decode("utf-8"))
    return result.get("response", "").strip()


def call_ai(prompt, api_key, backend):
    """Call the configured AI backend."""
    if backend == "ollama":
        return call_ollama(prompt)
    elif backend == "doubao":
        return call_doubao(prompt, api_key)
    else:
        return call_deepseek(prompt, api_key)


# ===== Session State Initialization =====
def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        'user_answers': {},       # {exam_type: {exam_id: {q_id_str: "A" or "ABC"}}}
        'checked': {},            # {exam_type: {exam_id: {q_id_str: True/False}}}
        'explanations': {},       # {exam_type: {exam_id: {q_id_str: "explanation text"}}}
        'current_page': 'home',   # 'home' | 'exam' | 'wrong' | 'settings'
        'current_exam': None,     # exam_id string (e.g. "1")
        'current_q_idx': 0,       # int index into the question list
        'show_answers': False,    # toggle to reveal correct answers
        'wrong_only': False,      # filter: show only wrong questions
        'ai_backend': 'deepseek', # 'deepseek' | 'doubao' | 'ollama'
        'api_key': '',            # API key string
        'exam_type': 'diagnostics',  # 'diagnostics' | 'auscultation'
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ===== Helper Functions =====
def get_exam_data():
    """Get the appropriate data based on exam_type."""
    if st.session_state.exam_type == 'auscultation':
        return load_tingzhen_data()
    return load_exam_data()


def get_question_list(data, exam_id, wrong_only=False):
    """Get filtered question list for an exam."""
    questions = data['questions'][exam_id]
    if not wrong_only:
        return questions

    exam_type = st.session_state.exam_type
    answers_data = data['answers'][exam_id]
    wrong_qs = []
    for q in questions:
        qid_str = str(q['id'])
        user_ans = st.session_state.user_answers.get(exam_type, {}).get(exam_id, {}).get(qid_str, '')
        correct_ans = answers_data.get(qid_str, '')
        if user_ans != correct_ans:
            wrong_qs.append(q)
    return wrong_qs


def sort_answer(answer_str):
    """Sort multi-choice answer string alphabetically (e.g. 'BCA' -> 'ABC')."""
    return ''.join(sorted(answer_str))


def get_stats(data):
    """Calculate overall statistics."""
    exam_type = st.session_state.exam_type
    total = 0
    done = 0
    correct = 0
    wrong = 0

    for exam_id in data['questions']:
        questions = data['questions'][exam_id]
        answers_data = data['answers'][exam_id]
        for q in questions:
            total += 1
            qid_str = str(q['id'])
            is_checked = st.session_state.checked.get(exam_type, {}).get(exam_id, {}).get(qid_str, False)
            if is_checked:
                done += 1
                user_ans = st.session_state.user_answers.get(exam_type, {}).get(exam_id, {}).get(qid_str, '')
                correct_ans = answers_data.get(qid_str, '')
                if sort_answer(user_ans) == sort_answer(correct_ans):
                    correct += 1
                else:
                    wrong += 1

    accuracy = f"{correct / done * 100:.1f}%" if done > 0 else "-"
    return total, done, correct, wrong, accuracy


def get_exam_stats(data, exam_id):
    """Calculate statistics for a specific exam."""
    exam_type = st.session_state.exam_type
    questions = data['questions'][exam_id]
    answers_data = data['answers'][exam_id]
    total = len(questions)
    done = 0
    correct = 0

    for q in questions:
        qid_str = str(q['id'])
        is_checked = st.session_state.checked.get(exam_type, {}).get(exam_id, {}).get(qid_str, False)
        if is_checked:
            done += 1
            user_ans = st.session_state.user_answers.get(exam_type, {}).get(exam_id, {}).get(qid_str, '')
            correct_ans = answers_data.get(qid_str, '')
            if sort_answer(user_ans) == sort_answer(correct_ans):
                correct += 1

    wrong = done - correct
    accuracy = f"{correct / done * 100:.1f}%" if done > 0 else "-"
    status = "Not Started"
    if done > 0:
        status = "Completed" if done == total else "In Progress"
    return total, done, correct, wrong, accuracy, status


# ===== Page: Home =====
def render_home():
    st.title("🩺 Medical Diagnostics Learning System")
    st.caption("A comprehensive learning platform for clinical diagnostics and auscultation")
    st.divider()

    # Overall statistics
    exam_data = load_exam_data()
    tz_data = load_tingzhen_data()

    # Diagnostics stats
    st.session_state.exam_type = 'diagnostics'
    d_total, d_done, d_correct, d_wrong, d_acc = get_stats(exam_data)
    # Auscultation stats
    st.session_state.exam_type = 'auscultation'
    t_total, t_done, t_correct, t_wrong, t_acc = get_stats(tz_data)

    st.subheader("📊 Overall Progress")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Questions", d_total + t_total)
    with col2:
        st.metric("Answered", d_done + t_done)
    with col3:
        st.metric("Correct", d_correct + t_correct)
    with col4:
        st.metric("Wrong", d_wrong + t_wrong)
    with col5:
        overall_acc = f"{(d_correct + t_correct) / (d_done + t_done) * 100:.1f}%" if (d_done + t_done) > 0 else "-"
        st.metric("Accuracy", overall_acc)

    st.divider()

    # Diagnostics exam cards
    st.subheader("📝 Diagnostics Exams")
    st.session_state.exam_type = 'diagnostics'
    _render_exam_cards(exam_data)

    st.divider()

    # Auscultation card
    st.subheader("🩺 Auscultation Training")
    st.session_state.exam_type = 'auscultation'
    _render_exam_cards(tz_data)

    st.divider()

    # Wrong answers shortcut
    has_wrong = (d_wrong + t_wrong) > 0
    if has_wrong:
        st.markdown("### ❌ Wrong Answers Review")
        col_a, col_b = st.columns([1, 4])
        with col_a:
            if st.button("📝 Review Diagnostics Wrong", use_container_width=True):
                st.session_state.exam_type = 'diagnostics'
                st.session_state.current_page = 'wrong'
                st.rerun()
            if st.button("🩺 Review Auscultation Wrong", use_container_width=True):
                st.session_state.exam_type = 'auscultation'
                st.session_state.current_page = 'wrong'
                st.rerun()


def _render_exam_cards(data):
    """Render exam cards in a grid."""
    exam_names = data.get('examNames', [f"Exam {k}" for k in data['questions']])
    exam_ids = list(data['questions'].keys())

    cols_per_row = 4
    for row_start in range(0, len(exam_ids), cols_per_row):
        cols = st.columns(cols_per_row)
        for i, exam_id in enumerate(exam_ids[row_start:row_start + cols_per_row]):
            with cols[i]:
                total, done, correct, wrong, accuracy, status = get_exam_stats(data, exam_id)
                name = exam_names[int(exam_id) - 1] if int(exam_id) <= len(exam_names) else f"Exam {exam_id}"

                # Status badge
                status_color = {"Not Started": "gray", "In Progress": "orange", "Completed": "green"}
                status_emoji = {"Not Started": "⚪", "In Progress": "🟡", "Completed": "🟢"}

                with st.container(border=True):
                    st.markdown(f"**{name}**")
                    st.caption(f"{status_emoji.get(status, '⚪')} {status}")
                    if done > 0:
                        st.progress(done / total, text=f"{correct}/{done}/{total}")
                        st.caption(f"Accuracy: {accuracy}")
                    else:
                        st.progress(0, text=f"0/{total}")
                        st.caption("Accuracy: -")
                    if st.button(f"Start / Continue", key=f"exam_btn_{st.session_state.exam_type}_{exam_id}", use_container_width=True):
                        st.session_state.current_exam = exam_id
                        st.session_state.current_q_idx = 0
                        st.session_state.current_page = 'exam'
                        st.session_state.wrong_only = False
                        st.session_state.show_answers = False
                        st.rerun()


# ===== Page: Exam =====
def render_exam():
    data = get_exam_data()
    exam_id = st.session_state.current_exam
    exam_type = st.session_state.exam_type
    questions = get_question_list(data, exam_id, st.session_state.wrong_only)
    total, done, correct, wrong, accuracy, status = get_exam_stats(data, exam_id)

    exam_names = data.get('examNames', [f"Exam {k}" for k in data['questions']])
    exam_name = exam_names[int(exam_id) - 1] if int(exam_id) <= len(exam_names) else f"Exam {exam_id}"

    # --- Top Toolbar ---
    st.subheader(f"{exam_name}")
    col1, col2, col3, col4, col5 = st.columns([1, 2, 1, 1, 1])
    with col1:
        if st.button("← Home", key="back_home", use_container_width=True):
            st.session_state.current_page = 'home'
            st.rerun()
    with col2:
        st.progress(done / total if total > 0 else 0, text=f"Progress: {correct}/{done}/{total} | Accuracy: {accuracy}")
    with col3:
        new_wrong = st.toggle("❌ Wrong Only", value=st.session_state.wrong_only, key="wrong_toggle")
        if new_wrong != st.session_state.wrong_only:
            st.session_state.wrong_only = new_wrong
            st.session_state.current_q_idx = 0
            st.rerun()
    with col4:
        new_show = st.toggle("👁 Show Answer", value=st.session_state.show_answers, key="show_ans_toggle")
        if new_show != st.session_state.show_answers:
            st.session_state.show_answers = new_show
            st.rerun()
    with col5:
        if st.button("🔄 Reset", key="reset_exam", use_container_width=True, type="secondary"):
            _reset_exam(exam_id)
            st.rerun()

    if not questions:
        st.info("No questions to display. All questions answered correctly! 🎉" if st.session_state.wrong_only else "No questions available.")
        return

    # Clamp index
    if st.session_state.current_q_idx >= len(questions):
        st.session_state.current_q_idx = len(questions) - 1
    if st.session_state.current_q_idx < 0:
        st.session_state.current_q_idx = 0

    q = questions[st.session_state.current_q_idx]
    qid_str = str(q['id'])
    q_type = q.get('type', 'single')
    options = q['options']
    correct_answer = sort_answer(data['answers'][exam_id].get(qid_str, ''))

    # Check submission status
    is_checked = st.session_state.checked.get(exam_type, {}).get(exam_id, {}).get(qid_str, False)
    user_answer = st.session_state.user_answers.get(exam_type, {}).get(exam_id, {}).get(qid_str, '')

    st.divider()

    # --- Question Display ---
    type_badge = "🔹 Single Choice" if q_type == 'single' else "🔸 Multiple Choice"
    st.markdown(f"**Q{q['id']}**  `{type_badge}`")
    st.markdown(f"**{q['question']}**")

    # Auscultation audio hint
    if exam_type == 'auscultation':
        st.info("🎧 This is an auscultation question. Please judge based on auscultation audio or clinical description.")

    st.markdown("")

    # --- Options ---
    option_letters = [opt[0] for opt in options]
    option_texts = [f"{opt[0]}. {opt[1]}" for opt in options]

    if q_type == 'single':
        _render_single_choice(option_letters, option_texts, user_answer, correct_answer, is_checked, exam_id, qid_str)
    else:
        _render_multi_choice(option_letters, option_texts, user_answer, correct_answer, is_checked, exam_id, qid_str)

    # --- Show answer toggle (display correct answer) ---
    if st.session_state.show_answers and not is_checked:
        st.info(f"💡 Correct Answer: **{correct_answer}**")

    # --- Feedback after submission ---
    if is_checked:
        user_sorted = sort_answer(user_answer)
        correct_sorted = sort_answer(correct_answer)
        if user_sorted == correct_sorted:
            st.success(f"✅ Correct! Answer: **{correct_answer}**")
        else:
            st.error(f"❌ Incorrect!")
            st.markdown(f"Your answer: **{user_answer or '(none)'}**  →  Correct answer: **{correct_answer}**")

    st.markdown("")

    # --- Action Buttons ---
    col_a, col_b, col_c = st.columns([1, 1, 4])
    with col_a:
        if not is_checked:
            if st.button("✅ Submit", key=f"submit_{exam_id}_{qid_str}", type="primary", use_container_width=True):
                # Save current answer to session state
                _save_answer(exam_id, qid_str, exam_type)
                # Mark as checked
                if exam_type not in st.session_state.checked:
                    st.session_state.checked[exam_type] = {}
                if exam_id not in st.session_state.checked[exam_type]:
                    st.session_state.checked[exam_type][exam_id] = {}
                st.session_state.checked[exam_type][exam_id][qid_str] = True
                st.rerun()
    with col_b:
        if st.button("🔍 Search Web", key=f"search_{exam_id}_{qid_str}", use_container_width=True):
            search_url = f"https://www.baidu.com/s?wd={urllib.parse.quote(q['question'])}"
            st.markdown(f"[Open Baidu Search]({search_url})", unsafe_allow_html=True)

    # --- AI Explanation ---
    if is_checked:
        _render_ai_explanation(q, options, correct_answer, user_answer, exam_id, qid_str)

    st.divider()

    # --- Question Navigation Dropdown ---
    nav_options = []
    for idx, qq in enumerate(questions):
        qid_s = str(qq['id'])
        ichk = st.session_state.checked.get(exam_type, {}).get(exam_id, {}).get(qid_s, False)
        ua = st.session_state.user_answers.get(exam_type, {}).get(exam_id, {}).get(qid_s, '')
        ca = sort_answer(data['answers'][exam_id].get(qid_s, ''))
        if ichk:
            marker = "✅" if sort_answer(ua) == ca else "❌"
        else:
            marker = "○"
        nav_options.append(f"{marker} Q{qq['id']}")

    selected_nav = st.selectbox(
        "Jump to question:",
        options=range(len(questions)),
        format_func=lambda i: nav_options[i],
        index=st.session_state.current_q_idx,
        key=f"nav_select_{exam_id}",
        label_visibility="collapsed"
    )
    if selected_nav != st.session_state.current_q_idx:
        st.session_state.current_q_idx = selected_nav
        st.rerun()

    # --- Prev / Next Navigation ---
    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.button("← Previous", key="prev_btn", use_container_width=True,
                     disabled=st.session_state.current_q_idx == 0):
            st.session_state.current_q_idx = max(0, st.session_state.current_q_idx - 1)
            st.rerun()
    with col_next:
        if st.button("Next →", key="next_btn", use_container_width=True,
                     disabled=st.session_state.current_q_idx >= len(questions) - 1):
            st.session_state.current_q_idx = min(len(questions) - 1, st.session_state.current_q_idx + 1)
            st.rerun()


def _save_answer(exam_id, qid_str, exam_type):
    """Save the current answer from widget state to session_state."""
    # Answer is already saved in real-time via _on_selection_change-like pattern
    # For single choice: saved as letter key
    # For multi choice: saved as sorted concatenated letters
    pass  # Answer saving is handled inline in the option rendering


def _reset_exam(exam_id):
    """Reset all answers and checks for a specific exam."""
    exam_type = st.session_state.exam_type
    for container in [st.session_state.user_answers, st.session_state.checked, st.session_state.explanations]:
        if exam_type in container and exam_id in container[exam_type]:
            container[exam_type][exam_id] = {}
    st.session_state.current_q_idx = 0
    st.session_state.wrong_only = False


def _render_single_choice(option_letters, option_texts, user_answer, correct_answer, is_checked, exam_id, qid_str):
    """Render single choice options with color feedback."""
    exam_type = st.session_state.exam_type

    # Determine which option to pre-select
    try:
        idx_default = option_letters.index(user_answer) if user_answer else None
    except ValueError:
        idx_default = None

    # Use a unique key for each question
    radio_key = f"radio_{exam_type}_{exam_id}_{qid_str}"

    # For checked questions, display with colors (not interactive radio)
    if is_checked:
        for i, (letter, text) in enumerate(zip(option_letters, option_texts)):
            is_correct = letter == correct_answer
            is_user_selected = letter == user_answer
            if is_correct:
                st.success(f"**{text}**  ✅ Correct Answer")
            elif is_user_selected and not is_correct:
                st.error(f"**{text}**  ❌ Your Answer")
            else:
                st.markdown(f"*{text}*")
    else:
        selected = st.radio(
            "Choose your answer:",
            options=option_letters,
            format_func=lambda x: option_texts[option_letters.index(x)],
            index=idx_default,
            key=radio_key,
            label_visibility="visible"
        )
        # Save selection to session state in real-time
        if selected:
            _persist_answer(exam_id, qid_str, selected)


def _render_multi_choice(option_letters, option_texts, user_answer, correct_answer, is_checked, exam_id, qid_str):
    """Render multi-choice options with checkboxes and color feedback."""
    exam_type = st.session_state.exam_type

    if is_checked:
        # Display results with colors
        for i, (letter, text) in enumerate(zip(option_letters, option_texts)):
            is_correct_option = letter in correct_answer
            is_user_chose = letter in (user_answer or '')
            is_missed = is_correct_option and not is_user_chose

            if is_user_chose and is_correct_option:
                st.success(f"**{text}**  ✅ Correct")
            elif is_user_chose and not is_correct_option:
                st.error(f"**{text}**  ❌ Incorrect choice")
            elif is_missed:
                st.warning(f"**{text}**  ⚠️ Missed (correct answer)")
            else:
                st.markdown(f"*{text}*")
    else:
        st.caption("Select all that apply:")
        selected_letters = []
        for i, (letter, text) in enumerate(zip(option_letters, option_texts)):
            is_checked_cb = letter in (user_answer or '')
            cb_key = f"cb_{exam_type}_{exam_id}_{qid_str}_{letter}"
            if st.checkbox(text, value=is_checked_cb, key=cb_key):
                selected_letters.append(letter)

        # Save sorted selection
        if selected_letters:
            _persist_answer(exam_id, qid_str, sort_answer(''.join(selected_letters)))
        else:
            _persist_answer(exam_id, qid_str, '')


def _persist_answer(exam_id, qid_str, answer_val):
    """Persist user answer to session_state."""
    exam_type = st.session_state.exam_type
    if exam_type not in st.session_state.user_answers:
        st.session_state.user_answers[exam_type] = {}
    if exam_id not in st.session_state.user_answers[exam_type]:
        st.session_state.user_answers[exam_type][exam_id] = {}
    st.session_state.user_answers[exam_type][exam_id][qid_str] = answer_val


def _render_ai_explanation(q, options, correct_answer, user_answer, exam_id, qid_str):
    """Render AI explanation expander."""
    exam_type = st.session_state.exam_type

    with st.expander("🤖 AI Explanation", expanded=False):
        # Check cache
        cached = st.session_state.explanations.get(exam_type, {}).get(exam_id, {}).get(qid_str, '')
        if cached:
            st.markdown(cached)
            return

        # Build option list for prompt
        option_list = [f"{opt[0]}. {opt[1]}" for opt in options]

        # Get API key
        api_key = load_api_key()
        backend = st.session_state.get('ai_backend', 'deepseek')

        if not api_key and backend != 'ollama':
            st.warning(
                "⚠️ API key not configured. Please go to **Settings** to configure your API key.\n\n"
                "You can get a free key from:\n"
                "- [DeepSeek](https://platform.deepseek.com/api_keys) (500M free tokens)\n"
                "- [Volcengine (Doubao)](https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint)"
            )
            return

        if st.button("🚀 Generate AI Explanation", key=f"ai_btn_{exam_type}_{exam_id}_{qid_str}", type="primary"):
            with st.spinner("AI is analyzing this question... Please wait..."):
                try:
                    prompt = build_prompt(q['question'], option_list, correct_answer, user_answer)
                    explanation = call_ai(prompt, api_key, backend)

                    # Cache
                    if exam_type not in st.session_state.explanations:
                        st.session_state.explanations[exam_type] = {}
                    if exam_id not in st.session_state.explanations[exam_type]:
                        st.session_state.explanations[exam_type][exam_id] = {}
                    st.session_state.explanations[exam_type][exam_id][qid_str] = explanation

                    st.markdown(explanation)
                    st.rerun()
                except urllib.error.HTTPError as e:
                    err_body = e.read().decode("utf-8", errors="replace")
                    st.error(f"API request failed (HTTP {e.code}): {err_body[:500]}")
                except urllib.error.URLError as e:
                    st.error(f"Network error: {e.reason}")
                except Exception as e:
                    st.error(f"Error: {str(e)[:300]}")


# ===== Page: Wrong Answers =====
def render_wrong():
    st.subheader("❌ Wrong Answers Collection")
    data = get_exam_data()
    exam_type = st.session_state.exam_type
    exam_names = data.get('examNames', [])

    # Collect all wrong answers
    wrong_items = []
    for exam_id in data['questions']:
        questions = data['questions'][exam_id]
        answers_data = data['answers'][exam_id]
        exam_name = exam_names[int(exam_id) - 1] if int(exam_id) <= len(exam_names) else f"Exam {exam_id}"
        for q in questions:
            qid_str = str(q['id'])
            is_checked = st.session_state.checked.get(exam_type, {}).get(exam_id, {}).get(qid_str, False)
            if not is_checked:
                continue
            user_ans = st.session_state.user_answers.get(exam_type, {}).get(exam_id, {}).get(qid_str, '')
            correct_ans = sort_answer(answers_data.get(qid_str, ''))
            if sort_answer(user_ans) != correct_ans:
                wrong_items.append({
                    'exam_id': exam_id,
                    'exam_name': exam_name,
                    'question': q,
                    'user_answer': user_ans,
                    'correct_answer': correct_ans
                })

    if not wrong_items:
        st.success("🎉 No wrong answers! Great job!")
        if st.button("← Back to Home"):
            st.session_state.current_page = 'home'
            st.rerun()
        return

    st.caption(f"Total: {len(wrong_items)} wrong questions")

    # Clear all wrong button
    if 'confirm_clear' not in st.session_state:
        st.session_state.confirm_clear = False

    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🗑 Clear All Wrong", type="secondary"):
            st.session_state.confirm_clear = True
            st.rerun()

    if st.session_state.confirm_clear:
        st.warning("⚠️ This will clear ALL answers for the current exam type. Are you sure?")
        col_yes, col_no, _ = st.columns([1, 1, 4])
        with col_yes:
            if st.button("Yes, clear all", type="primary"):
                exam_type = st.session_state.exam_type
                st.session_state.user_answers[exam_type] = {}
                st.session_state.checked[exam_type] = {}
                st.session_state.explanations[exam_type] = {}
                st.session_state.confirm_clear = False
                st.session_state.current_q_idx = 0
                st.rerun()
        with col_no:
            if st.button("Cancel"):
                st.session_state.confirm_clear = False
                st.rerun()

    st.divider()

    # Display each wrong answer
    for i, item in enumerate(wrong_items):
        q = item['question']
        with st.container(border=True):
            st.markdown(f"**[{item['exam_name']}] Q{q['id']}**")
            st.markdown(q['question'])
            st.markdown(f"Your answer: ❌ **{item['user_answer'] or '(none)'}**  →  Correct: ✅ **{item['correct_answer']}**")

            col_a, col_b, col_c = st.columns([1, 1, 4])
            with col_a:
                if st.button("📝 Go to Question", key=f"goto_{exam_type}_{item['exam_id']}_{q['id']}"):
                    st.session_state.current_exam = item['exam_id']
                    st.session_state.current_page = 'exam'
                    # Find the index of this question
                    questions = data['questions'][item['exam_id']]
                    for idx, qq in enumerate(questions):
                        if str(qq['id']) == str(q['id']):
                            st.session_state.current_q_idx = idx
                            break
                    st.rerun()
            with col_b:
                if st.button("🤖 AI Explain", key=f"wrong_ai_{exam_type}_{item['exam_id']}_{q['id']}"):
                    # Trigger AI explanation for this question
                    with st.spinner("Generating explanation..."):
                        options = q['options']
                        option_list = [f"{opt[0]}. {opt[1]}" for opt in options]
                        api_key = load_api_key()
                        backend = st.session_state.get('ai_backend', 'deepseek')
                        if api_key or backend == 'ollama':
                            try:
                                prompt = build_prompt(q['question'], option_list, item['correct_answer'], item['user_answer'])
                                explanation = call_ai(prompt, api_key, backend)
                                st.markdown(explanation)
                            except Exception as e:
                                st.error(f"Error: {str(e)[:300]}")
                        else:
                            st.warning("Please configure API key in Settings.")
            with col_c:
                search_url = f"https://www.baidu.com/s?wd={urllib.parse.quote(q['question'])}"
                st.markdown(f"[🔍 Baidu Search]({search_url})")

    if st.button("← Back to Home"):
        st.session_state.current_page = 'home'
        st.rerun()


# ===== Page: Settings =====
def render_settings():
    st.subheader("⚙️ Settings")

    tab1, tab2 = st.tabs(["API Configuration", "About"])

    with tab1:
        st.markdown("### 🤖 AI Backend Configuration")

        # Backend selection
        backend = st.selectbox(
            "AI Backend",
            options=["deepseek", "doubao", "ollama"],
            index=["deepseek", "doubao", "ollama"].index(st.session_state.get('ai_backend', 'deepseek')),
            format_func=lambda x: {"deepseek": "DeepSeek (Recommended)", "doubao": "Doubao / Volcengine", "ollama": "Ollama (Local)"}[x],
            key="settings_backend"
        )
        if backend != st.session_state.get('ai_backend'):
            st.session_state.ai_backend = backend

        # API Key input (not needed for Ollama)
        if backend != 'ollama':
            current_key = st.session_state.get('api_key', '') or ''
            # Try to load from file
            if not current_key and os.path.exists(API_KEY_FILE):
                with open(API_KEY_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            current_key = line
                            break

            api_key_input = st.text_input(
                "API Key",
                value=current_key,
                type="password",
                placeholder="Enter your API key...",
                key="settings_api_key"
            )

            col_save, col_file = st.columns(2)
            with col_save:
                if st.button("💾 Save to Session", use_container_width=True):
                    st.session_state.api_key = api_key_input
                    st.success("API key saved to current session!")
            with col_file:
                if st.button("📄 Save to api_key.txt", use_container_width=True):
                    with open(API_KEY_FILE, "w", encoding="utf-8") as f:
                        f.write(api_key_input)
                    st.session_state.api_key = api_key_input
                    st.success(f"API key saved to {API_KEY_FILE}!")

            st.divider()
            st.markdown("""
            **How to get an API key:**
            - **DeepSeek**: Register at [platform.deepseek.com](https://platform.deepseek.com/api_keys)
              - New users get 5 million free tokens
            - **Doubao (Volcengine)**: Register at [console.volcengine.com](https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint)
            """)
        else:
            st.info(f"Ollama will connect to: {OLLAMA_URL}\nModel: {OLLAMA_MODEL}\n\nMake sure Ollama is running locally and the model is pulled.")

    with tab2:
        st.markdown("""
        ### 📚 Medical Diagnostics Learning System

        A comprehensive learning platform for clinical diagnostics and auscultation training.

        **Features:**
        - 8 diagnostic exam sets (381 questions total)
        - 1 auscultation training set (68 questions)
        - AI-powered question explanations
        - Wrong answer collection and review
        - Progress tracking

        **Data Sources:**
        - Diagnostics exam questions from clinical diagnostics textbooks
        - Auscultation questions from cardiopulmonary auscultation training materials

        **Tech Stack:**
        - Built with [Streamlit](https://streamlit.io)
        - AI powered by DeepSeek / Doubao / Ollama
        """)


# ===== Main App =====
def main():
    init_session_state()

    # --- Sidebar Navigation ---
    with st.sidebar:
        st.markdown("## 🩺 Navigation")

        page = st.radio(
            "Navigate to:",
            options=["home", "exam", "wrong", "settings"],
            format_func=lambda x: {
                "home": "🏠 Home",
                "exam": "📝 Exam Practice",
                "wrong": "❌ Wrong Answers",
                "settings": "⚙️ Settings"
            }[x],
            key="sidebar_nav",
            index=["home", "exam", "wrong", "settings"].index(st.session_state.current_page)
        )

        if page != st.session_state.current_page:
            st.session_state.current_page = page
            st.rerun()

        st.divider()

        # Show current exam context
        if st.session_state.current_exam:
            data = get_exam_data()
            exam_names = data.get('examNames', [])
            exam_id = st.session_state.current_exam
            name = exam_names[int(exam_id) - 1] if int(exam_id) <= len(exam_names) else f"Exam {exam_id}"
            st.caption(f"📌 Current: {name}")

        # Quick exam selector
        st.markdown("### Quick Jump")
        data = get_exam_data()
        exam_names_list = data.get('examNames', [f"Exam {k}" for k in data['questions']])
        for eid in data['questions']:
            name = exam_names_list[int(eid) - 1] if int(eid) <= len(exam_names_list) else f"Exam {eid}"
            total_e, done_e = get_exam_stats(data, eid)[:2]
            if st.button(f"📝 {name} ({done_e}/{total_e})", key=f"sidebar_exam_{eid}", use_container_width=True):
                st.session_state.current_exam = eid
                st.session_state.current_q_idx = 0
                st.session_state.current_page = 'exam'
                st.session_state.wrong_only = False
                st.rerun()

        st.divider()
        st.caption("Medical Diagnostics Learning System v1.0")

    # --- Page Router ---
    current_page = st.session_state.current_page

    if current_page == 'home':
        render_home()
    elif current_page == 'exam':
        if st.session_state.current_exam is None:
            st.info("Please select an exam from the Home page or sidebar.")
            if st.button("← Go to Home"):
                st.session_state.current_page = 'home'
                st.rerun()
        else:
            render_exam()
    elif current_page == 'wrong':
        render_wrong()
    elif current_page == 'settings':
        render_settings()


if __name__ == "__main__":
    main()
