from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable


CHIEF_EXAMINER_INSIGHT_LIBRARY = {
    "mathematics": {
        "algebra": {
            "issue": "students often lose marks by skipping steps in simplification and equation solving",
            "advice": "practise step-by-step workings and show each transformation clearly",
            "practice": ["linear equations", "simultaneous equations", "algebraic simplification"],
        },
        "geometry": {
            "issue": "students often state final answers without giving geometric reasons or correct constructions",
            "advice": "focus on theorem wording, labelled diagrams, and proof-based explanations",
            "practice": ["circle theorems", "angle properties", "construction and loci"],
        },
        "statistics": {
            "issue": "students misread tables and use the wrong method for averages and probability",
            "advice": "revise interpretation of charts, mean/median calculations, and probability steps",
            "practice": ["mean and median", "frequency tables", "simple probability"],
        },
        "word problems": {
            "issue": "students struggle to convert story questions into mathematical expressions",
            "advice": "teach a read-plan-solve-check routine before attempting the calculation",
            "practice": ["ratio problems", "commercial arithmetic", "multi-step word problems"],
        },
    },
    "english language": {
        "grammar": {
            "issue": "students make avoidable errors in tense, concord, and sentence construction",
            "advice": "drill grammar correction and short sentence-rewrite exercises weekly",
            "practice": ["concord", "tense consistency", "sentence transformation"],
        },
        "comprehension": {
            "issue": "students copy large passages instead of giving precise answers from the text",
            "advice": "train learners to answer in concise sentences tied directly to the question stem",
            "practice": ["short-answer comprehension", "inference questions", "vocabulary in context"],
        },
        "composition": {
            "issue": "students lose marks through weak structure, poor paragraphing, and limited vocabulary",
            "advice": "use planning outlines and model introductions before full essay writing",
            "practice": ["narrative essays", "formal letter writing", "paragraph development"],
        },
    },
    "science": {
        "scientific units": {
            "issue": "students frequently omit or misuse standard scientific units",
            "advice": "revise SI units alongside every calculation and experiment summary",
            "practice": ["measurement units", "formula substitution", "unit conversion"],
        },
        "experiments": {
            "issue": "students describe practical procedures vaguely and miss key observations",
            "advice": "teach observation-result-conclusion writing in a fixed structure",
            "practice": ["labelling apparatus", "experiment write-ups", "observation tables"],
        },
        "human biology": {
            "issue": "students confuse organ functions and fail to connect concepts to real-life examples",
            "advice": "revise systems using labelled diagrams and short oral explanations",
            "practice": ["digestive system", "respiration", "reproduction"],
        },
    },
    "social studies": {
        "citizenship": {
            "issue": "students list points without explaining their civic importance",
            "advice": "insist on explanation sentences after every listed point",
            "practice": ["responsible citizenship", "governance", "rights and responsibilities"],
        },
        "environment": {
            "issue": "students identify problems correctly but do not propose practical solutions",
            "advice": "pair every environmental issue with at least two realistic interventions",
            "practice": ["sanitation", "environmental conservation", "community problem solving"],
        },
        "map reading": {
            "issue": "students misinterpret symbols and direction questions",
            "advice": "revise map symbols, scales, and direction drills with timed practice",
            "practice": ["map symbols", "bearing and direction", "scale interpretation"],
        },
    },
    "ict": {
        "practical": {
            "issue": "students know the theory but struggle to apply it in real computer tasks",
            "advice": "increase hands-on sessions with short repeatable practical exercises",
            "practice": ["file management", "word processing", "spreadsheet basics"],
        },
        "concepts": {
            "issue": "students mix up key hardware, software, and networking concepts",
            "advice": "use matching drills and simple diagrams to reinforce core definitions",
            "practice": ["hardware vs software", "input and output devices", "basic networking"],
        },
    },
    "creative arts": {
        "design": {
            "issue": "students produce ideas but do not explain creative choices clearly",
            "advice": "combine practical tasks with short reflection notes on colour, form, and purpose",
            "practice": ["design principles", "colour use", "artifact interpretation"],
        },
    },
    "religious & moral education": {
        "application": {
            "issue": "students recall stories but struggle to apply lessons to everyday life",
            "advice": "link each topic to modern school and community situations",
            "practice": ["moral lessons", "religious leadership", "values in daily life"],
        },
    },
}


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


