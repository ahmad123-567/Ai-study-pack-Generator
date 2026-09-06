"""
app.py
Main entry point (Streamlit UI). Run this with: streamlit run app.py
All AI logic lives in workflow.py / prompts.py — this file only handles
layout, inputs, session state, and rendering results.
"""

import json
from datetime import datetime

import anthropic
import streamlit as st

from workflow import run_workflow

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(
    page_title="AI Study Pack Generator",
    page_icon="📚",
    layout="wide",
)

# ----------------------------
# Session state init
# ----------------------------
if "history" not in st.session_state:
    st.session_state["history"] = []  # list of {id, title, created_at, data}
if "study_pack" not in st.session_state:
    st.session_state["study_pack"] = None

# ----------------------------
# Sidebar - Settings
# ----------------------------
with st.sidebar:
    st.title("⚙️ Settings")
    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        help="Get a key at https://console.anthropic.com/. It is only used for this session and never stored.",
    )
    st.markdown("---")
    st.subheader("Study Pack Options")
    difficulty = st.select_slider(
        "Difficulty level",
        options=["Beginner", "Intermediate", "Advanced"],
        value="Intermediate",
    )
    num_flashcards = st.slider("Number of flashcards", 5, 20, 10)
    num_quiz = st.slider("Number of quiz questions", 3, 15, 5)
    include_plan = st.checkbox("Include a study plan", value=True)
    plan_days = st.number_input(
        "Study plan length (days)", min_value=1, max_value=30, value=7, disabled=not include_plan
    )
    st.markdown("---")

    # ---- History / project memory ----
    st.subheader("🕘 History")
    if st.session_state["history"]:
        options = ["(current)"] + [
            f"{h['title']} — {h['created_at']}" for h in st.session_state["history"]
        ]
        choice = st.selectbox("Previously generated packs", options, index=0)
        if choice != "(current)":
            idx = options.index(choice) - 1
            if st.button("Load this pack", use_container_width=True):
                st.session_state["study_pack"] = st.session_state["history"][idx]["data"]
                st.rerun()
        if st.button("🗑️ Clear history", use_container_width=True):
            st.session_state["history"] = []
            st.rerun()
    else:
        st.caption("No saved packs yet this session.")

    st.markdown("---")
    st.caption("Made with Streamlit + Claude · Multi-step AI workflow")

st.title("📚 AI Study Pack Generator")
st.write(
    "Turn any topic, textbook chapter, or set of notes into a complete study pack. "
    "This version uses a **4-step AI workflow** (outline → flashcards → quiz → study plan) "
    "for higher-quality, more consistent results."
)

# ----------------------------
# Input area
# ----------------------------
tab1, tab2 = st.tabs(["✍️ Enter a topic", "📄 Paste / upload notes"])

topic = ""
source_text = ""

with tab1:
    topic = st.text_input("Topic to study", placeholder="e.g. Photosynthesis, The French Revolution, Big-O notation")

with tab2:
    uploaded_file = st.file_uploader("Upload a .txt or .md file", type=["txt", "md"])
    pasted_text = st.text_area("...or paste your notes / text here", height=200)
    if uploaded_file is not None:
        source_text = uploaded_file.read().decode("utf-8", errors="ignore")
    elif pasted_text.strip():
        source_text = pasted_text

generate_btn = st.button("✨ Generate Study Pack", type="primary", use_container_width=True)

# ----------------------------
# Generation logic
# ----------------------------
if generate_btn:
    if not api_key:
        st.error("Please enter your Anthropic API key in the sidebar.")
    elif not topic.strip() and not source_text.strip():
        st.error("Please enter a topic or provide some notes/text first.")
    else:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            with st.status("Starting AI workflow...", expanded=True) as status:
                data = run_workflow(
                    client=client,
                    status=status,
                    topic=topic,
                    source_text=source_text,
                    difficulty=difficulty,
                    num_flashcards=num_flashcards,
                    num_quiz=num_quiz,
                    include_plan=include_plan,
                    plan_days=plan_days,
                )
            st.session_state["study_pack"] = data
            st.session_state["history"].insert(
                0,
                {
                    "id": len(st.session_state["history"]) + 1,
                    "title": data.get("title", "Untitled"),
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "data": data,
                },
            )
            st.success("Study pack ready!")
        except anthropic.AuthenticationError:
            st.error("Invalid API key. Please check your key and try again.")
        except RuntimeError as e:
            st.error(f"The AI workflow failed: {e}")
        except Exception as e:
            st.error(f"Something went wrong: {e}")

