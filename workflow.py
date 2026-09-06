"""
workflow.py
The AI workflow engine: talks to Claude, parses JSON responses with retries,
and chains the 4 steps (outline -> flashcards -> quiz -> study plan).
"""

import json
import re
import time

import anthropic

from prompts import prompt_outline, prompt_flashcards, prompt_quiz, prompt_plan

MODEL = "claude-sonnet-4-5"  # good balance of quality/cost/speed
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


def call_claude(client: anthropic.Anthropic, prompt: str, max_tokens: int = 2500) -> dict:
    """Calls Claude and parses the JSON response, retrying on transient
    failures (bad JSON, API hiccups)."""
    last_err = None
    for _ in range(MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = "".join(block.text for block in response.content if block.type == "text")
            return extract_json(raw_text)
        except anthropic.AuthenticationError:
            # Invalid/expired API key — retrying won't help, so fail fast
            # and let the caller show a clear "check your key" message.
            raise
        except json.JSONDecodeError as e:
            last_err = e
            time.sleep(1)
        except anthropic.APIStatusError as e:
            last_err = e
            time.sleep(1.5)
    raise RuntimeError(f"Failed after {MAX_RETRIES + 1} attempts: {last_err}")


def run_workflow(
    client: anthropic.Anthropic,
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
    outline = call_claude(client, prompt_outline(topic, source_text, difficulty))

    # Step 2: Flashcards
    status.update(label="Step 2/4: Writing flashcards...")
    flashcards = call_claude(client, prompt_flashcards(outline, difficulty, num_flashcards))

    # Step 3: Quiz
    status.update(label="Step 3/4: Building quiz questions...")
    quiz = call_claude(client, prompt_quiz(outline, difficulty, num_quiz))

    # Step 4: Study plan (optional)
    plan = {}
    if include_plan:
        status.update(label="Step 4/4: Drafting study plan...")
        plan = call_claude(client, prompt_plan(outline, difficulty, plan_days))

    data = {**outline, **flashcards, **quiz, **plan}
    status.update(label="Done!", state="complete")
    return data