def _normalize_practice_items(practice_items):
    if isinstance(practice_items, str):
        practice_items = [
            item.strip()
            for item in practice_items.replace("\n", ";").split(";")
            if item.strip()
        ]
    elif not isinstance(practice_items, (list, tuple, set)):
        practice_items = []

    normalized = []
    seen = set()
    for item in practice_items:
        label = str(item or "").strip()
        if not label:
            continue
        key = normalize_topic_key(label)
        if key in seen:
            continue
        normalized.append(label)
        seen.add(key)
    return normalized


def normalize_chief_examiner_library(library_payload):
    if not library_payload:
        return {}

    subjects_payload = library_payload
    if isinstance(library_payload, dict) and isinstance(library_payload.get("subjects"), list):
        subjects_payload = library_payload.get("subjects") or []

    normalized_library = {}

    if isinstance(subjects_payload, dict):
        subject_items = subjects_payload.items()
    elif isinstance(subjects_payload, list):
        subject_items = []
        for subject_entry in subjects_payload:
            if isinstance(subject_entry, dict):
                subject_name = subject_entry.get("subject") or subject_entry.get("name")
                subject_items.append((subject_name, subject_entry.get("topics") or subject_entry))
    else:
        return {}

    for subject_name, topics_payload in subject_items:
        subject_key = normalize_subject_key(subject_name)
        if not subject_key:
            continue

        normalized_topics = normalized_library.setdefault(subject_key, {})
        if isinstance(topics_payload, dict) and isinstance(topics_payload.get("topics"), list):
            topics_payload = topics_payload.get("topics")

        if isinstance(topics_payload, dict):
            topic_items = topics_payload.items()
        elif isinstance(topics_payload, list):
            topic_items = []
            for topic_entry in topics_payload:
                if isinstance(topic_entry, dict):
                    topic_items.append((topic_entry.get("topic") or topic_entry.get("name"), topic_entry))
        else:
            continue

        for topic_name, topic_entry in topic_items:
            topic_key = normalize_topic_key(topic_name)
            if not topic_key or not isinstance(topic_entry, dict):
                continue

            issue = str(topic_entry.get("issue") or "").strip()
            advice = str(topic_entry.get("advice") or topic_entry.get("recommendation") or "").strip()
            practice = _normalize_practice_items(topic_entry.get("practice") or topic_entry.get("practice_areas") or [])
            if not issue and not advice and not practice:
                continue

            normalized_topics[topic_key] = {
                "issue": issue,
                "advice": advice,
                "practice": practice,
            }

        if not normalized_topics:
            normalized_library.pop(subject_key, None)

    return normalized_library


def merge_chief_examiner_library(custom_library=None, base_library=None):
    seed_library = CHIEF_EXAMINER_INSIGHT_LIBRARY if base_library is None else base_library
    merged = normalize_chief_examiner_library(seed_library)
    overrides = normalize_chief_examiner_library(custom_library)
    for subject_key, topics in overrides.items():
        subject_topics = merged.setdefault(subject_key, {})
        for topic_key, entry in topics.items():
            subject_topics[topic_key] = {
                "issue": entry.get("issue") or "",
                "advice": entry.get("advice") or "",
                "practice": _normalize_practice_items(entry.get("practice") or []),
            }
    return merged


def match_chief_examiner_insight(subject_name: str | None, topic_name: str | None, chief_examiner_library=None):
    subject_key = normalize_subject_key(subject_name)
    topic_key = normalize_topic_key(topic_name)
    if not subject_key or not topic_key:
        return None

    topic_library = merge_chief_examiner_library(chief_examiner_library).get(subject_key, {})
    if topic_key in topic_library:
        return topic_library[topic_key]

    for candidate_key, entry in topic_library.items():
        if candidate_key in topic_key or topic_key in candidate_key:
            return entry
    return None


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
    chief_examiner_library=None,
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
            insight = match_chief_examiner_insight(
                subject_name,
                topic_name,
                chief_examiner_library=chief_examiner_library,
            )
            hotspots.append(
                {
                    "subject": subject_name,
                    "topic": topic_name,
                    "score": round(score, 1),
                    "max_score": round(max_score, 1),
                    "ratio": round(ratio * 100, 1),
                    "is_low": ratio <= threshold,
                    "chief_examiner_issue": insight.get("issue") if insight else None,
                    "advice": insight.get("advice") if insight else None,
                    "practice": insight.get("practice") if insight else [],
                }
            )
    hotspots.sort(key=lambda item: (not item["is_low"], item["ratio"], item["subject"], item["topic"]))
    return hotspots


