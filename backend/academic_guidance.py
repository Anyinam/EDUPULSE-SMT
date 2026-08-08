from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable


PATHWAY_PROFILES = [
    {
        "name": "General Science",
        "subjects": [("mathematics", 0.35), ("science", 0.4), ("ict", 0.15), ("english language", 0.1)],
        "summary": "best suited for learners showing sustained strength in quantitative and science-oriented subjects",
    },
    {
        "name": "Business",
        "subjects": [("mathematics", 0.3), ("english language", 0.25), ("social studies", 0.2), ("ict", 0.25)],
        "summary": "fits learners with balanced numeracy, communication, and digital-skills performance",
    },
    {
        "name": "General Arts",
        "subjects": [("english language", 0.35), ("social studies", 0.3), ("religious & moral education", 0.2), ("french", 0.15)],
        "summary": "fits learners who show stronger language, humanities, and communication patterns",
    },
    {
        "name": "TVET / Technical",
        "subjects": [("mathematics", 0.25), ("science", 0.2), ("ict", 0.25), ("creative arts", 0.15), ("pre-technical skills", 0.15)],
        "summary": "fits learners who perform better in practical, technical, and applied problem-solving work",
    },
    {
        "name": "Home Economics",
        "subjects": [("science", 0.2), ("english language", 0.2), ("creative arts", 0.2), ("home economics", 0.4)],
        "summary": "fits learners whose strengths lean toward applied life skills, communication, and practical coursework",
    },
]


def normalize_subject_key(subject_name: str | None) -> str:
    return " ".join(str(subject_name or "").strip().lower().split())


def normalize_topic_key(topic_name: str | None) -> str:
    return " ".join(str(topic_name or "").strip().lower().split())


def _build_report_learner_snapshot(report, fit_score: float):
    student = getattr(report, "student", None)
    student_name = None
    student_code = None
    if student is not None:
        student_name = getattr(student, "name", None) or " ".join(
            part for part in [getattr(student, "first_name", None), getattr(student, "surname", None)] if part
        ).strip()
        student_code = getattr(student, "student_code", None)

    return {
        "student_id": getattr(report, "student_id", None),
        "student_name": student_name or "Learner",
        "student_code": student_code,
        "class_name": getattr(report, "class_name", None) or "Unassigned",
        "fit_score": round(float(fit_score or 0.0), 1),
    }


def build_pathway_recommendations(subject_grades: Iterable[dict], top_n: int = 2):
    normalized_scores = {}
    for item in subject_grades or []:
        subject_key = normalize_subject_key(item.get("subject"))
        if not subject_key:
            continue
        try:
            normalized_scores[subject_key] = float(item.get("total") or 0.0)
        except (TypeError, ValueError):
            normalized_scores[subject_key] = 0.0

    scored_profiles = []
    for profile in PATHWAY_PROFILES:
        weighted_total = 0.0
        weight_used = 0.0
        strengths = []
        for subject_key, weight in profile["subjects"]:
            if subject_key not in normalized_scores:
                continue
            score = normalized_scores[subject_key]
            weighted_total += score * weight
            weight_used += weight
            if score >= 65:
                strengths.append(subject_key)
        if weight_used == 0:
            continue
        fit_score = round(weighted_total / weight_used, 1)
        scored_profiles.append(
            {
                "pathway": profile["name"],
                "fit_score": fit_score,
                "summary": profile["summary"],
                "strengths": strengths[:3],
            }
        )

    scored_profiles.sort(key=lambda item: item["fit_score"], reverse=True)
    return scored_profiles[:top_n]


def filter_subject_grades(subject_grades: Iterable[dict], allowed_subjects: Iterable[str] | None = None):
    if not allowed_subjects:
        return [item for item in subject_grades or [] if isinstance(item, dict)]

    allowed = {normalize_subject_key(subject) for subject in allowed_subjects if normalize_subject_key(subject)}
    return [
        item
        for item in (subject_grades or [])
        if isinstance(item, dict) and normalize_subject_key(item.get("subject")) in allowed
    ]


def extract_diagnostic_hotspots(
    subject_grades: Iterable[dict],
    allowed_subjects: Iterable[str] | None = None,
    threshold: float = 0.55,
):
    hotspots = []
    for grade in filter_subject_grades(subject_grades, allowed_subjects=allowed_subjects):
        subject_name = grade.get("subject") or "Subject"
        for topic in grade.get("diagnostic_topics") or []:
            if not isinstance(topic, dict):
                continue
            topic_name = str(topic.get("topic") or "").strip()
            if not topic_name:
                continue
            try:
                score = float(topic.get("score") or 0.0)
                max_score = float(topic.get("max_score") or 0.0)
            except (TypeError, ValueError):
                continue
            if max_score <= 0:
                continue
            ratio = score / max_score
            hotspots.append(
                {
                    "subject": subject_name,
                    "topic": topic_name,
                    "score": round(score, 1),
                    "max_score": round(max_score, 1),
                    "ratio": round(ratio * 100, 1),
                    "is_low": ratio <= threshold,
                    "advice": None,
                    "practice": [],
                }
            )
    hotspots.sort(key=lambda item: (not item["is_low"], item["ratio"], item["subject"], item["topic"]))
    return hotspots