# ----------------------------
# Display results
# ----------------------------
data = st.session_state.get("study_pack")
if data:
    st.header(data.get("title", "Your Study Pack"))

    if data.get("note"):
        st.info(data["note"])

    result_tabs = st.tabs(["📝 Summary", "🔑 Key Concepts", "🗂️ Flashcards", "❓ Quiz", "🗓️ Study Plan", "⬇️ Export"])

    with result_tabs[0]:
        st.write(data.get("summary", "No summary available."))

    with result_tabs[1]:
        for kc in data.get("key_concepts", []):
            with st.expander(f"**{kc.get('term', '')}**"):
                st.write(kc.get("explanation", ""))

    with result_tabs[2]:
        st.caption("Click a card to reveal the answer.")
        for i, fc in enumerate(data.get("flashcards", [])):
            with st.expander(f"Card {i+1}: {fc.get('question', '')}"):
                st.write(fc.get("answer", ""))

    with result_tabs[3]:
        quiz = data.get("quiz", [])
        if quiz:
            with st.form("quiz_form"):
                user_answers = {}
                for i, q in enumerate(quiz):
                    user_answers[i] = st.radio(
                        f"{i+1}. {q.get('question', '')}",
                        options=list(range(len(q.get("options", [])))),
                        format_func=lambda idx, q=q: q["options"][idx],
                        key=f"quiz_{i}",
                        index=None,
                    )
                submitted = st.form_submit_button("Check my answers")
            if submitted:
                score = 0
                for i, q in enumerate(quiz):
                    correct = q.get("correct_index", 0)
                    chosen = user_answers.get(i)
                    if chosen == correct:
                        score += 1
                        st.success(f"Q{i+1}: Correct! {q.get('explanation', '')}")
                    else:
                        chosen_text = q["options"][chosen] if chosen is not None else "No answer"
                        st.error(
                            f"Q{i+1}: Incorrect (you chose: {chosen_text}). "
                            f"Correct answer: {q['options'][correct]}. {q.get('explanation', '')}"
                        )
                st.info(f"Score: {score} / {len(quiz)}")
        else:
            st.write("No quiz questions available.")

    with result_tabs[4]:
        plan = data.get("study_plan", [])
        if plan:
            for day in plan:
                with st.expander(f"Day {day.get('day', '?')}: {day.get('focus', '')}"):
                    for task in day.get("tasks", []):
                        st.checkbox(task, key=f"day{day.get('day')}_{task[:20]}")
        else:
            st.write("No study plan was generated (enable it in the sidebar and regenerate).")

    with result_tabs[5]:
        md_lines = [f"# {data.get('title', 'Study Pack')}\n"]
        md_lines.append("## Summary\n" + data.get("summary", "") + "\n")
        md_lines.append("## Key Concepts")
        for kc in data.get("key_concepts", []):
            md_lines.append(f"- **{kc.get('term','')}**: {kc.get('explanation','')}")
        md_lines.append("\n## Flashcards")
        for i, fc in enumerate(data.get("flashcards", [])):
            md_lines.append(f"{i+1}. Q: {fc.get('question','')}\n   A: {fc.get('answer','')}")
        md_lines.append("\n## Quiz")
        for i, q in enumerate(data.get("quiz", [])):
            opts = "\n".join([f"   {chr(65+j)}. {opt}" for j, opt in enumerate(q.get("options", []))])
            correct_letter = chr(65 + q.get("correct_index", 0))
            md_lines.append(f"{i+1}. {q.get('question','')}\n{opts}\n   Correct: {correct_letter} — {q.get('explanation','')}")
        if data.get("study_plan"):
            md_lines.append("\n## Study Plan")
            for day in data["study_plan"]:
                tasks = "\n".join([f"   - {t}" for t in day.get("tasks", [])])
                md_lines.append(f"Day {day.get('day')}: {day.get('focus','')}\n{tasks}")

        md_content = "\n".join(md_lines)
        st.download_button(
            "Download as Markdown (.md)",
            data=md_content,
            file_name=f"study_pack_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            use_container_width=True,
        )
        st.download_button(
            "Download raw data (.json)",
            data=json.dumps(data, indent=2),
            file_name=f"study_pack_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            use_container_width=True,
        )
