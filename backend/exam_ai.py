import json
import os
from typing import Any, Dict, List

import requests


def _fallback_questions(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    topic = payload.get("topic") or "General Revision"
    question_type = (payload.get("question_type") or "mcq").lower()
    difficulty = payload.get("difficulty") or "medium"
    count = int(payload.get("count") or 5)
    count = max(1, min(count, 20))

    questions: List[Dict[str, Any]] = []
    for index in range(count):
        number = index + 1
        if question_type == "essay":
            questions.append(
                {
                    "type": "essay",
                    "question": f"{number}. Explain {topic} and give two practical examples suitable for your class level.",
                    "marks": 10,
                    "section": "A",
                    "difficulty": difficulty,
                    "marking_guide": "Award marks for concept accuracy, examples, and clear explanation.",
                }
            )
        elif question_type == "short":
            questions.append(
                {
                    "type": "short",
                    "question": f"{number}. State one key principle of {topic} and apply it to a real-life situation.",
                    "marks": 5,
                    "section": "A",
                    "difficulty": difficulty,
                    "marking_guide": "Award marks for correct principle and valid application.",
                }
            )
        else:
            questions.append(
                {
                    "type": "mcq",
                    "question": f"{number}. Which statement best describes {topic}?",
                    "options": [
                        "A complete and correct interpretation",
                        "A partially correct interpretation",
                        "An incorrect interpretation",
                        "None of the above",
                    ],
                    "correct_answer": "A",
                    "marks": 2,
                    "section": "A",
                    "difficulty": difficulty,
                    "marking_guide": "Correct option: A",
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

    system_prompt = (
        "You are an experienced school teacher and assessment designer. "
        "Generate exam questions as strict JSON only."
    )
    user_prompt = (
        f"Generate {count} {question_type} questions for {subject_name}, class {class_name}, "
        f"topic '{topic}', difficulty {difficulty}, exam type {exam_type}. "
        "Return ONLY JSON array. Each item must include: "
        "type, question, marks, section, difficulty, marking_guide. "
        "If type is mcq, include options (array of 4) and correct_answer (A/B/C/D)."
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
