"""
prompts.py
All AI prompt templates used by the study pack workflow.
Keeping prompts separate makes them easy to tweak/version without touching app or workflow logic.
"""

import json


def content_description(topic: str, source_text: str) -> str:
    """Builds the 'what to study' portion of a prompt, based on either
    pasted/uploaded source text or a plain topic string."""
    if source_text.strip():
        return f'Base everything strictly on this source material:\n"""\n{source_text[:12000]}\n"""\n'
    return f'The study topic is: "{topic.strip()}". Use your own knowledge to cover it thoroughly.\n'


def prompt_outline(topic: str, source_text: str, difficulty: str) -> str:
    desc = content_description(topic, source_text)
    return f"""You are an expert tutor. {desc}
Difficulty level: {difficulty}.

Return ONLY valid JSON (no markdown fences, no commentary) with this schema:
{{
  "title": "short title for the study pack",
  "summary": "a clear, well-structured summary in 3-6 short paragraphs (use \\n\\n between paragraphs)",
  "key_concepts": [ {{"term": "...", "explanation": "..."}}, ... 6 to 10 items ]
}}"""


def prompt_flashcards(outline: dict, difficulty: str, num_flashcards: int) -> str:
    concepts = json.dumps(outline.get("key_concepts", []))
    return f"""You are an expert tutor creating flashcards at {difficulty} difficulty.
Base them on these key concepts: {concepts}
Topic context: {outline.get('title', '')}

Return ONLY valid JSON with this schema:
{{
  "flashcards": [ {{"question": "...", "answer": "..."}}, ... exactly {num_flashcards} items ]
}}"""


def prompt_quiz(outline: dict, difficulty: str, num_quiz: int) -> str:
    concepts = json.dumps(outline.get("key_concepts", []))
    return f"""You are an expert tutor creating a multiple-choice quiz at {difficulty} difficulty.
Base it on these key concepts: {concepts}
Topic context: {outline.get('title', '')}

Return ONLY valid JSON with this schema:
{{
  "quiz": [ {{"question": "...", "options": ["A","B","C","D"], "correct_index": 0, "explanation": "..."}}, ... exactly {num_quiz} items ]
}}
Rules: options must be plausible and mutually exclusive; correct_index is 0-based."""


def prompt_plan(outline: dict, difficulty: str, plan_days: int) -> str:
    concepts = json.dumps(outline.get("key_concepts", []))
    return f"""You are an expert tutor creating a {plan_days}-day study plan at {difficulty} difficulty.
Base it on these key concepts: {concepts}
Topic context: {outline.get('title', '')}

Return ONLY valid JSON with this schema:
{{
  "study_plan": [ {{"day": 1, "focus": "...", "tasks": ["...", "..."]}}, ... covering {plan_days} days ]
}}"""
