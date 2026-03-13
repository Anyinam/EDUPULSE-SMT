import json
import os
from typing import Any, Dict, List

import requests


def _difficulty_verbs(level: str) -> List[str]:
    level = (level or "medium").lower()
    if level == "easy":
        return ["define", "identify", "list", "state"]
    if level == "hard":
        return ["analyze", "evaluate", "justify", "compare"]
    return ["explain", "apply", "differentiate", "solve"]


def _fallback_questions(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    topic = payload.get("topic") or "General Revision"
    question_type = (payload.get("question_type") or "mcq").lower()
    difficulty = payload.get("difficulty") or "medium"
    teacher_instructions = (payload.get("teacher_instructions") or "").strip()
    class_name = payload.get("class_name") or "Selected Class"
    subject_name = payload.get("subject_name") or "General Subject"
    exam_type = payload.get("exam_type") or "Class Test"
    count = int(payload.get("count") or 5)
    count = max(1, min(count, 20))

    verbs = _difficulty_verbs(difficulty)
    section = "A"

    questions: List[Dict[str, Any]] = []
    for index in range(count):
        number = index + 1
        verb = verbs[index % len(verbs)]

        if question_type == "essay":
            questions.append(
                {
                    "type": "essay",
                    "question": f"{number}. {verb.capitalize()} the concept of {topic} in {subject_name} and provide two classroom-relevant examples for {class_name}.",
                    "marks": 10,
                    "section": section,
                    "difficulty": difficulty,
                    "marking_guide": "Award marks for correctness (4), depth of explanation (3), examples/application (2), and clarity/organization (1).",
                    "teacher_instructions": teacher_instructions,
                }
            )
        elif question_type == "short":
            questions.append(
                {
                    "type": "short",
                    "question": f"{number}. {verb.capitalize()} one key principle of {topic} and apply it to a practical {subject_name} scenario.",
                    "marks": 5,
                    "section": section,
                    "difficulty": difficulty,
                    "marking_guide": "Award marks for principle accuracy (2), valid application (2), and clear expression (1).",
                    "teacher_instructions": teacher_instructions,
                }
            )
        else:
            stem = f"{number}. Which option best answers this {subject_name} question on {topic} for {class_name}?"
            questions.append(
                {
                    "type": "mcq",
                    "question": stem,
                    "options": [
                        f"Correctly applies {topic} to the given context",
                        f"Partially applies {topic} but misses a key condition",
                        f"Uses an incorrect rule unrelated to {topic}",
                        "None of the above",
                    ],
                    "correct_answer": "A",
                    "marks": 2,
                    "section": section,
                    "difficulty": difficulty,
                    "marking_guide": "Correct option: A. Credit only exact option unless teacher rubric allows equivalent wording.",
                    "teacher_instructions": teacher_instructions,
                }
            )

    return questions


def generate_exam_questions(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate exam questions using OpenAI when available.
    Falls back to deterministic local generation in worst-case scenarios.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        return {
            "provider": "fallback",
            "status": "fallback",
            "message": "OPENAI_API_KEY not configured; generated fallback questions.",
            "questions": _fallback_questions(payload),
        }

    topic = payload.get("topic") or "General Revision"
    difficulty = payload.get("difficulty") or "medium"
    question_type = (payload.get("question_type") or "mcq").lower()
    count = int(payload.get("count") or 5)
    count = max(1, min(count, 20))
    class_name = payload.get("class_name") or "Selected Class"
    subject_name = payload.get("subject_name") or "General Subject"
    exam_type = payload.get("exam_type") or "Class Test"
    teacher_instructions = (payload.get("teacher_instructions") or "").strip()

    system_prompt = (
        "You are an experienced school teacher and assessment designer. "
        "Generate exam questions as strict JSON only."
    )
    user_prompt = (
        f"Generate {count} {question_type} questions for {subject_name}, class {class_name}, "
        f"topic '{topic}', difficulty {difficulty}, exam type {exam_type}. "
        f"Teacher instructions: {teacher_instructions or 'None provided'}. "
        "These teacher instructions are high priority and must be followed unless unsafe or impossible. "
        "Return ONLY JSON array. Each item must include: "
        "type, question, marks, section, difficulty, marking_guide. "
        "If type is mcq, include options (array of exactly 4 strings) and correct_answer (A/B/C/D). "
        "Questions must be curriculum-appropriate, unambiguous, and non-repetitive. "
        "Do not include placeholders, meta text, or markdown."
    )

    request_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.5,
        "response_format": {"type": "json_object"},
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request_payload,
            timeout=25,
        )

        if response.status_code >= 400:
            return {
                "provider": "fallback",
                "status": "fallback",
                "message": f"AI provider error ({response.status_code}); generated fallback questions.",
                "questions": _fallback_questions(payload),
            }

        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "{}")
        )

        parsed = json.loads(content)
        questions = parsed.get("questions") if isinstance(parsed, dict) else parsed
        if not isinstance(questions, list) or len(questions) == 0:
            questions = _fallback_questions(payload)
            return {
                "provider": "fallback",
                "status": "fallback",
                "message": "AI returned invalid format; generated fallback questions.",
                "questions": questions,
            }

        return {
            "provider": "openai",
            "status": "success",
            "message": "Questions generated successfully.",
            "questions": questions,
        }
    except Exception:
        return {
            "provider": "fallback",
            "status": "fallback",
            "message": "AI request failed; generated fallback questions.",
            "questions": _fallback_questions(payload),
        }
