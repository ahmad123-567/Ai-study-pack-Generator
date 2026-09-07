"""
workflow.py
The AI workflow engine: talks to Google Gemini's free API, parses JSON responses
with retries, and chains the 4 steps (outline -> flashcards -> quiz -> study plan).

Why Gemini: it has a free tier (no credit card required) via Google AI Studio.
Get a free API key at https://aistudio.google.com/apikey

Uses the current `google-genai` SDK (the older `google-generativeai` package
is deprecated).
"""

import json
import re
import time

from google import genai
from google.genai import errors as genai_errors

from prompts import prompt_outline, prompt_flashcards, prompt_quiz, prompt_plan

MODEL_CANDIDATES = [
    "gemini-3.6-flash",   # current recommended free-tier model (per Google's latest guidance)
    "gemini-flash-latest",  # generic alias Google keeps pointed at their current flash model
    "gemini-2.5-flash",   # fallback if the above aren't available on your account
]
MAX_RETRIES = 2


def extract_json(text: str) -> dict:
    """Strips markdown fences / stray text and parses the JSON object inside."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def call_ai(api_key: str, prompt: str) -> dict:
    """Calls the free Gemini API and parses the JSON response, retrying on
    transient failures (bad JSON, rate limits), and falling back to the next
    candidate model if the current one is unavailable (404)."""
    client = genai.Client(api_key=api_key)

    last_err = None
    for model_name in MODEL_CANDIDATES:
        for _ in range(MAX_RETRIES + 1):
            try:
                response = client.models.generate_content(model=model_name, contents=prompt)
                return extract_json(response.text)
            except genai_errors.ClientError as e:
                if e.code in (401, 403):
                    raise  # bad key / no permission — retrying or switching models won't help
                if e.code == 404:
                    last_err = e
                    break  # this model isn't available — try the next candidate
                last_err = e
                time.sleep(5 if e.code == 429 else 1.5)
            except json.JSONDecodeError as e:
                last_err = e
                time.sleep(1)
            except genai_errors.ServerError as e:
                last_err = e
                time.sleep(1.5)
    raise RuntimeError(f"Failed after trying all models: {last_err}")


def run_workflow(
    api_key: str,
    status,
    topic: str,
    source_text: str,
    difficulty: str,
    num_flashcards: int,
    num_quiz: int,
    include_plan: bool,
    plan_days: int,
) -> dict:
    """Runs the full 4-step AI workflow and returns the combined study pack dict.

    `status` is a Streamlit st.status(...) context object used to show
    live progress; any object with an .update(label=..., state=...) method works.
    """
    # Step 1: Outline + key concepts
    status.update(label="Step 1/4: Building outline & key concepts...")
    outline = call_ai(api_key, prompt_outline(topic, source_text, difficulty))

    # Step 2: Flashcards
    status.update(label="Step 2/4: Writing flashcards...")
    flashcards = call_ai(api_key, prompt_flashcards(outline, difficulty, num_flashcards))

    # Step 3: Quiz
    status.update(label="Step 3/4: Building quiz questions...")
    quiz = call_ai(api_key, prompt_quiz(outline, difficulty, num_quiz))

    # Step 4: Study plan (optional)
    plan = {}
    if include_plan:
        status.update(label="Step 4/4: Drafting study plan...")
        plan = call_ai(api_key, prompt_plan(outline, difficulty, plan_days))

    data = {**outline, **flashcards, **quiz, **plan}
    status.update(label="Done!", state="complete")
    return data
