import React, { useState, useEffect } from 'react';
import axios from 'axios';
import TimetableManager from '../components/TimetableManager';
import TeacherAlerts from '../components/TeacherAlerts';
import AcademicGuidancePanel from '../components/AcademicGuidancePanel';
import { useBranding } from '../hooks/useBranding';
import useSchoolClasses from '../hooks/useSchoolClasses';
import useSubscription from '../hooks/useSubscription';
import FeatureLock from '../components/FeatureLock';

export default function TeacherDashboard() {
  const [students, setStudents] = useState([]);
  const [selectedStudentId, setSelectedStudentId] = useState('');
  const [studentLoadError, setStudentLoadError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [lessonNoteData, setLessonNoteData] = useState({
    week_number: 1,
    class_name: '',
    subject: 'Mathematics',
    lesson_dates: [],
    class_size: '',
    indicator_code: '',
    content_standard_code: '',
    performance_indicator: '',
    core_competencies: '',
    key_words: '',
    teaching_learning_resources: '',
    references: ''
  });
  const [dailyPhases, setDailyPhases] = useState([
    { day: 'Monday', phase_1_starter: '', phase_2_main: '', phase_3_plenary: '' }
  ]);
  const [lessonDateInput, setLessonDateInput] = useState('');
  const [selectedClass, setSelectedClass] = useState('');
  const [selectedSubject, setSelectedSubject] = useState("Mathematics");
  const [lessonNoteSubject, setLessonNoteSubject] = useState("Mathematics");
  const [subjects, setSubjects] = useState([]);
  const [assignedSubjects, setAssignedSubjects] = useState([]);
  const [assignedClasses, setAssignedClasses] = useState([]);
  const [timetableEntries, setTimetableEntries] = useState([]);
  const [useTimetable, setUseTimetable] = useState(false);
  const [classScoreMax, setClassScoreMax] = useState(30);
  const [examScoreMax, setExamScoreMax] = useState(70);
  const [activeTab, setActiveTab] = useState('grades'); // 'grades' or 'lesson-notes'
  const [myLessonNotes, setMyLessonNotes] = useState([]);
  const [hasHeadmaster, setHasHeadmaster] = useState(true);
  const [selectedNote, setSelectedNote] = useState(null);
  const [feedbackModal, setFeedbackModal] = useState(false);
  const [feedbackNote, setFeedbackNote] = useState(null);
  const [examSubjectSummary, setExamSubjectSummary] = useState(null);
  const [examSubjectSummaryError, setExamSubjectSummaryError] = useState('');
  const { branding } = useBranding();
  const { classes: schoolClasses } = useSchoolClasses();
  const { hasFeature } = useSubscription();
  const canEnterGrades = hasFeature('grade_entry');

  const createEmptyDiagnosticTopic = () => ({ topic: '', score: '', max_score: '' });

  // Helper to get auth headers
  const getAuthHeaders = () => ({
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  // Fetch students for the selected class
  useEffect(() => {
    const fetchStudents = async () => {
      try {
        if (!selectedClass) {
          setStudents([]);
          setSelectedStudentId('');
          setStudentLoadError(null);
          return;
        }
        const encodedClass = encodeURIComponent(selectedClass);
        const res = await axios.get(`/api/students/by-class/${encodedClass}`, getAuthHeaders());
        // Initialize with empty scores for class work and exam
        setStudents(res.data.map(s => ({ ...s, class_score: '', exam_score: '', diagnostic_topics: [] })));
        setStudentLoadError(null);
      } catch (err) {
        console.error("Failed to fetch students:", err);
        const errorMsg = err.response?.data?.message || err.message || 'Failed to load students';
        setStudentLoadError(errorMsg);
        setStudents([]);
        setSelectedStudentId('');
      }
    };
    fetchStudents();
  }, [selectedClass]);

  useEffect(() => {
    if (students.length === 0) {
      setSelectedStudentId('');
      return;
    }

    const hasSelectedStudent = students.some((student) => String(student.id) === String(selectedStudentId));
    if (!hasSelectedStudent) {
      setSelectedStudentId(String(students[0].id));
    }
  }, [students, selectedStudentId]);

  // Fetch grading scheme
  useEffect(() => {
    const fetchGradingScheme = async () => {
      try {
        const res = await axios.get('/api/school/grading-scheme', getAuthHeaders());
        setClassScoreMax(res.data.class_score_max);
        setExamScoreMax(res.data.exam_score_max);
      } catch (err) {
        console.error("Failed to load grading scheme", err);
      }
    };
    fetchGradingScheme();
  }, []);

  // Fetch subject list
  useEffect(() => {
    const fetchSubjects = async () => {
      try {
        const assignmentsRes = await axios.get('/api/teacher/assignments', getAuthHeaders());
        const assigned = Array.isArray(assignmentsRes.data?.assigned_subjects)
          ? assignmentsRes.data.assigned_subjects
          : [];

        if (assigned.length > 0) {
          setAssignedSubjects(assigned);
          setSubjects(assigned);
          if (!assigned.includes(selectedSubject)) {
            setSelectedSubject(assigned[0]);
          }
          return;
        }

        const res = await axios.get('/api/school/subjects', getAuthHeaders());
        const list = Array.isArray(res.data) ? res.data : [];
        setAssignedSubjects([]);
        setSubjects(list);
        if (list.length > 0 && !list.includes(selectedSubject)) {
          setSelectedSubject(list[0]);
        }
      } catch (err) {
        console.error("Failed to load subjects", err);
      }
    };
    fetchSubjects();
  }, []);

  useEffect(() => {
    const fetchClasses = async () => {
      try {
        // First, try to get teacher's assigned classes from assignments
        const assignmentsRes = await axios.get('/api/teacher/assignments', getAuthHeaders());
        const assignedClasses = Array.isArray(assignmentsRes.data?.assigned_classes)
          ? assignmentsRes.data.assigned_classes
          : [];

        // If teacher has assigned classes, use only those
        if (assignedClasses.length > 0) {
          setAssignedClasses(assignedClasses);
          return;
        }

        setAssignedClasses([]);
      } catch (err) {
        console.error('Failed to load classes', err);
        setAssignedClasses([]);
      }
    };
    fetchClasses();
  }, []);

  const classOptions = assignedClasses.length > 0 ? assignedClasses : schoolClasses;

  useEffect(() => {
    if (classOptions.length === 0) {
      if (selectedClass) {
        setSelectedClass('');
      }
      return;
    }

    if (!classOptions.includes(selectedClass)) {
      setSelectedClass(classOptions[0]);
    }
  }, [classOptions, selectedClass]);

  useEffect(() => {
    const fetchTimetable = async () => {
      try {
        const res = await axios.get('/api/timetable/my', getAuthHeaders());
        const entries = Array.isArray(res.data) ? res.data : [];
        setTimetableEntries(entries);
        if (entries.length > 0) {
          setUseTimetable(true);
        } else {
          setUseTimetable(false);
        }
      } catch (err) {
        console.error('Failed to load timetable', err);
        setUseTimetable(false);
      }
    };
    fetchTimetable();
  }, []);

  const timetableSubjects = useTimetable
    ? Array.from(new Set(
        timetableEntries
          .filter((entry) => entry.class_name === selectedClass)
          .map((entry) => entry.subject_name)
      ))
    : [];

  const allowedSubjects = assignedSubjects.length > 0 ? assignedSubjects : subjects;

  const gradeSubjectOptions = useTimetable
    ? timetableSubjects.filter((subject) => allowedSubjects.includes(subject))
    : allowedSubjects;

  const selectedStudent = students.find((student) => String(student.id) === String(selectedStudentId)) || null;
  const completedStudentCount = students.filter((student) => (
    student.class_score !== ''
    && student.class_score !== undefined
    && student.exam_score !== ''
    && student.exam_score !== undefined
  )).length;

  const lessonNoteSubjectOptions = useTimetable
    ? timetableSubjects.filter((subject) => allowedSubjects.includes(subject))
    : allowedSubjects;

  useEffect(() => {
    if (gradeSubjectOptions.length > 0 && !gradeSubjectOptions.includes(selectedSubject)) {
      setSelectedSubject(gradeSubjectOptions[0]);
    }
  }, [useTimetable, selectedClass, timetableEntries, assignedSubjects, subjects, selectedSubject]);

  useEffect(() => {
    if (lessonNoteSubjectOptions.length > 0 && !lessonNoteSubjectOptions.includes(lessonNoteSubject)) {
      setLessonNoteSubject(lessonNoteSubjectOptions[0]);
    }
  }, [useTimetable, timetableSubjects, subjects, lessonNoteSubject]);

  useEffect(() => {
    setLessonNoteData((prev) => ({
      ...prev,
      class_name: selectedClass
    }));
  }, [selectedClass]);

  useEffect(() => {
    setLessonNoteData((prev) => ({
      ...prev,
      subject: lessonNoteSubject
    }));
  }, [lessonNoteSubject]);

  // Fetch teacher's own lesson notes
  useEffect(() => {
    const fetchMyLessonNotes = async () => {
      try {
        const res = await axios.get('/api/staff/my-lesson-notes', getAuthHeaders());
        setMyLessonNotes(Array.isArray(res.data) ? res.data : []);
      } catch (err) {
        console.error('Failed to fetch lesson notes', err);
      }
    };
    fetchMyLessonNotes();
  }, []);

  // Check if headmaster exists
  useEffect(() => {
    const checkHeadmaster = async () => {
      try {
        const res = await axios.get('/api/staff/check-headmaster', getAuthHeaders());
        setHasHeadmaster(res.data.has_headmaster || false);
      } catch (err) {
        console.error('Failed to check headmaster', err);
        setHasHeadmaster(false);
      }
    };
    checkHeadmaster();
  }, []);

  useEffect(() => {
    const fetchExamSubjectSummary = async () => {
      try {
        const res = await axios.get('/api/analytics/exam-intelligence', getAuthHeaders());
        if (res.data?.view_scope === 'teacher_subject_summary') {
          setExamSubjectSummary(res.data);
          setExamSubjectSummaryError('');
        } else {
          setExamSubjectSummary(null);
          setExamSubjectSummaryError('');
        }
      } catch (err) {
        const status = err.response?.status;
        if (status === 403 || status === 404) {
          setExamSubjectSummary(null);
          setExamSubjectSummaryError('');
          return;
        }
        console.error('Failed to load teacher exam subject summary', err);
        setExamSubjectSummary(null);
        setExamSubjectSummaryError(err.response?.data?.message || 'Failed to load subject-level exam summaries.');
      }
    };
    fetchExamSubjectSummary();
  }, []);

  const updateLessonField = (field, value) => {
    setLessonNoteData((prev) => ({ ...prev, [field]: value }));
  };

  const updatePhaseField = (index, field, value) => {
    setDailyPhases((prev) => prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  };

  const addPhaseRow = () => {
    setDailyPhases((prev) => ([
      ...prev,
      { day: '', phase_1_starter: '', phase_2_main: '', phase_3_plenary: '' }
    ]));
  };

  const removePhaseRow = (index) => {
    setDailyPhases((prev) => prev.filter((_, i) => i !== index));
  };

  const handleClassAssignmentChange = (id, score) => {
    const numericScore = parseFloat(score);
    
    // Validate against maximum
    if (numericScore > classScoreMax) {
      alert(`Class score cannot exceed ${classScoreMax}. Please enter a valid score.`);
      return;
    }
    
    // Validate non-negative
    if (numericScore < 0) {
      alert('Score cannot be negative.');
      return;
    }
    
    setStudents(prev => prev.map(s => s.id === id ? { ...s, class_score: score === '' ? '' : numericScore } : s));
  };

  const handleExamScoreChange = (id, score) => {
    const numericScore = parseFloat(score);
    
    // Validate against maximum
    if (numericScore > examScoreMax) {
      alert(`Exam score cannot exceed ${examScoreMax}. Please enter a valid score.`);
      return;
    }
    
    // Validate non-negative
    if (numericScore < 0) {
      alert('Score cannot be negative.');
      return;
    }
    
    setStudents(prev => prev.map(s => s.id === id ? { ...s, exam_score: score === '' ? '' : numericScore } : s));
  };

  const handleDiagnosticTopicChange = (studentId, topicIndex, field, value) => {
    setStudents((prev) => prev.map((student) => {
      if (student.id !== studentId) {
        return student;
      }
      const diagnosticTopics = Array.isArray(student.diagnostic_topics)
        ? [...student.diagnostic_topics]
        : [];
      diagnosticTopics[topicIndex] = {
        ...diagnosticTopics[topicIndex],
        [field]: value,
      };
      return { ...student, diagnostic_topics: diagnosticTopics };
    }));
  };

  const addDiagnosticTopic = (studentId) => {
    setStudents((prev) => prev.map((student) => {
      if (student.id !== studentId) {
        return student;
      }
      const diagnosticTopics = Array.isArray(student.diagnostic_topics)
        ? [...student.diagnostic_topics]
        : [];
      diagnosticTopics.push(createEmptyDiagnosticTopic());
      return { ...student, diagnostic_topics: diagnosticTopics };
    }));
  };

  const removeDiagnosticTopic = (studentId, topicIndex) => {
    setStudents((prev) => prev.map((student) => {
      if (student.id !== studentId) {
        return student;
      }
      const diagnosticTopics = Array.isArray(student.diagnostic_topics)
        ? student.diagnostic_topics.filter((_, index) => index !== topicIndex)
        : [];
      return { ...student, diagnostic_topics: diagnosticTopics };
    }));
  };

  const handleSave = async () => {
    if (!canEnterGrades) return;
    if (students.length === 0) {
      return alert('No students found for the selected class.');
    }
    // Validate that all students have both scores
    for (const s of students) {
      if (s.class_score === undefined || s.exam_score === undefined || 
          s.class_score === '' || s.exam_score === '') {
        return alert(`Please enter both class assignment and exam scores for ${s.name}`);
      }
      
      // Additional validation for max values
      const classScore = parseFloat(s.class_score);
      const examScore = parseFloat(s.exam_score);
      
      if (classScore > classScoreMax) {
        return alert(`${s.name}: Class score (${classScore}) exceeds maximum allowed (${classScoreMax})`);
      }
      
      if (examScore > examScoreMax) {
        return alert(`${s.name}: Exam score (${examScore}) exceeds maximum allowed (${examScoreMax})`);
      }
      
      if (classScore < 0 || examScore < 0) {
        return alert(`${s.name}: Scores cannot be negative`);
      }
    }

    const gradeData = {};
    students.forEach(s => {
      gradeData[s.id] = {
        class_score: parseFloat(s.class_score),
        exam_score: parseFloat(s.exam_score),
        diagnostic_topics: Array.isArray(s.diagnostic_topics) ? s.diagnostic_topics : []
      };
    });

    try {
      await axios.post('/api/teacher/submit-grades-to-homeroom', {
        class_name: selectedClass,
        subject: selectedSubject,
        grade_data: gradeData
      }, getAuthHeaders());
      alert("Grades submitted to homeroom teacher successfully!");
    } catch (err) {
      alert("Error saving records: " + (err.response?.data?.message || err.message));
    }
  };

  const handleSubmitLessonNote = async (submitTo = 'headmaster') => {
    if (!lessonNoteData.week_number || !lessonNoteData.subject || !lessonNoteData.class_name) {
      return alert('Please provide week, subject, and class for the lesson note.');
    }
    if (!lessonNoteData.lesson_dates || lessonNoteData.lesson_dates.length === 0) {
      return alert('Please add at least one lesson date.');
    }
    if (!lessonNoteData.indicator_code || !lessonNoteData.content_standard_code) {
      return alert('Please provide the indicator code and content standard code.');
    }
    if (!lessonNoteData.performance_indicator.trim()) {
      return alert('Please provide the performance indicator.');
    }
    if (dailyPhases.length === 0) {
      return alert('Please add at least one day with lesson phases.');
    }
    const hasInvalidPhase = dailyPhases.some((row) => (
      !row.day || !row.phase_1_starter.trim() || !row.phase_2_main.trim() || !row.phase_3_plenary.trim()
    ));
    if (hasInvalidPhase) {
      return alert('Please complete all phase fields for each day.');
    }

    try {
      const res = await axios.post('/api/staff/lesson-note', {
        week_number: parseInt(lessonNoteData.week_number, 10),
        subject: lessonNoteData.subject,
        class_name: lessonNoteData.class_name,
        lesson_dates: lessonNoteData.lesson_dates,
        class_size: lessonNoteData.class_size ? parseInt(lessonNoteData.class_size, 10) : null,
        indicator_code: lessonNoteData.indicator_code,
        content_standard_code: lessonNoteData.content_standard_code,
        performance_indicator: lessonNoteData.performance_indicator,
        core_competencies: lessonNoteData.core_competencies,
        key_words: lessonNoteData.key_words,
        teaching_learning_resources: lessonNoteData.teaching_learning_resources,
        references: lessonNoteData.references,
        daily_phases: dailyPhases,
        submit_to: submitTo
      }, getAuthHeaders());
      
      alert(`Note Submitted to ${submitTo === 'headmaster' ? 'Headmaster' : 'Proprietor'}! AI Score: ${res.data.ai_score}/100\nFeedback: ${res.data.feedback}`);
      
      // Refresh lesson notes list
      const notesRes = await axios.get('/api/staff/my-lesson-notes', getAuthHeaders());
      setMyLessonNotes(Array.isArray(notesRes.data) ? notesRes.data : []);
      setLessonNoteData((prev) => ({
        ...prev,
        lesson_dates: [],
        class_size: '',
        indicator_code: '',
        content_standard_code: '',
        performance_indicator: '',
        core_competencies: '',
        key_words: '',
        teaching_learning_resources: '',
        references: ''
      }));
      setLessonDateInput('');
      setDailyPhases([{ day: 'Monday', phase_1_starter: '', phase_2_main: '', phase_3_plenary: '' }]);
    } catch (err) {
      console.error("Error submitting lesson note:", err);
      const errorMsg = err.response?.data?.message || err.message || "Failed to submit note.";
      alert(`Failed to submit note: ${errorMsg}`);
    }
  };

  const handlePrintLessonNote = (note) => {
    const printWindow = window.open('', '_blank');
    const lessonDates = Array.isArray(note.lesson_dates) ? note.lesson_dates : [];
    const phasesHtml = note.daily_phases.map(phase => `
      <div style="margin-bottom: 20px; border: 1px solid #e0e0e0; padding: 10px; border-radius: 5px;">
        <h4 style="color: #1e40af; margin: 0 0 10px 0;">${phase.day}</h4>
        <p><strong>Phase 1 - Starter:</strong> ${phase.phase_1_starter}</p>
        <p><strong>Phase 2 - Main Activity:</strong> ${phase.phase_2_main}</p>
        <p><strong>Phase 3 - Plenary:</strong> ${phase.phase_3_plenary}</p>
      </div>
    `).join('');

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Lesson Note - Week ${note.week_number}</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 40px; line-height: 1.6; }
          h1 { color: #1e40af; border-bottom: 3px solid #1e40af; padding-bottom: 10px; }
          h2 { color: #3b82f6; margin-top: 30px; }
          .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }
          .info-item { background: #f3f4f6; padding: 10px; border-radius: 5px; }
          .info-label { font-weight: bold; color: #374151; }
          .section { margin: 20px 0; padding: 15px; background: #f9fafb; border-left: 4px solid #3b82f6; }
          .ai-score { background: #dbeafe; padding: 15px; border-radius: 8px; margin: 20px 0; }
          @media print { button { display: none; } }
        </style>
      </head>
      <body>
        <h1>${branding.name || 'EduPulse SMT'} - Lesson Note</h1>
        
        <div class="info-grid">
          <div class="info-item"><span class="info-label">Week:</span> ${note.week_number}</div>
          <div class="info-item"><span class="info-label">Subject:</span> ${note.subject}</div>
          <div class="info-item"><span class="info-label">Class:</span> ${note.class_name}</div>
          <div class="info-item"><span class="info-label">Class Size:</span> ${note.class_size || 'N/A'}</div>
          <div class="info-item"><span class="info-label">Lesson Dates:</span> ${lessonDates.length ? lessonDates.join(', ') : 'N/A'}</div>
          <div class="info-item"><span class="info-label">Status:</span> ${note.status}</div>
        </div>

        <div class="section">
          <p><span class="info-label">Indicator Code:</span> ${note.indicator_code}</p>
          <p><span class="info-label">Content Standard Code:</span> ${note.content_standard_code}</p>
        </div>

        <div class="section">
          <h3>Performance Indicator</h3>
          <p>${note.performance_indicator}</p>
        </div>

        ${note.core_competencies ? `
          <div class="section">
            <h3>Core Competencies</h3>
            <p>${note.core_competencies}</p>
          </div>
        ` : ''}

        ${note.key_words ? `
          <div class="section">
            <h3>Key Words</h3>
            <p>${note.key_words}</p>
          </div>
        ` : ''}

        ${note.teaching_learning_resources ? `
          <div class="section">
            <h3>Teaching & Learning Resources</h3>
            <p>${note.teaching_learning_resources}</p>
          </div>
        ` : ''}

        ${note.references ? `
          <div class="section">
            <h3>References</h3>
            <p>${note.references}</p>
          </div>
        ` : ''}

        <h2>Daily Lesson Phases</h2>
        ${phasesHtml}

        <div class="ai-score">
          <h3 style="margin-top: 0;">AI Assessment</h3>
          <p><strong>Score:</strong> ${note.ai_score}/100</p>
          <p><strong>Feedback:</strong> ${note.ai_feedback}</p>
        </div>

        <p style="text-align: center; color: #6b7280; margin-top: 40px; font-size: 12px;">
          Generated on ${new Date().toLocaleDateString()} at ${new Date().toLocaleTimeString()}<br/>
          Submitted to: ${note.submit_to === 'headmaster' ? 'Headmaster' : 'Proprietor'}
        </p>

        <button onclick="window.print()" style="display: block; margin: 20px auto; padding: 10px 30px; background: #3b82f6; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">
          Print Lesson Note
        </button>
      </body>
      </html>
    `);
    printWindow.document.close();
  };

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-cca-blue">Subject Teacher Dashboard</h1>
        <p className="text-gray-600">{branding.name || 'EduPulse SMT'} - Grade Entry</p>
      </header>

      {notice && (
        <div className="bg-blue-600 text-white p-4 rounded-xl mb-6 animate-bounce shadow-lg flex items-center gap-3">
          <span>📢</span>
          <div>
            <p className="text-xs font-bold uppercase opacity-80">Message from Proprietor</p>
            <p className="font-bold">{notice.details}</p>
          </div>
        </div>
      )}
      <div className="mb-8">
        <TimetableManager title="My Teaching Schedule" scope="mine" canManage={false} />
      </div>

      {/* Teacher Alerts - Promotion & Repetition Notifications */}
      <div className="mb-8">
        <TeacherAlerts />
      </div>

      {examSubjectSummary && (
        <div className="mb-8 rounded-xl border border-emerald-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-700">Exam Subject Summary</p>
              <h2 className="mt-2 text-2xl font-bold text-gray-800">My Subject-Level BECE and WAEC Signals</h2>
              <p className="mt-2 text-sm text-gray-600">
                These summaries are shown automatically for your assigned subjects only. Raw candidate-level exam records remain restricted to school leadership.
              </p>
            </div>
            <div className="rounded-xl bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-800">
              {examSubjectSummary.summary?.latest_academic_year || 'No latest year yet'}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {(examSubjectSummary.assigned_subjects || []).map((subject) => (
              <span key={subject} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
                {subject}
              </span>
            ))}
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl bg-slate-900 p-4 text-white">
              <p className="text-xs uppercase tracking-wide text-slate-300">Tracked Subjects</p>
              <p className="mt-2 text-3xl font-black">{examSubjectSummary.summary?.tracked_subjects || 0}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Latest Subject Count</p>
              <p className="mt-2 text-3xl font-black text-slate-900">{examSubjectSummary.summary?.latest_subject_count || 0}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-4 md:col-span-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Assigned Classes</p>
              <p className="mt-2 text-sm font-bold text-slate-900">{(examSubjectSummary.assigned_classes || []).join(', ') || 'No class assignment recorded'}</p>
            </div>
          </div>

          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
            <p className="font-bold text-slate-800">Class-level summary setting</p>
            <p className="mt-1">
              {examSubjectSummary.class_level_summaries_enabled
                ? 'Your school has enabled class-level teacher summaries. Only assigned classes and assigned subjects are shown below when matching student records are available.'
                : 'Your school has not enabled class-level teacher summaries. You are currently limited to automatic subject-level summaries only.'}
            </p>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
            <div className="rounded-xl border border-slate-200 p-4">
              <h3 className="text-sm font-bold uppercase tracking-wide text-slate-700">Latest Subject Snapshot</h3>
              <div className="mt-4 space-y-3">
                {(examSubjectSummary.latest_batch?.subject_summaries || []).length === 0 ? (
                  <p className="text-sm text-slate-500">No subject-level exam summary is available yet for your assignments.</p>
                ) : (
                  examSubjectSummary.latest_batch.subject_summaries.map((item) => (
                    <div key={item.subject} className="rounded-lg bg-slate-50 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-bold text-slate-800">{item.subject}</p>
                        <span className="text-xs font-bold text-slate-500">{item.entries} entries</span>
                      </div>
                      <p className="mt-2 text-xs text-slate-600">Average {Number(item.average_score || 0).toFixed(1)} • Pass rate {Number(item.pass_rate || 0).toFixed(1)}%</p>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 p-4">
              <h3 className="text-sm font-bold uppercase tracking-wide text-slate-700">Subject Trend Movement</h3>
              <div className="mt-4 space-y-3">
                {(examSubjectSummary.subject_trends || []).length === 0 ? (
                  <p className="text-sm text-slate-500">Trend data will appear here once your subjects have at least one imported batch.</p>
                ) : (
                  examSubjectSummary.subject_trends.map((item) => (
                    <div key={item.subject} className="rounded-lg bg-slate-50 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-bold text-slate-800">{item.subject}</p>
                        <span className={`text-xs font-bold ${item.delta === null ? 'text-slate-500' : item.delta >= 0 ? 'text-emerald-700' : 'text-red-600'}`}>
                          {item.delta === null ? 'No prior baseline' : `${item.delta >= 0 ? '+' : ''}${item.delta.toFixed(1)} pts`}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-slate-600">Latest average {Number(item.latest_average || 0).toFixed(1)} • Pass rate {Number(item.latest_pass_rate || 0).toFixed(1)}%</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {examSubjectSummary.class_level_summaries_enabled && (
            <div className="mt-6 rounded-xl border border-slate-200 p-4">
              <h3 className="text-sm font-bold uppercase tracking-wide text-slate-700">Assigned Class Summaries</h3>
              <div className="mt-4 space-y-3">
                {(examSubjectSummary.class_summaries || []).length === 0 ? (
                  <p className="text-sm text-slate-500">No class-level summary could be derived yet for your assigned classes. This usually means the imported exam rows could not be matched to enrolled student records or did not include class information.</p>
                ) : (
                  examSubjectSummary.class_summaries.map((item) => (
                    <div key={item.class_name} className="rounded-lg bg-slate-50 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="text-sm font-bold text-slate-800">{item.class_name}</p>
                        <span className="text-xs font-bold text-slate-500">{item.candidate_count} candidates • {item.subject_entry_count} entries</span>
                      </div>
                      <p className="mt-2 text-xs text-slate-600">Average {Number(item.average_score || 0).toFixed(1)} • Pass rate {Number(item.pass_rate || 0).toFixed(1)}%</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {examSubjectSummaryError && (
        <div className="mb-8 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
          {examSubjectSummaryError}
        </div>
      )}

      <div className="mb-8">
        <AcademicGuidancePanel title="My Diagnostic Mock Guidance" />
      </div>

      {/* Tabs Navigation */}
      <div className="mb-6 border-b border-gray-200">
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab('grades')}
            className={`px-6 py-3 font-bold transition-colors ${
              activeTab === 'grades'
                ? 'border-b-4 border-blue-600 text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            📝 Grade Entry
          </button>
          <button
            onClick={() => setActiveTab('lesson-notes')}
            className={`px-6 py-3 font-bold transition-colors ${
              activeTab === 'lesson-notes'
                ? 'border-b-4 border-blue-600 text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            📖 My Lesson Notes ({myLessonNotes.length})
          </button>
        </div>
      </div>

      {activeTab === 'lesson-notes' && (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <h2 className="text-2xl font-bold text-gray-800 mb-6">My Lesson Notes</h2>
          {myLessonNotes.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No lesson notes submitted yet.</p>
          ) : (
            <div className="space-y-4">
              {myLessonNotes.map((note) => (
                <div
                  key={note.id}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <h3 className="font-bold text-lg text-gray-800">
                        Week {note.week_number} - {note.subject}
                      </h3>
                      <p className="text-sm text-gray-600">
                        {note.class_name} • Submitted to: {note.submit_to === 'headmaster' ? 'Headmaster' : 'Proprietor'}
                      </p>
                    </div>
                    <div className="flex gap-2 items-center">
                      <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                        note.status === 'Approved' ? 'bg-green-100 text-green-700' :
                        note.status === 'Rejected' ? 'bg-red-100 text-red-700' :
                        'bg-yellow-100 text-yellow-700'
                      }`}>
                        {note.status}
                      </span>
                      <button
                        onClick={() => handlePrintLessonNote(note)}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 transition-colors"
                      >
                        🖨️ Print
                      </button>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3 text-sm mb-3">
                    <div className="bg-gray-50 p-2 rounded">
                      <span className="font-bold text-gray-600">Indicator:</span> {note.indicator_code}
                    </div>
                    <div className="bg-gray-50 p-2 rounded">
                      <span className="font-bold text-gray-600">Content Standard:</span> {note.content_standard_code}
                    </div>
                    <div className="bg-gray-50 p-2 rounded">
                      <span className="font-bold text-gray-600">Class Size:</span> {note.class_size || 'N/A'}
                    </div>
                    <div className="bg-gray-50 p-2 rounded">
                      <span className="font-bold text-gray-600">Lesson Dates:</span> {Array.isArray(note.lesson_dates) && note.lesson_dates.length > 0 ? note.lesson_dates.join(', ') : 'N/A'}
                    </div>
                  </div>

                  <div className="bg-blue-50 p-3 rounded-lg mb-3">
                    <p className="text-sm"><span className="font-bold text-blue-900">Performance Indicator:</span> {note.performance_indicator}</p>
                  </div>

                  {note.daily_phases && note.daily_phases.length > 0 && (
                    <div className="bg-gray-50 p-3 rounded-lg mb-3">
                      <p className="text-xs font-bold text-gray-600 mb-2">Daily Phases:</p>
                      <div className="flex flex-wrap gap-2">
                        {note.daily_phases.map((phase, idx) => (
                          <span key={idx} className="text-xs bg-white px-2 py-1 rounded border">
                            {phase.day}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex items-center justify-between text-sm pt-3 border-t">
                    <div className="flex items-center gap-4">
                      <span className="font-bold text-gray-600">AI Score: <span className="text-blue-600">{note.ai_score}/100</span></span>
                      <span className="text-gray-500">•</span>
                      <span className="text-gray-500">{new Date(note.submitted_at).toLocaleDateString()}</span>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setFeedbackNote(note);
                          setFeedbackModal(true);
                        }}
                        className="px-3 py-1 bg-purple-600 text-white rounded-lg text-xs font-bold hover:bg-purple-700 transition-colors"
                      >
                        📊 View Feedback
                      </button>
                      <button
                        onClick={() => setSelectedNote(selectedNote?.id === note.id ? null : note)}
                        className="text-blue-600 hover:text-blue-800 font-bold text-xs"
                      >
                        {selectedNote?.id === note.id ? 'Hide Details ▲' : 'View Details ▼'}
                      </button>
                    </div>
                  </div>

                  {selectedNote?.id === note.id && (
                    <div className="mt-4 pt-4 border-t space-y-3">
                      {note.core_competencies && (
                        <div>
                          <p className="text-xs font-bold text-gray-600">Core Competencies:</p>
                          <p className="text-sm text-gray-700">{note.core_competencies}</p>
                        </div>
                      )}
                      {note.key_words && (
                        <div>
                          <p className="text-xs font-bold text-gray-600">Key Words:</p>
                          <p className="text-sm text-gray-700">{note.key_words}</p>
                        </div>
                      )}
                      {note.teaching_learning_resources && (
                        <div>
                          <p className="text-xs font-bold text-gray-600">T.L.R(s):</p>
                          <p className="text-sm text-gray-700">{note.teaching_learning_resources}</p>
                        </div>
                      )}
                      {note.references && (
                        <div>
                          <p className="text-xs font-bold text-gray-600">References:</p>
                          <p className="text-sm text-gray-700">{note.references}</p>
                        </div>
                      )}
                      <div className="bg-blue-50 p-3 rounded">
                        <p className="text-xs font-bold text-blue-900">AI Feedback:</p>
                        <p className="text-sm text-blue-700">{note.ai_feedback}</p>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'grades' && (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* LEFT COLUMN: MARKS ENTRY */}
        <div className="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          {!canEnterGrades && <FeatureLock feature="grade_entry" requiredPlan="Basic" />}
          <fieldset disabled={!canEnterGrades} className="min-w-0">
          <div className="flex flex-wrap items-end gap-4 mb-4">
            <div>
              <label className="block text-xs font-bold text-gray-400 uppercase mb-1">Class</label>
              <select
                value={selectedClass}
                onChange={(e) => setSelectedClass(e.target.value)}
                className="p-2 border rounded-lg bg-gray-50 font-bold text-slate-700"
                disabled={classOptions.length === 0}
              >
                {classOptions.length === 0 && <option value="">No school classes configured</option>}
                {classOptions.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold text-gray-400 uppercase mb-1">Subject</label>
              <select
                value={selectedSubject}
                onChange={(e) => setSelectedSubject(e.target.value)}
                className="p-2 border rounded-lg bg-gray-50 font-bold text-slate-700 w-52"
              >
                {useTimetable && gradeSubjectOptions.length === 0 && (
                  <option value="">No timetable subjects</option>
                )}
                {!useTimetable && gradeSubjectOptions.length === 0 && (
                  <option value="">No assigned subjects available</option>
                )}
                {gradeSubjectOptions.map((subject) => (
                  <option key={subject} value={subject}>{subject}</option>
                ))}
              </select>
            </div>
            <div className="text-xs text-slate-500">
              Class Work: 0-{classScoreMax} • Exam: 0-{examScoreMax}
            </div>
          </div>

          {assignedClasses.length > 0 && (
            <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-blue-700 mb-2">Your Assigned Classes</p>
              <div className="flex flex-wrap gap-2">
                {assignedClasses.map((className) => (
                  <span
                    key={className}
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${selectedClass === className ? 'bg-blue-600 text-white' : 'bg-white text-blue-800 border border-blue-200'}`}
                  >
                    {className}
                  </span>
                ))}
              </div>
            </div>
          )}

          {studentLoadError && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-800 font-semibold text-sm">⚠️ Error loading students</p>
              <p className="text-red-700 text-sm mt-1">{studentLoadError}</p>
            </div>
          )}

          <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
            📝 Student Grades
          </h3>
          
          {students.length === 0 && !studentLoadError && selectedClass && (
            <div className="p-6 bg-blue-50 border border-blue-200 rounded-lg text-center">
              <p className="text-blue-800 font-medium">No students found in this class yet.</p>
            </div>
          )}

          {students.length > 0 && (
          <div className="space-y-4">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                <div className="flex-1">
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-500">
                    Select Student
                  </label>
                  <select
                    value={selectedStudentId}
                    onChange={(e) => setSelectedStudentId(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white p-3 text-sm font-medium text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
                  >
                    {students.map((student) => (
                      <option key={student.id} value={student.id}>
                        {student.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="rounded-lg bg-white px-4 py-3 text-sm text-slate-600 border border-slate-200">
                  Completed: <span className="font-bold text-slate-900">{completedStudentCount}/{students.length}</span>
                </div>
              </div>
            </div>

            {selectedStudent && (
              <div className="p-4 bg-gray-50 rounded-lg hover:bg-blue-50 transition-colors space-y-3">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-4 md:items-center">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Student Name</p>
                    <p className="mt-1 font-medium text-gray-800">{selectedStudent.name}</p>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-bold uppercase tracking-wide text-slate-500">Class Score</label>
                    <input
                      type="number"
                      min="0"
                      max={classScoreMax}
                      step="0.5"
                      className={`w-full p-2 border rounded text-center focus:ring-2 outline-none ${
                        selectedStudent.class_score && parseFloat(selectedStudent.class_score) > classScoreMax 
                          ? 'border-red-500 bg-red-50 focus:ring-red-500' 
                          : 'focus:ring-blue-500'
                      }`}
                      value={selectedStudent.class_score || ''}
                      onChange={(e) => handleClassAssignmentChange(selectedStudent.id, e.target.value)}
                      title={`Max: ${classScoreMax}`}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-bold uppercase tracking-wide text-slate-500">Exam Score</label>
                    <input
                      type="number"
                      min="0"
                      max={examScoreMax}
                      step="0.5"
                      className={`w-full p-2 border rounded text-center focus:ring-2 outline-none ${
                        selectedStudent.exam_score && parseFloat(selectedStudent.exam_score) > examScoreMax 
                          ? 'border-red-500 bg-red-50 focus:ring-red-500' 
                          : 'focus:ring-green-500'
                      }`}
                      value={selectedStudent.exam_score || ''}
                      onChange={(e) => handleExamScoreChange(selectedStudent.id, e.target.value)}
                      title={`Max: ${examScoreMax}`}
                    />
                  </div>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Total</p>
                    <div className="mt-1 font-bold text-slate-700 text-lg">
                      {(parseFloat(selectedStudent.class_score) || 0) + (parseFloat(selectedStudent.exam_score) || 0)}
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 bg-white p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Diagnostic strands for {selectedSubject}</p>
                    <button
                      type="button"
                      onClick={() => addDiagnosticTopic(selectedStudent.id)}
                      className="rounded-md border border-blue-200 px-2 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                    >
                      + Add Diagnostic
                    </button>
                  </div>
                  {(selectedStudent.diagnostic_topics || []).length === 0 ? (
                    <p className="mt-2 text-xs text-slate-400">Optional: add topic-level diagnostics that should flow to the homeroom report builder.</p>
                  ) : (
                    <div className="mt-3 space-y-2">
                      {selectedStudent.diagnostic_topics.map((topic, index) => (
                        <div key={`${selectedStudent.id}-${index}`} className="grid grid-cols-1 gap-2 md:grid-cols-[minmax(0,2fr)_90px_90px_auto] md:items-center">
                          <input
                            type="text"
                            className="rounded border p-2 text-sm"
                            placeholder="Topic or strand"
                            value={topic.topic || ''}
                            onChange={(e) => handleDiagnosticTopicChange(selectedStudent.id, index, 'topic', e.target.value)}
                          />
                          <input
                            type="number"
                            min="0"
                            step="0.5"
                            className="rounded border p-2 text-sm"
                            placeholder="Score"
                            value={topic.score || ''}
                            onChange={(e) => handleDiagnosticTopicChange(selectedStudent.id, index, 'score', e.target.value)}
                          />
                          <input
                            type="number"
                            min="0"
                            step="0.5"
                            className="rounded border p-2 text-sm"
                            placeholder="Max"
                            value={topic.max_score || ''}
                            onChange={(e) => handleDiagnosticTopicChange(selectedStudent.id, index, 'max_score', e.target.value)}
                          />
                          <button
                            type="button"
                            onClick={() => removeDiagnosticTopic(selectedStudent.id, index)}
                            className="rounded border border-slate-200 px-2 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                          >
                            Remove
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          )}
          <button onClick={handleSave} disabled={!canEnterGrades} className="mt-6 w-full btn-primary">
            Submit Grades to Homeroom
          </button>
          </fieldset>
        </div>

        {/* RIGHT COLUMN: LESSON NOTES & AI */}
        <div className="space-y-8">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <h3 className="font-bold text-lg mb-4">🗓️ My Timetable</h3>
            {timetableEntries.length === 0 ? (
              <p className="text-sm text-slate-400">No timetable slots assigned yet.</p>
            ) : (
              <div className="space-y-3">
                {timetableEntries.map((entry) => (
                  <div key={entry.id} className="p-3 bg-slate-50 rounded-lg border">
                    <p className="font-semibold text-slate-800">{entry.class_name} • {entry.subject_name}</p>
                    <p className="text-xs text-slate-500">{entry.day_of_week} • {entry.start_time} - {entry.end_time}</p>
                    {entry.location && <p className="text-xs text-slate-400">Room: {entry.location}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <h3 className="font-bold text-lg mb-4">📖 Submit Lesson Notes</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Week</label>
                <input
                  type="number"
                  min="1"
                  max="52"
                  className="w-full p-2 border rounded-lg bg-gray-50"
                  value={lessonNoteData.week_number}
                  onChange={(e) => updateLessonField('week_number', e.target.value)}
                  placeholder="3"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Class</label>
                <select
                  className="w-full p-2 border rounded-lg bg-gray-50"
                  value={selectedClass}
                  onChange={(e) => setSelectedClass(e.target.value)}
                  disabled={classOptions.length === 0}
                >
                  {classOptions.length === 0 && <option value="">No school classes configured</option>}
                  {classOptions.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Subject</label>
                <select
                  className="w-full p-2 border rounded-lg bg-gray-50"
                  value={lessonNoteSubject}
                  onChange={(e) => setLessonNoteSubject(e.target.value)}
                >
                  {useTimetable && lessonNoteSubjectOptions.length === 0 && (
                    <option value="">No timetable subjects</option>
                  )}
                  {!useTimetable && lessonNoteSubjectOptions.length === 0 && (
                    <option value="">No subjects available</option>
                  )}
                  {lessonNoteSubjectOptions.map((subject) => (
                    <option key={subject} value={subject}>{subject}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Class Size</label>
                <input
                  type="number"
                  min="1"
                  className="w-full p-2 border rounded-lg bg-gray-50"
                  value={lessonNoteData.class_size}
                  onChange={(e) => updateLessonField('class_size', e.target.value)}
                  placeholder="e.g. 45"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Indicator Code</label>
                <input
                  type="text"
                  className="w-full p-2 border rounded-lg"
                  value={lessonNoteData.indicator_code}
                  onChange={(e) => updateLessonField('indicator_code', e.target.value)}
                  placeholder="e.g. B3.2.1"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Content Standard Code</label>
                <input
                  type="text"
                  className="w-full p-2 border rounded-lg"
                  value={lessonNoteData.content_standard_code}
                  onChange={(e) => updateLessonField('content_standard_code', e.target.value)}
                  placeholder="e.g. B3.2"
                />
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Lesson Dates</label>
              <div className="flex gap-2">
                <input
                  type="date"
                  className="w-full p-2 border rounded-lg bg-gray-50"
                  value={lessonDateInput}
                  onChange={(e) => setLessonDateInput(e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => {
                    if (!lessonDateInput) return;
                    if (lessonNoteData.lesson_dates.includes(lessonDateInput)) return;
                    updateLessonField('lesson_dates', [...lessonNoteData.lesson_dates, lessonDateInput]);
                    setLessonDateInput('');
                  }}
                  className="px-3 py-2 text-xs font-bold bg-blue-600 text-white rounded-lg"
                >
                  Add
                </button>
              </div>
              {lessonNoteData.lesson_dates.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {lessonNoteData.lesson_dates.map((date) => (
                    <span key={date} className="bg-slate-100 text-slate-700 text-xs px-2 py-1 rounded-full">
                      {date}
                      <button
                        type="button"
                        onClick={() => updateLessonField('lesson_dates', lessonNoteData.lesson_dates.filter((d) => d !== date))}
                        className="ml-2 text-red-600 font-bold"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="space-y-4 mb-4">
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Performance Indicator</label>
                <textarea
                  className="w-full h-20 p-3 border rounded-lg bg-gray-50 focus:ring-2 focus:ring-blue-500 outline-none"
                  value={lessonNoteData.performance_indicator}
                  onChange={(e) => updateLessonField('performance_indicator', e.target.value)}
                  placeholder="Learners will be able to..."
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Core Competencies</label>
                <textarea
                  className="w-full h-16 p-3 border rounded-lg bg-gray-50"
                  value={lessonNoteData.core_competencies}
                  onChange={(e) => updateLessonField('core_competencies', e.target.value)}
                  placeholder="Creativity, Critical thinking, Collaboration..."
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Key Words</label>
                <input
                  type="text"
                  className="w-full p-2 border rounded-lg"
                  value={lessonNoteData.key_words}
                  onChange={(e) => updateLessonField('key_words', e.target.value)}
                  placeholder="e.g. fraction, numerator, denominator"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">T.L.R(s)</label>
                <input
                  type="text"
                  className="w-full p-2 border rounded-lg"
                  value={lessonNoteData.teaching_learning_resources}
                  onChange={(e) => updateLessonField('teaching_learning_resources', e.target.value)}
                  placeholder="Flash cards, chart, real objects..."
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">References</label>
                <input
                  type="text"
                  className="w-full p-2 border rounded-lg"
                  value={lessonNoteData.references}
                  onChange={(e) => updateLessonField('references', e.target.value)}
                  placeholder="Textbook page, syllabus, etc."
                />
              </div>
            </div>

            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-bold text-sm text-slate-700">Daily Phases</h4>
                <button
                  type="button"
                  onClick={addPhaseRow}
                  className="px-3 py-1 text-xs font-bold bg-blue-600 text-white rounded-lg"
                >
                  + Add Day
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs border">
                  <thead className="bg-slate-50">
                    <tr className="text-slate-500 uppercase">
                      <th className="p-2 text-left">Day</th>
                      <th className="p-2 text-left">Phase 1: Starter</th>
                      <th className="p-2 text-left">Phase 2: Main</th>
                      <th className="p-2 text-left">Phase 3: Plenary</th>
                      <th className="p-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {dailyPhases.map((row, index) => (
                      <tr key={`phase-${index}`} className="border-t">
                        <td className="p-2">
                          <input
                            type="text"
                            className="w-28 p-1 border rounded"
                            value={row.day}
                            onChange={(e) => updatePhaseField(index, 'day', e.target.value)}
                            placeholder="Monday"
                          />
                        </td>
                        <td className="p-2">
                          <textarea
                            className="w-full h-32 p-2 border rounded"
                            value={row.phase_1_starter}
                            onChange={(e) => updatePhaseField(index, 'phase_1_starter', e.target.value)}
                            placeholder="Preparing the brain for learning"
                          />
                        </td>
                        <td className="p-2">
                          <textarea
                            className="w-full h-32 p-2 border rounded"
                            value={row.phase_2_main}
                            onChange={(e) => updatePhaseField(index, 'phase_2_main', e.target.value)}
                            placeholder="New learning including assessment"
                          />
                        </td>
                        <td className="p-2">
                          <textarea
                            className="w-full h-32 p-2 border rounded"
                            value={row.phase_3_plenary}
                            onChange={(e) => updatePhaseField(index, 'phase_3_plenary', e.target.value)}
                            placeholder="Plenary/Reflections"
                          />
                        </td>
                        <td className="p-2 text-right">
                          <button
                            type="button"
                            onClick={() => removePhaseRow(index)}
                            className="text-red-600 text-xs font-bold"
                            disabled={dailyPhases.length === 1}
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="mt-4 flex flex-col gap-2">
              {hasHeadmaster && (
                <button 
                  onClick={() => handleSubmitLessonNote('headmaster')} 
                  className="w-full bg-blue-600 text-white py-2 rounded-lg font-bold hover:bg-blue-700 transition-colors"
                >
                  Submit to Headmaster & AI
                </button>
              )}
              <button 
                onClick={() => handleSubmitLessonNote('proprietor')} 
                className="w-full bg-purple-600 text-white py-2 rounded-lg font-bold hover:bg-purple-700 transition-colors"
              >
                Submit to Proprietor & AI
              </button>
              {!hasHeadmaster && (
                <p className="text-xs text-gray-500 text-center">No headmaster assigned. Submitting to proprietor only.</p>
              )}
            </div>
          </div>

          <div className="bg-blue-50 p-6 rounded-xl border border-blue-100">
            <h4 className="text-blue-900 font-bold text-sm mb-2 italic">EduPulse SMT AI Tip:</h4>
            <p className="text-blue-700 text-xs">
              "Abena Selorm is currently at **High Risk** due to 3+ missed feeding payments. 
              Avoid calling her out in class; the Headmaster has been notified for a guardian meeting."
            </p>
          </div>
        </div>
      </div>
      )}

      {/* AI Feedback Modal */}
      {feedbackModal && feedbackNote && (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="sticky top-0 bg-linear-to-r from-blue-600 to-purple-600 text-white p-6 rounded-t-2xl">
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-2xl font-bold mb-2">
                  📊 AI Analysis & Feedback
                </h2>
                <p className="text-blue-100 text-sm">
                  Week {feedbackNote.week_number} • {feedbackNote.subject} • {feedbackNote.class_name}
                </p>
              </div>
              <button
                onClick={() => setFeedbackModal(false)}
                className="text-white hover:text-gray-200 text-3xl font-bold leading-none"
              >
                ×
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="p-6 space-y-6">
            {/* Overall Score */}
            <div className="bg-linear-to-br from-blue-50 to-purple-50 p-6 rounded-xl border-2 border-blue-200">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-bold text-gray-800">Overall Quality Score</h3>
                <div className="flex items-center gap-3">
                  <div className={`text-5xl font-black ${
                    feedbackNote.ai_score >= 85 ? 'text-green-600' :
                    feedbackNote.ai_score >= 70 ? 'text-blue-600' :
                    feedbackNote.ai_score >= 55 ? 'text-yellow-600' :
                    'text-red-600'
                  }`}>
                    {feedbackNote.ai_score}
                  </div>
                  <div className="text-gray-500 text-2xl font-bold">/100</div>
                </div>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    feedbackNote.ai_score >= 85 ? 'bg-green-500' :
                    feedbackNote.ai_score >= 70 ? 'bg-blue-500' :
                    feedbackNote.ai_score >= 55 ? 'bg-yellow-500' :
                    'bg-red-500'
                  }`}
                  style={{ width: `${feedbackNote.ai_score}%` }}
                ></div>
              </div>
              <p className="text-sm text-gray-600 mt-2">
                {feedbackNote.ai_score >= 85 && '🌟 Outstanding - Exemplary lesson planning'}
                {feedbackNote.ai_score >= 70 && feedbackNote.ai_score < 85 && '✅ Good - Solid pedagogical approach'}
                {feedbackNote.ai_score >= 55 && feedbackNote.ai_score < 70 && '✓ Satisfactory - Room for enhancement'}
                {feedbackNote.ai_score < 55 && '⚠️ Needs Improvement - Requires development'}
              </p>
            </div>

            {/* Status Badge */}
            <div className="flex items-center gap-3">
              <span className={`px-4 py-2 rounded-full text-sm font-bold ${
                feedbackNote.status === 'Approved' ? 'bg-green-100 text-green-800' :
                feedbackNote.status === 'Rejected' ? 'bg-red-100 text-red-800' :
                'bg-yellow-100 text-yellow-800'
              }`}>
                Status: {feedbackNote.status}
              </span>
              <span className="text-sm text-gray-600">
                Submitted to: <span className="font-bold">{feedbackNote.submit_to === 'headmaster' ? 'Headmaster' : 'Proprietor'}</span>
              </span>
            </div>

            {/* Detailed Feedback */}
            <div className="bg-gray-50 p-6 rounded-xl border border-gray-200">
              <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                <span className="text-2xl">🤖</span>
                AI Detailed Analysis
              </h3>
              <div className="prose prose-sm max-w-none">
                <pre className="whitespace-pre-wrap font-sans text-sm text-gray-700 leading-relaxed">
                  {feedbackNote.ai_feedback}
                </pre>
              </div>
            </div>

            {/* Lesson Details Summary */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white p-4 rounded-lg border border-gray-200">
                <p className="text-xs font-bold text-gray-500 uppercase mb-2">Curriculum Alignment</p>
                <p className="text-sm"><span className="font-bold">Indicator:</span> {feedbackNote.indicator_code}</p>
                <p className="text-sm"><span className="font-bold">Standard:</span> {feedbackNote.content_standard_code}</p>
              </div>
              <div className="bg-white p-4 rounded-lg border border-gray-200">
                <p className="text-xs font-bold text-gray-500 uppercase mb-2">Submission Info</p>
                <p className="text-sm"><span className="font-bold">Date:</span> {new Date(feedbackNote.submitted_at).toLocaleString()}</p>
                <p className="text-sm"><span className="font-bold">Phases:</span> {feedbackNote.daily_phases?.length || 0} day(s)</p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 pt-4 border-t">
              <button
                onClick={() => handlePrintLessonNote(feedbackNote)}
                className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-bold hover:bg-blue-700 transition-colors"
              >
                🖨️ Print Lesson Note
              </button>
              <button
                onClick={() => setFeedbackModal(false)}
                className="flex-1 bg-gray-200 text-gray-800 py-3 rounded-lg font-bold hover:bg-gray-300 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    )}
    </div>
  );
}