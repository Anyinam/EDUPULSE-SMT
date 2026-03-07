"""
AI-Powered Lesson Note Scoring & Analysis
Provides sophisticated quality assessment for lesson notes
"""

import os
from typing import Dict, List, Tuple


def calculate_completeness_score(note_data: Dict) -> Tuple[int, List[str]]:
    """
    Calculate completeness score based on required fields.
    Returns: (score, list of feedback points)
    """
    score = 0
    feedback = []
    max_score = 100
    
    # Required core fields (40 points)
    core_fields = {
        'indicator_code': 8,
        'content_standard_code': 8,
        'performance_indicator': 8,
        'subject': 4,
        'class_name': 4,
        'lesson_dates': 4,
        'class_size': 4,
    }
    
    for field, points in core_fields.items():
        value = note_data.get(field)
        if isinstance(value, list):
            has_value = len(value) > 0
        elif isinstance(value, (int, float)):
            has_value = value > 0
        else:
            has_value = bool(str(value or '').strip())
        if has_value:
            score += points
        else:
            feedback.append(f"⚠️ Missing {field.replace('_', ' ').title()}")
    
    # Supporting fields (30 points)
    supporting_fields = {
        'core_competencies': 10,
        'key_words': 5,
        'teaching_learning_resources': 10,
        'references': 5
    }
    
    for field, points in supporting_fields.items():
        value = note_data.get(field, '').strip()
        if value and len(value) > 10:
            score += points
            if len(value) > 50:
                feedback.append(f"✅ Good detail in {field.replace('_', ' ')}")
        elif value:
            score += points // 2
            feedback.append(f"⚠️ {field.replace('_', ' ').title()} needs more detail")
        else:
            feedback.append(f"❌ Missing {field.replace('_', ' ')}")
    
    # Daily phases (30 points)
    daily_phases = note_data.get('daily_phases', [])
    if daily_phases and len(daily_phases) > 0:
        phases_score = 0
        phases_complete = 0
        
        for phase in daily_phases:
            if isinstance(phase, dict):
                # Check all three phases are filled
                p1 = phase.get('phase_1_starter', '').strip()
                p2 = phase.get('phase_2_main', '').strip()
                p3 = phase.get('phase_3_plenary', '').strip()
                
                if p1 and p2 and p3:
                    phases_complete += 1
                    # Quality check - each phase should be substantial
                    if len(p1) > 20 and len(p2) > 30 and len(p3) > 20:
                        phases_score += 10
                    else:
                        phases_score += 5
        
        score += min(30, phases_score)
        
        if phases_complete >= 3:
            feedback.append(f"✅ Excellent: {phases_complete} complete daily phases")
        elif phases_complete >= 1:
            feedback.append(f"✓ Good: {phases_complete} daily phase(s), consider adding more")
        else:
            feedback.append("⚠️ Daily phases need more detail")
    else:
        feedback.append("❌ No daily lesson phases provided")
    
    return score, feedback