def build_report_guidance_payload(
    subject_grades: Iterable[dict],
    allowed_subjects: Iterable[str] | None = None,
):
    filtered_grades = filter_subject_grades(subject_grades, allowed_subjects=allowed_subjects)
    hotspots = [
        item
        for item in extract_diagnostic_hotspots(filtered_grades)
        if item["is_low"]
    ]
    pathways = build_pathway_recommendations(filtered_grades)
    primary_pathway = pathways[0] if pathways else None

    return {
        "diagnostic_hotspots": hotspots[:4],
        "pathway_recommendations": pathways,
        "printable_card": {
            "headline": f"Recommended SHS pathway: {primary_pathway['pathway']}" if primary_pathway else None,
            "pathway_fit_score": primary_pathway.get("fit_score") if primary_pathway else None,
            "focus_note": (
                f"Priority focus: {hotspots[0]['subject']} - {hotspots[0]['topic']}. {hotspots[0]['advice']}"
                if hotspots
                else None
            ),
            "secondary_pathway": pathways[1]["pathway"] if len(pathways) > 1 else None,
        },
    }
def build_academic_guidance_summary(
    report_cards: Iterable,
    allowed_classes: Iterable[str] | None = None,
    allowed_subjects: Iterable[str] | None = None,
):
    class_filter = {str(item).strip() for item in (allowed_classes or []) if str(item).strip()}
    hotspot_buckets = defaultdict(lambda: {"low_count": 0, "subject": None, "topic": None, "advice": None, "practice": set()})
    pathway_counter = Counter()
    pathway_scores = defaultdict(list)
    pathway_learners = defaultdict(list)
    class_counter = Counter()
    class_pathway_counter = defaultdict(Counter)
    analyzed_reports = 0
    tracked_subjects = set()

    for report in report_cards or []:
        class_name = getattr(report, "class_name", None) or "Unassigned"
        if class_filter and class_name not in class_filter:
            continue

        filtered_grades = filter_subject_grades(getattr(report, "subject_grades", []) or [], allowed_subjects=allowed_subjects)
        if not filtered_grades:
            continue

        analyzed_reports += 1
        class_counter[class_name] += 1
        tracked_subjects.update(normalize_subject_key(item.get("subject")) for item in filtered_grades if item.get("subject"))

        guidance = build_report_guidance_payload(filtered_grades)
        for hotspot in guidance["diagnostic_hotspots"]:
            key = (normalize_subject_key(hotspot["subject"]), normalize_topic_key(hotspot["topic"]))
            bucket = hotspot_buckets[key]
            bucket["low_count"] += 1
            bucket["subject"] = hotspot["subject"]
            bucket["topic"] = hotspot["topic"]
            bucket["advice"] = hotspot.get("advice")
            for item in hotspot.get("practice") or []:
                bucket["practice"].add(item)

        if guidance["pathway_recommendations"]:
            top_pathway = guidance["pathway_recommendations"][0]
            pathway_counter[top_pathway["pathway"]] += 1
            pathway_scores[top_pathway["pathway"]].append(top_pathway["fit_score"])
            pathway_learners[top_pathway["pathway"]].append(
                _build_report_learner_snapshot(report, top_pathway["fit_score"])
            )
            class_pathway_counter[class_name][top_pathway["pathway"]] += 1

    diagnostic_hotspots = []
    for bucket in hotspot_buckets.values():
        diagnostic_hotspots.append(
            {
                "subject": bucket["subject"],
                "topic": bucket["topic"],
                "low_report_count": bucket["low_count"],
                "advice": bucket["advice"],
                "practice": sorted(bucket["practice"]),
            }
        )
    diagnostic_hotspots.sort(key=lambda item: (-item["low_report_count"], item["subject"], item["topic"]))

    pathway_distribution = [
        {
            "pathway": pathway,
            "student_count": count,
            "average_fit_score": round(sum(pathway_scores[pathway]) / len(pathway_scores[pathway]), 1) if pathway_scores[pathway] else 0.0,
            "learners": sorted(
                pathway_learners[pathway],
                key=lambda item: (-item["fit_score"], item["student_name"], item["class_name"]),
            ),
        }
        for pathway, count in pathway_counter.most_common()
    ]

    class_overview = []
    for class_name, report_count in class_counter.items():
        top_pathway = class_pathway_counter[class_name].most_common(1)
        class_overview.append(
            {
                "class_name": class_name,
                "report_count": report_count,
                "top_pathway": top_pathway[0][0] if top_pathway else None,
                "top_pathway_count": top_pathway[0][1] if top_pathway else 0,
            }
        )
    class_overview.sort(key=lambda item: item["class_name"])

    return {
        "summary": {
            "reports_analyzed": analyzed_reports,
            "tracked_subjects": len(tracked_subjects),
            "classes_in_scope": len(class_overview),
        },
        "diagnostic_hotspots": diagnostic_hotspots[:6],
        "pathway_distribution": pathway_distribution[:5],
        "class_overview": class_overview,
    }