def build_report_guidance_payload(
    subject_grades: Iterable[dict],
    allowed_subjects: Iterable[str] | None = None,
    chief_examiner_library=None,
):
    filtered_grades = filter_subject_grades(subject_grades, allowed_subjects=allowed_subjects)
    hotspots = [
        item
        for item in extract_diagnostic_hotspots(
            filtered_grades,
            chief_examiner_library=chief_examiner_library,
        )
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


def build_chief_examiner_library_payload(allowed_subjects: Iterable[str] | None = None, chief_examiner_library=None):
    allowed = {normalize_subject_key(subject) for subject in (allowed_subjects or []) if normalize_subject_key(subject)}
    payload = []
    for subject_name, topics in sorted(merge_chief_examiner_library(chief_examiner_library).items()):
        if allowed and subject_name not in allowed:
            continue
        payload.append(
            {
                "subject": subject_name.title() if subject_name != "ict" else "ICT",
                "topics": [
                    {
                        "topic": topic_name.title(),
                        "issue": entry.get("issue"),
                        "advice": entry.get("advice"),
                        "practice": entry.get("practice") or [],
                    }
                    for topic_name, entry in sorted(topics.items())
                ],
            }
        )
    return payload


def build_academic_guidance_summary(
    report_cards: Iterable,
    allowed_classes: Iterable[str] | None = None,
    allowed_subjects: Iterable[str] | None = None,
    chief_examiner_library=None,
):
    class_filter = {str(item).strip() for item in (allowed_classes or []) if str(item).strip()}
    hotspot_buckets = defaultdict(lambda: {"low_count": 0, "subject": None, "topic": None, "advice": None, "issue": None, "practice": set()})
    pathway_counter = Counter()
    pathway_scores = defaultdict(list)
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

        guidance = build_report_guidance_payload(
            filtered_grades,
            chief_examiner_library=chief_examiner_library,
        )
        for hotspot in guidance["diagnostic_hotspots"]:
            key = (normalize_subject_key(hotspot["subject"]), normalize_topic_key(hotspot["topic"]))
            bucket = hotspot_buckets[key]
            bucket["low_count"] += 1
            bucket["subject"] = hotspot["subject"]
            bucket["topic"] = hotspot["topic"]
            bucket["advice"] = hotspot.get("advice")
            bucket["issue"] = hotspot.get("chief_examiner_issue")
            for item in hotspot.get("practice") or []:
                bucket["practice"].add(item)

        if guidance["pathway_recommendations"]:
            top_pathway = guidance["pathway_recommendations"][0]
            pathway_counter[top_pathway["pathway"]] += 1
            pathway_scores[top_pathway["pathway"]].append(top_pathway["fit_score"])
            class_pathway_counter[class_name][top_pathway["pathway"]] += 1

    diagnostic_hotspots = []
    for bucket in hotspot_buckets.values():
        diagnostic_hotspots.append(
            {
                "subject": bucket["subject"],
                "topic": bucket["topic"],
                "low_report_count": bucket["low_count"],
                "advice": bucket["advice"],
                "chief_examiner_issue": bucket["issue"],
                "practice": sorted(bucket["practice"]),
            }
        )
    diagnostic_hotspots.sort(key=lambda item: (-item["low_report_count"], item["subject"], item["topic"]))

    pathway_distribution = [
        {
            "pathway": pathway,
            "student_count": count,
            "average_fit_score": round(sum(pathway_scores[pathway]) / len(pathway_scores[pathway]), 1) if pathway_scores[pathway] else 0.0,
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