def calculate_pedagogical_quality(note_data: Dict) -> Tuple[int, List[str]]:
    """
    Assess pedagogical quality and teaching methodology.
    Returns: (score, list of feedback points)
    """
    score = 0
    feedback = []
    
    performance_indicator = note_data.get('performance_indicator', '').lower()
    core_competencies = note_data.get('core_competencies', '').lower()
    daily_phases = note_data.get('daily_phases', [])
    
    # Check for action verbs in performance indicators (20 points)
    action_verbs = [
        'analyze', 'apply', 'assess', 'calculate', 'compare', 'create',
        'demonstrate', 'describe', 'develop', 'evaluate', 'explain',
        'identify', 'interpret', 'investigate', 'solve', 'understand'
    ]
    
    verbs_found = [verb for verb in action_verbs if verb in performance_indicator]
    if len(verbs_found) >= 2:
        score += 20
        feedback.append(f"✅ Strong performance indicators with clear action verbs")
    elif len(verbs_found) == 1:
        score += 10
        feedback.append(f"✓ Performance indicator present, consider adding more specific verbs")
    else:
        feedback.append("⚠️ Performance indicator should include clear action verbs (analyze, apply, etc.)")
    
    # Check for competency variety (20 points)
    competency_keywords = [
        'problem solving', 'critical thinking', 'communication', 'collaboration',
        'creativity', 'digital literacy', 'cultural identity', 'global citizenship'
    ]
    
    competencies_found = [kw for kw in competency_keywords if kw in core_competencies]
    if len(competencies_found) >= 3:
        score += 20
        feedback.append(f"✅ Diverse core competencies addressed ({len(competencies_found)} identified)")
    elif len(competencies_found) >= 1:
        score += 10
        feedback.append(f"✓ Core competencies identified, consider adding more variety")
    else:
        feedback.append("⚠️ Core competencies should include problem solving, critical thinking, etc.")
    
    # Check phase structure (30 points)
    if daily_phases:
        structure_score = 0
        
        for phase in daily_phases:
            if isinstance(phase, dict):
                starter = phase.get('phase_1_starter', '').lower()
                main = phase.get('phase_2_main', '').lower()
                plenary = phase.get('phase_3_plenary', '').lower()
                
                # Starter quality
                starter_keywords = ['review', 'recap', 'question', 'discuss', 'brainstorm', 'warm up']
                if any(kw in starter for kw in starter_keywords):
                    structure_score += 3
                
                # Main activity quality
                main_keywords = ['practice', 'activity', 'exercise', 'group work', 'investigation', 'demonstration']
                if any(kw in main for kw in main_keywords):
                    structure_score += 4
                
                # Plenary quality
                plenary_keywords = ['summary', 'reflect', 'assess', 'review', 'evaluate', 'conclude']
                if any(kw in plenary for kw in plenary_keywords):
                    structure_score += 3
        
        score += min(30, structure_score)
        
        if structure_score >= 20:
            feedback.append("✅ Excellent lesson structure with clear phases")
        elif structure_score >= 10:
            feedback.append("✓ Good lesson structure, ensure starters/plenaries are engaging")
        else:
            feedback.append("⚠️ Lesson phases need clearer structure (starter → main → plenary)")
    
    # Check for differentiation/inclusion (15 points)
    content = str(note_data).lower()
    differentiation_keywords = ['differentiat', 'support', 'challenge', 'extension', 'scaffold', 'mixed ability']
    if any(kw in content for kw in differentiation_keywords):
        score += 15
        feedback.append("✅ Evidence of differentiation/support for diverse learners")
    else:
        feedback.append("💡 Consider adding differentiation strategies for mixed-ability classes")
    
    # Check for assessment integration (15 points)
    assessment_keywords = ['assess', 'evaluate', 'check understanding', 'formative', 'quiz', 'question']
    if any(kw in content for kw in assessment_keywords):
        score += 15
        feedback.append("✅ Assessment strategies integrated")
    else:
        feedback.append("💡 Consider adding assessment/checking for understanding")
    
    return score, feedback


def calculate_content_quality(note_data: Dict) -> Tuple[int, List[str]]:
    """
    Assess content depth and resource quality.
    Returns: (score, list of feedback points)
    """
    score = 0
    feedback = []
    
    # Teaching resources quality (40 points)
    resources = note_data.get('teaching_learning_resources', '')
    if resources:
        resource_count = len(resources.split(','))
        if resource_count >= 4:
            score += 20
            feedback.append(f"✅ Rich variety of resources ({resource_count} listed)")
        elif resource_count >= 2:
            score += 15
            feedback.append(f"✓ Multiple resources listed, consider adding more variety")
        else:
            score += 5
        
        # Check for resource quality
        quality_resources = [
            'manipulative', 'visual', 'concrete', 'technology', 'real-world',
            'model', 'chart', 'diagram', 'interactive'
        ]
        if any(qr in resources.lower() for qr in quality_resources):
            score += 20
            feedback.append("✅ Quality resources including hands-on/visual materials")
        else:
            score += 10
            feedback.append("💡 Consider adding manipulatives, visuals, or interactive resources")
    else:
        feedback.append("❌ Teaching resources not specified")
    
    # References quality (30 points)
    references = note_data.get('references', '')
    if references:
        ref_length = len(references)
        if ref_length > 100:
            score += 30
            feedback.append("✅ Comprehensive references with curriculum alignment")
        elif ref_length > 30:
            score += 20
            feedback.append("✓ References provided, ensure curriculum page numbers included")
        else:
            score += 10
            feedback.append("⚠️ References need more detail (curriculum pages, textbook chapters)")
    else:
        feedback.append("⚠️ No references to curriculum or textbooks")
    
    # Keywords quality (30 points)
    keywords = note_data.get('key_words', '')
    if keywords:
        keyword_list = [k.strip() for k in keywords.split(',')]
        if len(keyword_list) >= 5:
            score += 30
            feedback.append(f"✅ Rich vocabulary with {len(keyword_list)} key terms")
        elif len(keyword_list) >= 3:
            score += 20
            feedback.append(f"✓ Key words identified, consider adding more subject-specific terms")
        else:
            score += 10
    else:
        feedback.append("⚠️ Key vocabulary/terminology not identified")
    
    return score, feedback


