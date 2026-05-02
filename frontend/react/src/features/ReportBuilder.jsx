import React, { useState, useEffect } from 'react';
import axios from 'axios';
import reportTemplates from '../report_templates';
import { buildTemplateHtml, formatGradingSchemeSummary, GRADE_SCALE_ROWS, getGradeFromTotal } from '../utils/reportTemplate';

/**
 * Report Builder: Manual report card entry for homeroom teachers.
 * Allows homeroom teachers to input full terminal report data:
 * - Subject grades (class score, exam score, total, position, remarks)
 * - Overall performance stats (term average, position, attendance)
 * - Teacher remarks
 */
export default function ReportBuilder() {
  const [students, setStudents] = useState([]);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reportTemplateId, setReportTemplateId] = useState('gradman_v1');
  const [reportTemplateConfig, setReportTemplateConfig] = useState({});
  
  // Academic context
  const [academicTerm, setAcademicTerm] = useState('Term 1');
  const [academicYear, setAcademicYear] = useState('2024/2025');
  
  // Form fields
  const [subjectGrades, setSubjectGrades] = useState([]);
  const [overallPosition, setOverallPosition] = useState('');
  const [outOfStudents, setOutOfStudents] = useState('');
  const [attendancePercentage, setAttendancePercentage] = useState('');
  const [totalAttendance, setTotalAttendance] = useState('');
  const [homeroomRemarks, setHomeroomRemarks] = useState('');
  const [termCalendar, setTermCalendar] = useState({});
  
  // Grading scheme
  const [classScoreMax, setClassScoreMax] = useState(30);
  const [examScoreMax, setExamScoreMax] = useState(70);
  const [hasHeadmaster, setHasHeadmaster] = useState(true);
  
  const currentClass = localStorage.getItem('assigned_class') || 'JHS 1';
  const userRole = localStorage.getItem('role');
  const roles = JSON.parse(localStorage.getItem('roles') || '[]');
  const isHomeroom = roles.includes('homeroom') || userRole === 'homeroom' || (userRole === 'teacher' && currentClass);
  
  const [branding, setBranding] = useState(() => JSON.parse(localStorage.getItem('branding')) || {});
  const primaryColor = branding.primary_color || '#1e3a8a';

  const formatReportDate = (value) => {
    if (!value) return '';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
  };

  const getAuthHeaders = () => ({
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  // Fetch grading scheme
  useEffect(() => {
    const fetchGradingScheme = async () => {
      try {
        const res = await axios.get('/api/school/grading-scheme', getAuthHeaders());
        setClassScoreMax(res.data.class_score_max);
        setExamScoreMax(res.data.exam_score_max);
      } catch (err) {
        console.error("Failed to load grading scheme", err);
        // Use defaults if fetch fails
      }
    };
    fetchGradingScheme();
  }, []);

  // Fetch branding to ensure latest school logo is used
  useEffect(() => {
    const fetchBranding = async () => {
      try {
        const res = await axios.get('/api/school/branding', getAuthHeaders());
        const nextBranding = {
          name: res.data.school_name,
          logo: res.data.logo_url,
          theme_color: res.data.theme_color,
          motto: res.data.motto,
          email: res.data.school_email,
          phone: res.data.school_phone
        };
        setBranding((prev) => ({ ...prev, ...nextBranding }));
      } catch (err) {
        console.error('Failed to load school branding', err);
      }
    };
    fetchBranding();
  }, []);

  // Fetch report template settings
  useEffect(() => {
    const fetchTemplate = async () => {
      try {
        const res = await axios.get('/api/school/report-template', getAuthHeaders());
        const legacyMap = {
          sample1: 'gradman_v1',
          sample2: 'parent_focus',
          sample3: 'progress_insights',
          sample4: 'compact_clear',
          sample5: 'guardian_narrative',
          sample6: 'classic_traditional'
        };
        const rawId = res.data.report_template_id || 'gradman_v1';
        const nextId = legacyMap[rawId] || rawId;
        setReportTemplateId(nextId);
        const preset = reportTemplates.find((t) => t.id === nextId);
        const mergedConfig = mergeTemplateConfig(preset?.config, res.data.report_template_config || {});
        setReportTemplateConfig(mergedConfig);
      } catch (err) {
        console.error('Failed to load report template', err);
      }
    };
    fetchTemplate();
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

  // Fetch students for current class
  useEffect(() => {
    const fetchStudents = async () => {
      setLoading(true);
      try {
        const res = await axios.get(`/api/homeroom/report-builder/students?class_name=${currentClass}`, getAuthHeaders());
        setStudents(res.data);
      } catch (err) {
        console.error("Failed to load students", err);
        alert("Failed to load students for report builder");
      } finally {
        setLoading(false);
      }
    };
    fetchStudents();
  }, [currentClass]);

  // Fetch existing report when student selected
  useEffect(() => {
    if (!selectedStudent) return;
    
    const fetchReport = async () => {
      setLoading(true);
      try {
        const res = await axios.get(
          `/api/homeroom/report-builder/report/${selectedStudent.id}?academic_term=${academicTerm}&academic_year=${academicYear}`,
          getAuthHeaders()
        );
        
        // Load existing report data
        setReportData(res.data);
        setTermCalendar(res.data.term_calendar || {});
        setSubjectGrades(res.data.subject_grades || []);
        setOverallPosition(res.data.overall_position || '');
        setOutOfStudents(res.data.out_of_students || '');
        setAttendancePercentage(res.data.attendance_percentage || '');
        setTotalAttendance(res.data.total_attendance || '');
        setHomeroomRemarks(res.data.homeroom_teacher_remarks || '');
      } catch (err) {
        if (err.response?.status === 404) {
          // No existing report, auto-fill from finalized subject grades
          await fetchAutoFill();
        } else {
          console.error("Failed to load report", err);
        }
      } finally {
        setLoading(false);
      }
    };
    
    fetchReport();
  }, [selectedStudent, academicTerm, academicYear]);

  const fetchAutoFill = async () => {
    try {
      const res = await axios.get(
        `/api/homeroom/report-builder/auto-fill/${selectedStudent.id}?class_name=${currentClass}&academic_term=${academicTerm}&academic_year=${academicYear}`,
        getAuthHeaders()
      );
      const data = res.data || {};

      if (Array.isArray(data.subject_grades) && data.subject_grades.length > 0) {
        setSubjectGrades(data.subject_grades);
      } else {
        initializeEmptyReport();
      }

      setTermCalendar(data.term_calendar || {});

      setOutOfStudents(
        data.out_of_students !== null && data.out_of_students !== undefined
          ? String(data.out_of_students)
          : (students.length ? String(students.length) : '')
      );
      setOverallPosition(data.overall_position || '');
      setAttendancePercentage(data.attendance_percentage || '');
      setTotalAttendance(data.total_attendance || '');
      setHomeroomRemarks('');
      setReportData(null);
    } catch (err) {
      console.error('Failed to auto-fill report builder', err);
      initializeEmptyReport();
    }
  };

  const initializeEmptyReport = () => {
    // Initialize with default subjects (can be customized)
    const defaultSubjects = [
      'Mathematics', 'English Language', 'Science', 'Social Studies',
      'Religious & Moral Education', 'French', 'ICT', 'Creative Arts'
    ];
    
    setSubjectGrades(defaultSubjects.map(subject => ({
      subject,
      class_score: '',
      exam_score: '',
      total: '',
      position: '',
      grade: '',
      remarks: ''
    })));
    setOverallPosition('');
    setOutOfStudents('');
    setAttendancePercentage('');
    setTotalAttendance('');
    setHomeroomRemarks('');
    setReportData(null);
    setTermCalendar({});
  };

  const handleSubjectChange = (index, field, value) => {
    const updated = [...subjectGrades];
    updated[index][field] = value;
    
    // Auto-calculate total when class_score or exam_score changes
    if (field === 'class_score' || field === 'exam_score') {
      const classScore = parseFloat(updated[index].class_score) || 0;
      const examScore = parseFloat(updated[index].exam_score) || 0;
      updated[index].total = (classScore + examScore).toFixed(1);
      
      // Auto-assign grade based on total
      const total = classScore + examScore;
      updated[index].grade = getGradeFromTotal(total);
    }
    
    setSubjectGrades(updated);
  };

  const handleDiagnosticTopicChange = (subjectIndex, topicIndex, field, value) => {
    const updated = [...subjectGrades];
    const diagnosticTopics = Array.isArray(updated[subjectIndex].diagnostic_topics)
      ? [...updated[subjectIndex].diagnostic_topics]
      : [];
    diagnosticTopics[topicIndex] = {
      ...diagnosticTopics[topicIndex],
      [field]: value,
    };
    updated[subjectIndex].diagnostic_topics = diagnosticTopics;
    setSubjectGrades(updated);
  };

  const addDiagnosticTopic = (subjectIndex) => {
    const updated = [...subjectGrades];
    const diagnosticTopics = Array.isArray(updated[subjectIndex].diagnostic_topics)
      ? [...updated[subjectIndex].diagnostic_topics]
      : [];
    diagnosticTopics.push({ topic: '', score: '', max_score: '' });
    updated[subjectIndex].diagnostic_topics = diagnosticTopics;
    setSubjectGrades(updated);
  };

  const removeDiagnosticTopic = (subjectIndex, topicIndex) => {
    const updated = [...subjectGrades];
    const diagnosticTopics = Array.isArray(updated[subjectIndex].diagnostic_topics)
      ? updated[subjectIndex].diagnostic_topics.filter((_, index) => index !== topicIndex)
      : [];
    updated[subjectIndex].diagnostic_topics = diagnosticTopics;
    setSubjectGrades(updated);
  };

  const addSubject = () => {
    setSubjectGrades([...subjectGrades, {
      subject: '',
      class_score: '',
      exam_score: '',
      total: '',
      position: '',
      grade: '',
      remarks: '',
      diagnostic_topics: []
    }]);
  };

  const removeSubject = (index) => {
    setSubjectGrades(subjectGrades.filter((_, i) => i !== index));
  };

  const handleSave = async (submitForApproval = false, submitTo = 'headmaster') => {
    if (!selectedStudent) {
      alert("Please select a student first");
      return;
    }
    
    // Validate required fields
    const hasIncompleteSubjects = subjectGrades.some(s => 
      !s.subject || s.class_score === '' || s.exam_score === ''
    );
    
    if (hasIncompleteSubjects) {
      alert("Please fill in all subject scores before saving");
      return;
    }
    
    setSaving(true);
    try {
      // Calculate positions for each subject based on class performance
      const gradesWithPosition = await calculateSubjectPositions(subjectGrades);
      
      const payload = {
        student_id: selectedStudent.id,
        academic_term: academicTerm,
        academic_year: academicYear,
        subject_grades: gradesWithPosition,
        overall_position: overallPosition,
        out_of_students: parseInt(outOfStudents) || 0,
        attendance_percentage: parseFloat(attendancePercentage) || 0,
        total_attendance: parseInt(totalAttendance) || 0,
        homeroom_teacher_remarks: homeroomRemarks
      };
      
      const res = await axios.post('/api/homeroom/report-builder/report', payload, getAuthHeaders());
      
      setReportData(res.data.report);
      setTermCalendar(res.data.term_calendar || {});
      if (res.data.report?.subject_grades) {
        setSubjectGrades(res.data.report.subject_grades);
      }
      setOverallPosition(res.data.report?.overall_position || overallPosition);
      setOutOfStudents(res.data.report?.out_of_students || outOfStudents);
      alert("Report card saved successfully!");
      
      // If submitting for approval
      if (submitForApproval && res.data.report_id) {
        await axios.post('/api/homeroom/report-builder/submit', {
          report_id: res.data.report_id,
          submit_to: submitTo
        }, getAuthHeaders());
        const recipient = submitTo === 'headmaster' ? 'Headmaster' : 'Proprietor';
        alert(`Report card submitted to ${recipient} for approval!`);
      }
    } catch (err) {
      console.error("Failed to save report", err);
      alert(err.response?.data?.message || "Failed to save report card");
    } finally {
      setSaving(false);
    }
  };

  // Calculate position for each subject based on all students' performance
  const calculateSubjectPositions = async (grades) => {
    try {
      // Fetch all students' grades for this class, term, and year
      const res = await axios.get(
        `/api/homeroom/class-subject-rankings?class_name=${currentClass}&academic_term=${academicTerm}&academic_year=${academicYear}`,
        getAuthHeaders()
      );
      
      const classRankings = res.data || {};
      
      // Format position with ordinal suffix
      const ordinal = (n) => {
        const s = ['th', 'st', 'nd', 'rd'];
        const v = n % 100;
        return n + (s[(v - 20) % 10] || s[v] || s[0]);
      };
      
      // Calculate position for each subject
      const gradesWithPositions = grades.map(grade => {
        const subjectRankings = classRankings[grade.subject] || [];
        const total = parseFloat(grade.total) || 0;
        
        // Count how many students scored higher
        let position = 1;
        for (const ranking of subjectRankings) {
          if (ranking.student_id !== selectedStudent.id && ranking.total > total) {
            position++;
          }
        }
        
        return {
          ...grade,
          position: ordinal(position)
        };
      });
      
      // Calculate overall position based on average score
      const averageScore = grades.reduce((sum, g) => sum + (parseFloat(g.total) || 0), 0) / grades.length;
      
      // Get all students' averages to rank current student
      let overallRank = 1;
      if (classRankings && Object.keys(classRankings).length > 0) {
        const allStudentsAverages = {};
        
        // Collect all unique students and their scores
        Object.values(classRankings).forEach(rankings => {
          if (Array.isArray(rankings)) {
            rankings.forEach(r => {
              if (!allStudentsAverages[r.student_id]) {
                allStudentsAverages[r.student_id] = [];
              }
              allStudentsAverages[r.student_id].push(r.total || 0);
            });
          }
        });
        
        // Calculate averages and find rank
        const studentAverages = Object.entries(allStudentsAverages)
          .map(([sid, scores]) => ({
            student_id: parseInt(sid),
            average: scores.reduce((a, b) => a + b, 0) / scores.length
          }))
          .sort((a, b) => b.average - a.average);
        
        const rankIndex = studentAverages.findIndex(s => s.student_id === selectedStudent.id);
        overallRank = rankIndex >= 0 ? rankIndex + 1 : 1;
      }
      
      const overallPositionText = ordinal(overallRank);
      setOverallPosition(overallPositionText);
      
      return gradesWithPositions;
    } catch (err) {
      console.error('Failed to calculate positions, using manual entry', err);
      // If endpoint doesn't exist or fails, return grades as-is
      return grades;
    }
  };

  const isHtmlTemplate = reportTemplateConfig?.type === 'html';

  const activeTemplateConfig = isHtmlTemplate
    ? null
    : reportTemplateConfig?.sections
      ? reportTemplateConfig
      : reportTemplates.find((t) => t.id === reportTemplateId)?.config;

  const resolveVisibilityFlag = (key, fallback = true) => {
    const value = activeTemplateConfig?.visibility?.[key];
    return typeof value === 'boolean' ? value : fallback;
  };

  const mergeTemplateConfig = (presetConfig, storedConfig) => {
    if (!presetConfig) return storedConfig || {};
    if (!storedConfig || Object.keys(storedConfig).length === 0) return presetConfig;
    return {
      ...presetConfig,
      ...storedConfig,
      visibility: {
        ...(presetConfig.visibility || {}),
        ...(storedConfig.visibility || {})
      },
      sections: storedConfig.sections || presetConfig.sections
    };
  };

  const toNumber = (value) => {
    const parsed = parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const subjectTotals = subjectGrades.map((subject) => {
    if (subject.total !== '' && subject.total !== null && subject.total !== undefined) {
      return toNumber(subject.total);
    }
    return toNumber(subject.class_score) + toNumber(subject.exam_score);
  });

  const totalMarks = subjectTotals.reduce((sum, value) => sum + value, 0);
  const totalPossible = subjectGrades.length * 100;
  const computedAverage = totalPossible > 0 ? (totalMarks / totalPossible) * 100 : 0;

  const resolvedAverage = reportData?.term_average ?? computedAverage;
  const resolvedTotalMarks = reportData?.total_marks_obtained ?? totalMarks;
  const resolvedTotalPossible = reportData?.total_possible_marks ?? totalPossible;
  const resolvedOutOfStudents = reportData?.out_of_students || outOfStudents || (students.length ? String(students.length) : '');
  const resolvedOverallPosition = reportData?.overall_position || overallPosition || '';
  const resolvedReopeningDate = formatReportDate(termCalendar?.reopening_date || reportData?.term_calendar?.reopening_date || '');

  const previewData = {
    school_name: branding.name || 'EduPulse',
    school_logo: branding.logo || '',
    school_motto: branding.motto || '',
    school_email: branding.email || '',
    school_phone: branding.phone || '',
    school_contact: `${branding.email || ''} | ${branding.phone || ''}`.trim(),
    student_name: selectedStudent?.name || '',
    student_code: selectedStudent?.student_code || '',
    class_name: currentClass,
    academic_term: academicTerm,
    academic_year: academicYear,
    class_score_max: String(classScoreMax),
    exam_score_max: String(examScoreMax),
    grading_scheme_summary: formatGradingSchemeSummary(classScoreMax, examScoreMax),
    subject_grades: subjectGrades,
    total_marks_obtained: resolvedTotalMarks,
    total_possible_marks: resolvedTotalPossible,
    term_average: Number(resolvedAverage).toFixed(1),
    overall_position: resolvedOverallPosition,
    out_of_students: resolvedOutOfStudents,
    attendance_percentage: attendancePercentage,
    total_attendance: totalAttendance,
    reopening_date: resolvedReopeningDate,
    homeroom_teacher_remarks: homeroomRemarks,
    headmaster_remarks: reportData?.headmaster_remarks || '',
    proprietor_remarks: reportData?.proprietor_remarks || '',
    ai_performance_analysis: reportData?.ai_performance_analysis || '',
    academic_guidance: reportData?.academic_guidance || null,
  };

  const showHeadmasterRemarks = (() => {
    const value = reportTemplateConfig?.visibility?.show_headmaster_remarks ?? activeTemplateConfig?.visibility?.show_headmaster_remarks;
    return typeof value === 'boolean' ? value : true;
  })();

  const templatePreviewHtml = isHtmlTemplate
    ? buildTemplateHtml({ templateConfig: reportTemplateConfig, data: previewData })
    : '';

  const isEmptyValue = (value) => {
    if (value === null || value === undefined) return true;
    if (Array.isArray(value)) return value.length === 0;
    if (typeof value === 'string') return value.trim() === '';
    return false;
  };

  const shouldHideEmpty = Boolean(activeTemplateConfig?.visibility?.hide_empty_fields);

  const renderFieldValue = (fieldKey) => {
    const value = previewData[fieldKey];
    if (isEmptyValue(value)) return '';
    return String(value);
  };

  const renderSection = (section) => {
    if (!section) return null;
    const showHeadmasterRemarks = resolveVisibilityFlag('show_headmaster_remarks', true);
    if (!showHeadmasterRemarks && (section.id === 'headmaster_remarks' || section.fields?.some((f) => f.key === 'headmaster_remarks'))) {
      return null;
    }
    if (section.type === 'table') {
      const rows = previewData.subject_grades || [];
      if (rows.length === 0 && activeTemplateConfig?.visibility?.hide_empty_sections) return null;
      return (
        <div key={section.id} className="mb-6">
          <h3 className="font-bold text-slate-700 mb-2 border-b pb-1">{section.label}</h3>
          <table className="w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                {section.columns.map((col) => (
                  <th key={col.key} className="p-2 text-left">{col.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={`${section.id}-${idx}`} className="border-b">
                  {section.columns.map((col) => (
                    <td key={col.key} className="p-2">
                      {col.key === 'grade' ? (
                        <span className="font-bold text-green-700">{row[col.key] ?? ''}</span>
                      ) : col.key === 'total' ? (
                        <span className="font-bold">{row[col.key] ?? ''}</span>
                      ) : (
                        row[col.key] ?? ''
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    if (section.type === 'grading_scale') {
      return (
        <div key={section.id} className="mb-6">
          <h3 className="font-bold text-slate-700 mb-2 border-b pb-1">{section.label}</h3>
          <p className="mb-2 text-xs text-slate-600">{formatGradingSchemeSummary(classScoreMax, examScoreMax)}</p>
          <table className="w-full text-xs">
            <thead className="bg-slate-50">
              <tr className="text-slate-500 uppercase">
                <th className="p-2 text-left">Grade</th>
                <th className="p-2 text-left">Range</th>
                <th className="p-2 text-left">Remarks</th>
              </tr>
            </thead>
            <tbody>
              {GRADE_SCALE_ROWS.map((row) => (
                <tr key={row.grade} className="border-t">
                  <td className="p-2 font-bold text-slate-700">{row.grade}</td>
                  <td className="p-2 text-slate-700">{row.range}</td>
                  <td className="p-2 text-slate-700">{row.remark}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    if (section.type === 'signatures') {
      const fields = section.fields || [];
      if (fields.length === 0 && activeTemplateConfig?.visibility?.hide_empty_sections) return null;
      return (
        <div key={section.id} className="mt-8 pt-4 border-t">
          <div className="grid grid-cols-3 gap-4">
            {fields.map((field) => (
              <div key={field.key} className="text-center">
                <div className="border-t border-slate-400 pt-1 mt-8">
                  <p className="text-xs font-bold text-slate-700">{field.label}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (section.type === 'header') {
      const fields = section.fields || [];
      const visibleFields = shouldHideEmpty
        ? fields.filter((f) => !isEmptyValue(previewData[f.key]))
        : fields;

      if (visibleFields.length === 0 && activeTemplateConfig?.visibility?.hide_empty_sections) return null;

      return (
        <div key={section.id} className="border rounded-lg p-4">
          <div className="text-center mb-6 border-b-4 border-blue-800 pb-4">
            {previewData.school_logo ? (
              <div className="mb-2">
                <img
                  src={previewData.school_logo}
                  alt="School Logo"
                  className="h-16 w-16 object-contain mx-auto"
                />
              </div>
            ) : (
              <div className="mb-2">
                <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center text-3xl mx-auto">
                  🏫
                </div>
              </div>
            )}
            <h1 className="text-3xl font-bold text-blue-900 uppercase">{previewData.school_name}</h1>
            {previewData.school_motto && (
              <p className="text-sm italic text-gray-600 mt-1">{previewData.school_motto}</p>
            )}
            {(previewData.school_email || previewData.school_phone) && (
              <p className="text-xs text-gray-500 mt-2">
                {previewData.school_email || ''}{previewData.school_email && previewData.school_phone ? ' | ' : ''}{previewData.school_phone || ''}
              </p>
            )}
          </div>
        </div>
      );
    }

    // Handle title/student_info sections with special formatting
    if (section.type === 'student_info') {
      const fields = section.fields || [];
      const visibleFields = shouldHideEmpty
        ? fields.filter((f) => !isEmptyValue(previewData[f.key]))
        : fields;

      if (visibleFields.length === 0 && activeTemplateConfig?.visibility?.hide_empty_sections) return null;

      // Check if this is academic info (has term/year fields)
      const hasAcademicInfo = fields.some(f => f.key === 'academic_term' || f.key === 'academic_year');
      
      if (hasAcademicInfo) {
        return (
          <div key={section.id}>
            <div className="text-center mb-4">
              <h2 className="text-xl font-bold text-slate-800 uppercase">Terminal Report Card</h2>
              <p className="text-sm text-slate-600">
                Academic Year: {previewData.academic_year} - {previewData.academic_term}
              </p>
            </div>
          </div>
        );
      }

      return (
        <div key={section.id} className="p-4 bg-blue-50 rounded-lg">
          <div className="grid grid-cols-2 gap-4 text-xs">
            {visibleFields.map((field) => (
              <div key={field.key}>
                <p className="text-slate-600 mb-1">{field.label}:</p>
                <p className="font-bold text-slate-800">{renderFieldValue(field.key)}</p>
              </div>
            ))}
          </div>
        </div>
      );
    }

    // Handle summary sections
    if (section.type === 'summary') {
      const fields = section.fields || [];
      const visibleFields = shouldHideEmpty
        ? fields.filter((f) => !isEmptyValue(previewData[f.key]))
        : fields;

      if (visibleFields.length === 0 && activeTemplateConfig?.visibility?.hide_empty_sections) return null;

      return (
        <div key={section.id} className="p-4 bg-blue-50 rounded-lg">
          <h3 className="font-bold text-slate-700 mb-3 border-b pb-1">{section.label}</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            {visibleFields.map((field) => (
              <div key={field.key}>
                <span className="font-bold text-slate-700">{field.label}:</span>{' '}
                <span className="text-slate-800">{renderFieldValue(field.key)}</span>
              </div>
            ))}
          </div>
        </div>
      );
    }

    // Handle remarks sections with colored borders
    if (section.type === 'remarks') {
      const fields = section.fields || [];
      const visibleFields = shouldHideEmpty
        ? fields.filter((f) => !isEmptyValue(previewData[f.key]))
        : fields;

      if (visibleFields.length === 0 && activeTemplateConfig?.visibility?.hide_empty_sections) return null;

      // Determine border color based on section ID
      const borderColor = section.id.includes('teacher') ? 'yellow' :
                         section.id.includes('headmaster') ? 'orange' :
                         section.id.includes('proprietor') ? 'cyan' : 'gray';

      return (
        <div key={section.id} className={`p-3 bg-${borderColor}-50 border-l-4 border-${borderColor}-400 rounded`}>
          <p className="text-xs font-bold text-slate-700 mb-1">{section.label}:</p>
          {visibleFields.map((field) => (
            <p key={field.key} className="text-sm text-slate-600 italic">{renderFieldValue(field.key)}</p>
          ))}
        </div>
      );
    }

    const fields = section.fields || [];
    const visibleFields = shouldHideEmpty
      ? fields.filter((f) => !isEmptyValue(previewData[f.key]))
      : fields;

    if (visibleFields.length === 0 && activeTemplateConfig?.visibility?.hide_empty_sections) return null;

    return (
      <div key={section.id} className="border rounded-lg p-4">
        <p className="text-sm font-bold text-gray-700 mb-2">{section.label}</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-600">
          {visibleFields.map((field) => (
            <div key={field.key} className="flex items-start gap-2">
              <span className="font-semibold text-gray-700">{field.label}:</span>
              <span>{renderFieldValue(field.key)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  if (!isHomeroom) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-3xl mx-auto bg-white border border-gray-200 rounded-lg p-6 text-center text-gray-600">
          Report Builder is available only for homeroom teachers.
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Report Builder</h1>
          <p className="text-gray-600">Create and manage terminal report cards for your class</p>
        </div>

        {/* Academic Context Selector */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Class</label>
              <input
                type="text"
                value={currentClass}
                disabled
                className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Academic Term</label>
              <select
                value={academicTerm}
                onChange={(e) => setAcademicTerm(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
              >
                <option value="Term 1">Term 1</option>
                <option value="Term 2">Term 2</option>
                <option value="Term 3">Term 3</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Academic Year</label>
              <input
                type="text"
                value={academicYear}
                onChange={(e) => setAcademicYear(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                placeholder="2024/2025"
              />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Student List Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="p-4 border-b border-gray-200" style={{ backgroundColor: primaryColor }}>
                <h2 className="font-semibold text-white">Students</h2>
              </div>
              <div className="max-h-150 overflow-y-auto">
                {loading && <div className="p-4 text-center text-gray-500">Loading...</div>}
                {!loading && students.length === 0 && (
                  <div className="p-4 text-center text-gray-500">No students found</div>
                )}
                {students.map(student => (
                  <button
                    key={student.id}
                    onClick={() => setSelectedStudent(student)}
                    className={`w-full text-left px-4 py-3 hover:bg-blue-50 border-b border-gray-100 transition ${
                      selectedStudent?.id === student.id ? 'bg-blue-100 border-l-4 border-l-blue-500' : ''
                    }`}
                  >
                    <div className="font-medium text-gray-800">{student.name}</div>
                    <div className="text-sm text-gray-500">{student.student_code}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Report Form */}
          <div className="lg:col-span-3">
            {!selectedStudent ? (
              <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
                <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-lg">Select a student to create or edit their report card</p>
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow">
                {/* Student Header */}
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-2xl font-bold text-gray-800">{selectedStudent.name}</h2>
                  <p className="text-gray-600">Student Code: {selectedStudent.student_code} | Class: {currentClass}</p>
                  <p className="text-sm text-gray-500 mt-1">
                    {academicTerm} {academicYear} {reportData?.status && `• Status: ${reportData.status}`}
                  </p>
                </div>

                {/* Subject Grades Table */}
                <div className="p-6">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold text-gray-800">Subject Grades</h3>
                    <button
                      onClick={addSubject}
                      className="px-3 py-1 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm"
                    >
                      + Add Subject
                    </button>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Subject</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Class ({classScoreMax})</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Exam ({examScoreMax})</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Total (100)</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Position</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Grade</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Remarks</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {subjectGrades.map((subject, index) => (
                          <React.Fragment key={index}>
                          <tr>
                            <td className="px-3 py-2 align-top">
                              <input
                                type="text"
                                value={subject.subject}
                                onChange={(e) => handleSubjectChange(index, 'subject', e.target.value)}
                                className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                                placeholder="Subject name"
                              />
                            </td>
                            <td className="px-3 py-2 align-top">
                              <input
                                type="number"
                                min="0"
                                max={classScoreMax}
                                value={subject.class_score}
                                onChange={(e) => handleSubjectChange(index, 'class_score', e.target.value)}
                                className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                              />
                            </td>
                            <td className="px-3 py-2 align-top">
                              <input
                                type="number"
                                min="0"
                                max={examScoreMax}
                                value={subject.exam_score}
                                onChange={(e) => handleSubjectChange(index, 'exam_score', e.target.value)}
                                className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                              />
                            </td>
                            <td className="px-3 py-2 align-top">
                              <input
                                type="text"
                                value={subject.total}
                                disabled
                                className="w-20 px-2 py-1 border border-gray-300 rounded text-sm bg-gray-50"
                              />
                            </td>
                            <td className="px-3 py-2 align-top">
                              <input
                                type="text"
                                value={subject.position}
                                onChange={(e) => handleSubjectChange(index, 'position', e.target.value)}
                                className="w-16 px-2 py-1 border border-gray-300 rounded text-sm"
                                placeholder="1st"
                              />
                            </td>
                            <td className="px-3 py-2 align-top">
                              <input
                                type="text"
                                value={subject.grade}
                                disabled
                                className="w-12 px-2 py-1 border border-gray-300 rounded text-sm bg-gray-50 font-semibold"
                              />
                            </td>
                            <td className="px-3 py-2 align-top">
                              <input
                                type="text"
                                value={subject.remarks}
                                onChange={(e) => handleSubjectChange(index, 'remarks', e.target.value)}
                                className="w-32 px-2 py-1 border border-gray-300 rounded text-sm"
                                placeholder="Remarks"
                              />
                            </td>
                            <td className="px-3 py-2 align-top">
                              <div className="flex flex-col gap-2">
                                <button
                                  type="button"
                                  onClick={() => addDiagnosticTopic(index)}
                                  className="text-blue-600 hover:text-blue-800 text-sm text-left"
                                >
                                  + Diagnostics
                                </button>
                                <button
                                  type="button"
                                  onClick={() => removeSubject(index)}
                                  className="text-red-600 hover:text-red-800 text-sm text-left"
                                >
                                  Remove
                                </button>
                              </div>
                            </td>
                          </tr>
                          {Array.isArray(subject.diagnostic_topics) && subject.diagnostic_topics.length > 0 && (
                            <tr>
                              <td colSpan="8" className="px-3 pb-4 pt-0">
                                <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                                  <div className="flex items-center justify-between gap-3 mb-3">
                                    <div>
                                      <p className="text-sm font-semibold text-blue-900">Diagnostic mock strands for {subject.subject || 'this subject'}</p>
                                      <p className="text-xs text-blue-700">Optional topic sub-scores used for chief examiner guidance and SHS pathway recommendations.</p>
                                    </div>
                                    <button
                                      type="button"
                                      onClick={() => addDiagnosticTopic(index)}
                                      className="px-2 py-1 rounded-md border border-blue-300 text-blue-800 text-xs font-semibold hover:bg-blue-100"
                                    >
                                      Add strand
                                    </button>
                                  </div>
                                  <div className="space-y-2">
                                    {subject.diagnostic_topics.map((topic, topicIndex) => (
                                      <div key={topicIndex} className="grid grid-cols-1 md:grid-cols-4 gap-2 items-center">
                                        <input
                                          type="text"
                                          value={topic.topic}
                                          onChange={(e) => handleDiagnosticTopicChange(index, topicIndex, 'topic', e.target.value)}
                                          className="px-3 py-2 border border-blue-200 rounded-md text-sm bg-white"
                                          placeholder="e.g. Geometry, Grammar, Scientific Units"
                                        />
                                        <input
                                          type="number"
                                          min="0"
                                          value={topic.score}
                                          onChange={(e) => handleDiagnosticTopicChange(index, topicIndex, 'score', e.target.value)}
                                          className="px-3 py-2 border border-blue-200 rounded-md text-sm bg-white"
                                          placeholder="Score"
                                        />
                                        <input
                                          type="number"
                                          min="1"
                                          value={topic.max_score}
                                          onChange={(e) => handleDiagnosticTopicChange(index, topicIndex, 'max_score', e.target.value)}
                                          className="px-3 py-2 border border-blue-200 rounded-md text-sm bg-white"
                                          placeholder="Max score"
                                        />
                                        <button
                                          type="button"
                                          onClick={() => removeDiagnosticTopic(index, topicIndex)}
                                          className="text-red-600 hover:text-red-800 text-sm justify-self-start"
                                        >
                                          Remove strand
                                        </button>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                          </React.Fragment>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Performance Summary */}
                  <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Overall Position</label>
                      <input
                        type="text"
                        value={overallPosition}
                        onChange={(e) => setOverallPosition(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        placeholder="1st"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Out of Students</label>
                      <input
                        type="number"
                        value={outOfStudents}
                        onChange={(e) => setOutOfStudents(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        placeholder="40"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Attendance %</label>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={attendancePercentage}
                        onChange={(e) => setAttendancePercentage(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        placeholder="95.5"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Total Attendance</label>
                      <input
                        type="number"
                        value={totalAttendance}
                        onChange={(e) => setTotalAttendance(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        placeholder="160"
                      />
                    </div>
                  </div>

                  {/* Teacher Remarks */}
                  <div className="mt-6">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Homeroom Teacher Remarks</label>
                    <textarea
                      value={homeroomRemarks}
                      onChange={(e) => setHomeroomRemarks(e.target.value)}
                      rows="4"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                      placeholder="Enter remarks about the student's overall performance..."
                    />
                  </div>

                  {/* AI Performance Analysis */}
                  {reportData?.ai_performance_analysis && (
                    <div className="mt-6">
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        🤖 AI Performance Analysis
                      </label>
                      <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
                        <p className="text-sm text-gray-700 whitespace-pre-wrap">
                          {reportData.ai_performance_analysis}
                        </p>
                      </div>
                      <p className="text-xs text-gray-500 mt-1">
                        AI-generated analysis of student performance trends and recommendations
                      </p>
                    </div>
                  )}

                  {reportData?.academic_guidance?.printable_card?.headline && (
                    <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                      <label className="block text-sm font-medium text-emerald-900 mb-2">🎯 SHS Pathway Card</label>
                      <p className="text-sm font-bold text-emerald-900">{reportData.academic_guidance.printable_card.headline}</p>
                      {reportData.academic_guidance.printable_card.pathway_fit_score !== null && (
                        <p className="mt-1 text-xs text-emerald-800">Fit score: {Number(reportData.academic_guidance.printable_card.pathway_fit_score || 0).toFixed(1)}%</p>
                      )}
                      {reportData.academic_guidance.printable_card.focus_note && (
                        <p className="mt-2 text-sm text-emerald-900">{reportData.academic_guidance.printable_card.focus_note}</p>
                      )}
                      {reportData.academic_guidance.printable_card.secondary_pathway && (
                        <p className="mt-2 text-xs text-emerald-800">Secondary option: {reportData.academic_guidance.printable_card.secondary_pathway}</p>
                      )}
                    </div>
                  )}

                  {/* AI Performance Analysis Summary */}
                  {reportData?.ai_performance_analysis && (
                    <div className="mt-6 mb-6 border-l-4 border-purple-600 bg-purple-50 p-4 rounded-lg">
                      <div className="flex items-start gap-3">
                        <span className="text-2xl">🤖</span>
                        <div className="flex-1">
                          <h3 className="text-lg font-semibold text-purple-900 mb-2">AI Performance Analysis</h3>
                          <p className="text-sm text-purple-800 leading-relaxed">{reportData.ai_performance_analysis}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Template Preview */}
                  <div className="mt-6">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-lg font-semibold text-gray-800">Template Preview</h3>
                      <span className="text-xs text-gray-500">Live preview from the selected template</span>
                    </div>
                    <div className="p-8 bg-gray-50">
                      <div className="bg-white p-8 shadow-lg" style={{ minHeight: '500px' }}>
                        {isHtmlTemplate ? (
                          <div
                            className="min-h-80"
                            dangerouslySetInnerHTML={{ __html: templatePreviewHtml }}
                          />
                        ) : (
                          <div className="space-y-4">
                            {activeTemplateConfig?.sections?.map((section) => renderSection(section))}
                            {!activeTemplateConfig?.sections?.length && (
                              <p className="text-sm text-gray-500">No template configured.</p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="mt-6 flex gap-3">
                    <button
                      onClick={() => handleSave(false)}
                      disabled={saving}
                      className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400"
                    >
                      {saving ? 'Saving...' : 'Save Draft'}
                    </button>
                    {hasHeadmaster && (
                      <button
                        onClick={() => handleSave(true, 'headmaster')}
                        disabled={saving}
                        className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400"
                      >
                        {saving ? 'Submitting...' : 'Submit to Headmaster'}
                      </button>
                    )}
                    <button
                      onClick={() => handleSave(true, 'proprietor')}
                      disabled={saving}
                      className="px-6 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:bg-gray-400"
                    >
                      {saving ? 'Submitting...' : 'Submit to Proprietor'}
                    </button>
                    {!hasHeadmaster && (
                      <span className="text-xs text-gray-500">No headmaster assigned</span>
                    )}
                    {reportData?.status && (
                      <div className="ml-auto flex items-center">
                        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                          reportData.status === 'ProprietorApproved' || reportData.status === 'Published' ? 'bg-green-100 text-green-800' :
                          reportData.status === 'HeadmasterApproved' ? 'bg-blue-100 text-blue-800' :
                          reportData.status === 'Submitted' ? 'bg-yellow-100 text-yellow-800' :
                          reportData.status === 'Rejected' ? 'bg-red-100 text-red-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {reportData.status === 'HeadmasterApproved' ? 'Pending Proprietor' : reportData.status}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Headmaster Remarks (if any) */}
                  {showHeadmasterRemarks && reportData?.headmaster_remarks && (
                    <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
                      <p className="text-sm font-medium text-gray-700">Headmaster's Remarks:</p>
                      <p className="text-sm text-gray-600 mt-1">{reportData.headmaster_remarks}</p>
                      {reportData.headmaster_approved_at && (
                        <p className="text-xs text-gray-500 mt-2">
                          Approved on {new Date(reportData.headmaster_approved_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Proprietor Remarks (if any) */}
                  {reportData?.proprietor_remarks && (
                    <div className="mt-4 p-4 bg-purple-50 border border-purple-200 rounded-md">
                      <p className="text-sm font-medium text-gray-700">Proprietor's Remarks:</p>
                      <p className="text-sm text-gray-600 mt-1">{reportData.proprietor_remarks}</p>
                      {reportData.proprietor_approved_at && (
                        <p className="text-xs text-gray-500 mt-2">
                          Approved on {new Date(reportData.proprietor_approved_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Print Status */}
                  {reportData?.printed_at && (
                    <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-md">
                      <p className="text-sm font-medium text-green-700">
                        ✅ Report card printed on {new Date(reportData.printed_at).toLocaleDateString()}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