def generate_ai_lesson_note_score(note_data: Dict) -> Dict:
    """
    Generate comprehensive AI score and feedback for a lesson note.
    
    Args:
        note_data: Dictionary containing lesson note fields
        
    Returns:
        Dictionary with:
        - ai_score: Overall score (0-100)
        - ai_feedback: Detailed feedback text
        - breakdown: Dict with category scores
    """
    
    # Calculate component scores
    completeness_score, completeness_feedback = calculate_completeness_score(note_data)
    pedagogical_score, pedagogical_feedback = calculate_pedagogical_quality(note_data)
    content_score, content_feedback = calculate_content_quality(note_data)
    
    # Weighted average (adjust weights as needed)
    overall_score = int(
        (completeness_score * 0.35) +  # 35% - Having all required fields
        (pedagogical_score * 0.40) +    # 40% - Teaching quality
        (content_score * 0.25)          # 25% - Resource quality
    )
    
    # Generate comprehensive feedback
    feedback_sections = []
    
    # Overall assessment
    if overall_score >= 85:
        feedback_sections.append("🌟 EXCELLENT - Outstanding lesson plan with strong pedagogical approach")
    elif overall_score >= 70:
        feedback_sections.append("✅ GOOD - Solid lesson plan with clear objectives and structure")
    elif overall_score >= 55:
        feedback_sections.append("✓ SATISFACTORY - Adequate lesson plan with room for enhancement")
    else:
        feedback_sections.append("⚠️ NEEDS IMPROVEMENT - Lesson plan requires significant development")
    
    # Add category breakdowns
    feedback_sections.append(f"\n📋 COMPLETENESS: {completeness_score}/100")
    feedback_sections.extend([f"  {f}" for f in completeness_feedback])
    
    feedback_sections.append(f"\n🎓 PEDAGOGICAL QUALITY: {pedagogical_score}/100")
    feedback_sections.extend([f"  {f}" for f in pedagogical_feedback])
    
    feedback_sections.append(f"\n📚 CONTENT & RESOURCES: {content_score}/100")
    feedback_sections.extend([f"  {f}" for f in content_feedback])
    
    # Recommendations
    feedback_sections.append("\n💡 RECOMMENDATIONS:")
    recommendations = []
    
    if completeness_score < 80:
        recommendations.append("  • Complete all required fields for comprehensive planning")
    if pedagogical_score < 70:
        recommendations.append("  • Strengthen learning activities with varied teaching strategies")
        recommendations.append("  • Include formative assessment throughout the lesson")
    if content_score < 70:
        recommendations.append("  • Add more diverse teaching resources")
        recommendations.append("  • Include specific curriculum page references")
    
    if not recommendations:
        recommendations.append("  • Continue this excellent standard of lesson planning")
        recommendations.append("  • Share best practices with colleagues")
    
    feedback_sections.extend(recommendations)
    
    # Combine all feedback
    detailed_feedback = "\n".join(feedback_sections)
    
    return {
        'ai_score': overall_score,
        'ai_feedback': detailed_feedback,
        'breakdown': {
            'completeness': completeness_score,
            'pedagogical': pedagogical_score,
            'content': content_score
        }
    }


def generate_quick_feedback(score: int) -> str:
    """Generate a quick summary feedback based on score."""
    if score >= 85:
        return "Outstanding lesson plan! Exemplary pedagogical approach and comprehensive planning."
    elif score >= 70:
        return "Good lesson plan with clear structure and objectives. Minor enhancements suggested."
    elif score >= 55:
        return "Satisfactory lesson plan. Review feedback for areas of improvement."
    else:
        return "Lesson plan needs significant development. Please address feedback points."
