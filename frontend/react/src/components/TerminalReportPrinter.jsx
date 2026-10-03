import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useBranding } from '../hooks/useBranding';

const getDiagnosticSubjects = (subjectGrades = []) =>
  (Array.isArray(subjectGrades) ? subjectGrades : []).filter(
    (grade) => Array.isArray(grade?.diagnostic_topics) && grade.diagnostic_topics.length > 0
  );

const formatDiagnosticTopicScore = (topic) => {
  const score = Number(topic?.score || 0);
  const maxScore = Number(topic?.max_score || 0);
  return `${score}/${maxScore}`;
};

const getDiagnosticTopicRatio = (topic) => {
  const maxScore = Number(topic?.max_score || 0);
  if (maxScore <= 0) {
    return 0;
  }
  return Number(topic?.score || 0) / maxScore;
};

const isWeakDiagnosticTopic = (topic) => getDiagnosticTopicRatio(topic) <= 0.55;

const getSortedDiagnosticTopics = (topics = []) =>
  [...(Array.isArray(topics) ? topics : [])].sort((left, right) => {
    const leftWeak = isWeakDiagnosticTopic(left) ? 1 : 0;
    const rightWeak = isWeakDiagnosticTopic(right) ? 1 : 0;
    if (leftWeak !== rightWeak) {
      return rightWeak - leftWeak;
    }
    return getDiagnosticTopicRatio(left) - getDiagnosticTopicRatio(right);
  });

const getWeakDiagnosticTopics = (topics = []) =>
  getSortedDiagnosticTopics(topics).filter((topic) => isWeakDiagnosticTopic(topic));

const getStrongDiagnosticTopics = (topics = []) =>
  getSortedDiagnosticTopics(topics).filter((topic) => !isWeakDiagnosticTopic(topic));

const currentAcademicYear = () => {
  const today = new Date();
  const startYear = today.getMonth() >= 7 ? today.getFullYear() : today.getFullYear() - 1;
  return `${startYear}/${startYear + 1}`;
};

export default function TerminalReportPrinter() {
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [selectedStudent, setSelectedStudent] = useState('');
  const [selectedTerm, setSelectedTerm] = useState('Term 1');
  const [selectedYear, setSelectedYear] = useState(currentAcademicYear);
  const [termContextLoading, setTermContextLoading] = useState(true);
  const [previewData, setPreviewData] = useState({});
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [headmasterRemarks, setHeadmasterRemarks] = useState('');
  const [proprietorRemarks, setProprietorRemarks] = useState('');
  const [showHeadmasterRemarks, setShowHeadmasterRemarks] = useState(true);
  const [saving, setSaving] = useState(false);
  const [performanceHistory, setPerformanceHistory] = useState([]);
  const [gradingScheme, setGradingScheme] = useState({ classScoreMax: 30, examScoreMax: 70 });
  const [promotionData, setPromotionData] = useState({ new_class: '', remarks: '' });
  const [promotingStudent, setPromotingStudent] = useState(false);
  const userRole = localStorage.getItem('role') || 'proprietor';
  const { branding } = useBranding();

  useEffect(() => {
    fetchClasses();
    fetchGradingScheme();
    let cancelled = false;
    const fetchActiveTerm = async () => {
      try {
        const response = await axios.get('/api/school/terms', {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
            'X-School-ID': localStorage.getItem('school_id'),
          },
        });
        const activeTerm = response.data?.terms?.find((term) => term.is_active);
        if (!cancelled && activeTerm) {
          if (activeTerm.academic_year) setSelectedYear(activeTerm.academic_year);
          if (activeTerm.name) setSelectedTerm(activeTerm.name);
        }
      } catch {
        if (!cancelled) setSelectedYear(currentAcademicYear());
      } finally {
        if (!cancelled) setTermContextLoading(false);
      }
    };
    fetchActiveTerm();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (selectedClass) {
      fetchStudents(selectedClass);
    }
  }, [selectedClass]);

  useEffect(() => {
    if (!termContextLoading && selectedStudent && selectedClass) {
      fetchReportData();
    }
  }, [selectedStudent, selectedClass, selectedTerm, selectedYear, termContextLoading]);

  const fetchClasses = async () => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get('/api/school/grades', { headers });
      
      // /api/school/grades returns a simple array of grade/class names
      const classList = Array.isArray(res.data) ? res.data : [];
      
      setClasses(classList);
      
      if (classList.length > 0) {
        setSelectedClass(classList[0]);
        setMessage(`✅ Loaded ${classList.length} classes`);
      } else {
        setMessage('⚠️ No classes found');
      }
    } catch (err) {
      console.error('Failed to load classes:', err);
      setMessage(`❌ Error loading classes: ${err.response?.data?.message || err.message}`);
    }
  };

  const fetchGradingScheme = async () => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get('/api/school/grading-scheme', { headers });
      setGradingScheme({
        classScoreMax: res.data.class_score_max || 30,
        examScoreMax: res.data.exam_score_max || 70
      });
    } catch (err) {
      console.error('Failed to load grading scheme');
    }
  };

  const fetchStudents = async (className) => {
    try {
      setMessage('Loading students...');
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      
      const res = await axios.get(`/api/students/by-class/${encodeURIComponent(className)}`, { headers });
      
      let studentList = [];
      if (Array.isArray(res.data)) {
        studentList = res.data;
      } else if (res.data?.students) {
        studentList = res.data.students;
      }
      
      setStudents(studentList);
      
      if (studentList.length > 0) {
        setSelectedStudent(studentList[0].id || studentList[0].student_id);
        setMessage(`✅ Loaded ${studentList.length} students`);
      } else {
        setMessage('⚠️ No students in this class');
        setPreviewData({});
      }
    } catch (err) {
      console.error('Failed to load students:', err);
      setMessage(`❌ Error loading students: ${err.response?.data?.message || err.message}`);
      setStudents([]);
    }
  };

  const fetchPerformanceHistory = async (studentId) => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      
      const res = await axios.get(`/api/students/${studentId}/reports`, { headers });
      
      if (res.data && Array.isArray(res.data)) {
        const history = res.data
          .filter(r => r.term_average)
          .map(r => ({
            term: r.academic_term,
            year: r.academic_year,
            average: parseFloat(r.term_average)
          }))
          .slice(-5); // Last 5 terms
        
        setPerformanceHistory(history);
      }
    } catch (err) {
      console.error('Failed to load performance history:', err);
      setPerformanceHistory([]);
    }
  };

  const fetchReportData = async () => {
    try {
      setLoading(true);
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      
      const res = await axios.get(`/api/students/${selectedStudent}/terminal-report`, {
        params: { term: selectedTerm, year: selectedYear },
        headers
      });
      
      setPreviewData(res.data);
      setHeadmasterRemarks(res.data.headmaster_remarks || '');
      setProprietorRemarks(res.data.proprietor_remarks || '');
      
      // Fetch performance history for trend visualization
      fetchPerformanceHistory(selectedStudent);
      setMessage('');
    } catch (err) {
      console.error('Failed to load report data:', err);
      setPreviewData({});
      setMessage(`⚠️ No report data available`);
    } finally {
      setLoading(false);
    }
  };

  const saveRemarks = async () => {
    try {
      setSaving(true);
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      
      const payload = {
        headmaster_remarks: headmasterRemarks,
        proprietor_remarks: proprietorRemarks,
        show_headmaster_remarks: showHeadmasterRemarks,
        term: selectedTerm,
        year: selectedYear
      };
      
      await axios.post(`/api/students/${selectedStudent}/terminal-report/remarks`, payload, { headers });
      setMessage('✅ Remarks saved successfully!');
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage(`❌ Error saving remarks: ${err.response?.data?.message || err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const promoteStudent = async () => {
    if (!promotionData.new_class) {
      setMessage('❌ Please select a new class');
      return;
    }

    try {
      setPromotingStudent(true);
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      
      const payload = {
        term: selectedTerm,
        year: selectedYear,
        new_class: promotionData.new_class,
        remarks: promotionData.remarks || `Promoted after ${selectedTerm} approval`
      };
      
      await axios.post(`/api/students/${selectedStudent}/terminal-report/promote`, payload, { headers });
      setMessage(`✅ Student promoted to ${promotionData.new_class}!`);
      setPromotionData({ new_class: '', remarks: '' });
      fetchReportData(); // Refresh to show updated promotion info
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage(`❌ Error promoting student: ${err.response?.data?.message || err.message}`);
    } finally {
      setPromotingStudent(false);
    }
  };

  const handlePrintReport = () => {
    if (!previewData || Object.keys(previewData).length === 0) {
      setMessage('❌ No report data to print');
      return;
    }
    
    const html = buildPrintReportHtml();
    const win = window.open('', '_blank', 'width=1000,height=1200');
    if (!win) {
      setMessage('❌ Pop-up blocked. Please allow pop-ups to print.');
      return;
    }
    win.document.open();
    win.document.write(html);
    win.document.close();
    win.focus();
  };

  const diagnosticSubjects = getDiagnosticSubjects(previewData.subject_grades);

  const handleExportReport = () => {
    const schoolId = localStorage.getItem('school_id');
    const headers = {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    };
    axios
      .get(`/api/proprietor/export-term-summary?school_id=${schoolId}`, {
        headers,
        responseType: 'blob'
      })
      .then((res) => {
        const blob = new Blob([res.data], { type: res.headers['content-type'] || 'application/octet-stream' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `term-report-${schoolId}.xlsx`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      })
      .catch((err) => {
        setMessage(`❌ Export failed: ${err.response?.data?.message || err.message}`);
      });
  };

  const buildPrintReportHtml = () => {
    return `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="UTF-8" />
          <title>${previewData.student_name || 'Terminal Report'}</title>
          <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Arial, sans-serif; color: #1f2937; background: #fff; padding: 20px; line-height: 1.6; }
            .container { max-width: 900px; margin: 0 auto; background: white; padding: 40px; }
            
            .report-header {
              text-align: center;
              margin-bottom: 40px;
              padding-bottom: 30px;
              border-bottom: 3px solid #1e3a8a;
            }
            
            .school-logo { height: 60px; width: auto; margin: 0 auto 15px; display: block; }
            
            .school-name {
              font-size: 28px;
              font-weight: bold;
              color: #1e3a8a;
              margin-bottom: 8px;
              letter-spacing: 0.5px;
            }
            
            .school-motto {
              font-size: 14px;
              color: #6b7280;
              font-style: italic;
              margin-bottom: 12px;
            }
            
            .school-contact { font-size: 11px; color: #9ca3af; line-height: 1.5; }
            
            .report-title {
              text-align: center;
              font-size: 18px;
              font-weight: bold;
              color: #1f2937;
              margin: 30px 0;
              text-transform: uppercase;
              letter-spacing: 1px;
            }
            
            .section { margin-bottom: 24px; page-break-inside: avoid; }
            
            .section-title {
              font-size: 13px;
              font-weight: bold;
              color: white;
              background: #1e3a8a;
              padding: 10px 15px;
              margin-bottom: 12px;
              border-radius: 4px;
            }
            
            .field-grid {
              display: grid;
              grid-template-columns: repeat(2, 1fr);
              gap: 12px;
              padding: 12px;
              background: #f9fafb;
              border-radius: 4px;
              border: 1px solid #e5e7eb;
            }
            
            .field-row { font-size: 12px; display: flex; justify-content: space-between; }
            .field-label { font-weight: bold; color: #374151; }
            .field-value { color: #6b7280; }
            
            .remarks-box {
              padding: 12px;
              background: #f9fafb;
              border-radius: 4px;
              border-left: 3px solid #1e3a8a;
              margin: 12px 0;
              font-size: 12px;
            }
            
            .grades-table {
              width: 100%;
              border-collapse: collapse;
              margin: 12px 0;
              font-size: 11px;
            }
            
            .grades-table thead {
              background: #1e3a8a;
              color: white;
            }
            
            .grades-table th {
              padding: 10px 8px;
              text-align: center;
              font-weight: bold;
              font-size: 10px;
              text-transform: uppercase;
              letter-spacing: 0.5px;
            }
            
            .grades-table th:first-child {
              text-align: left;
            }
            
            .grades-table td {
              padding: 8px;
              text-align: center;
              border-bottom: 1px solid #e5e7eb;
            }
            
            .grades-table td:first-child {
              text-align: left;
              font-weight: bold;
              color: #1f2937;
            }
            
            .grades-table tbody tr:nth-child(even) {
              background: #f9fafb;
            }
            
            .grade-badge {
              display: inline-block;
              padding: 3px 8px;
              border-radius: 4px;
              font-weight: bold;
              font-size: 10px;
            }
            
            .grade-A { background: #d1fae5; color: #065f46; }
            .grade-B { background: #dbeafe; color: #1e40af; }
            .grade-C { background: #fef3c7; color: #92400e; }
            .grade-D { background: #fed7aa; color: #9a3412; }
            .grade-E, .grade-F { background: #fee2e2; color: #991b1b; }
            
            .signature-grid {
              display: grid;
              grid-template-columns: repeat(3, 1fr);
              gap: 30px;
              margin-top: 40px;
            }
            
            .signature-block { text-align: center; }
            .signature-line { border-bottom: 1px solid #1f2937; height: 40px; margin-bottom: 8px; }
            .signature-label { font-size: 11px; font-weight: bold; }
            
            .footer {
              text-align: center;
              font-size: 10px;
              color: #9ca3af;
              margin-top: 40px;
              padding-top: 20px;
              border-top: 1px solid #e5e7eb;
            }
            
            @media print { body { padding: 0; } .container { padding: 0; } }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="report-header">
              ${branding.logo || branding.logo_url ? `<img src="${branding.logo || branding.logo_url}" alt="School Logo" class="school-logo" />` : ''}
              <div class="school-name">${branding.school_name || branding.name || 'School Name'}</div>
              ${branding.school_motto || branding.motto ? `<div class="school-motto">"${branding.school_motto || branding.motto}"</div>` : ''}
              <div class="school-contact">
                ${branding.school_address || branding.address ? `<div>${branding.school_address || branding.address}</div>` : ''}
                ${branding.school_phone || branding.phone ? `<div>📞 ${branding.school_phone || branding.phone}</div>` : ''}
              </div>
            </div>
            
            <div class="report-title">📄 Terminal Report Card</div>
            
            <div class="section">
              <div class="section-title">Student Information</div>
              <div class="field-grid">
                <div class="field-row">
                  <span class="field-label">Student Name:</span>
                  <span class="field-value">${previewData.student_name || '-'}</span>
                </div>
                <div class="field-row">
                  <span class="field-label">Student ID:</span>
                  <span class="field-value">${previewData.student_code || '-'}</span>
                </div>
                <div class="field-row">
                  <span class="field-label">Class:</span>
                  <span class="field-value">${previewData.class_name || '-'}</span>
                </div>
                <div class="field-row">
                  <span class="field-label">Term:</span>
                  <span class="field-value">${selectedTerm}</span>
                </div>
                <div class="field-row">
                  <span class="field-label">Term Start:</span>
                  <span class="field-value">${previewData.term_calendar?.term_start_date || '-'}</span>
                </div>
                <div class="field-row">
                  <span class="field-label">Vacation Day:</span>
                  <span class="field-value">${previewData.term_calendar?.vacation_date || '-'}</span>
                </div>
                <div class="field-row">
                  <span class="field-label">Reopening Date:</span>
                  <span class="field-value">${previewData.term_calendar?.reopening_date || '-'}</span>
                </div>
              </div>
            </div>
            
            ${previewData.term_average ? `
              <div class="section">
                <div class="section-title">Performance Summary</div>
                <div class="field-grid">
                  <div class="field-row">
                    <span class="field-label">Average Mark:</span>
                    <span class="field-value">${previewData.term_average}%</span>
                  </div>
                  <div class="field-row">
                    <span class="field-label">Class Position:</span>
                    <span class="field-value">${previewData.overall_position || '-'}</span>
                  </div>
                  <div class="field-row">
                    <span class="field-label">Grading Scheme:</span>
                    <span class="field-value">Class Work ${gradingScheme.classScoreMax}% • Exam ${gradingScheme.examScoreMax}%</span>
                  </div>
                </div>
              </div>
            ` : ''}
            
            ${previewData.subject_grades && previewData.subject_grades.length > 0 ? `
              <div class="section">
                <div class="section-title">📚 Subject Performance</div>
                <table class="grades-table">
                  <thead>
                    <tr>
                      <th>Subject</th>
                      <th>Class Score</th>
                      <th>Exam Score</th>
                      <th>Total</th>
                      <th>Position</th>
                      <th>Grade</th>
                      <th>Remarks</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${previewData.subject_grades.map(grade => `
                      <tr>
                        <td>${grade.subject || '-'}</td>
                        <td>${grade.class_score !== undefined ? grade.class_score : '-'}</td>
                        <td>${grade.exam_score !== undefined ? grade.exam_score : '-'}</td>
                        <td style="font-weight: bold;">${grade.total !== undefined ? grade.total : '-'}</td>
                        <td>${grade.position || '-'}</td>
                        <td><span class="grade-badge grade-${grade.grade || 'F'}">${grade.grade || '-'}</span></td>
                        <td style="font-size: 9px; text-align: left;">${grade.remarks || '-'}</td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
            ` : ''}

            ${getDiagnosticSubjects(previewData.subject_grades).length > 0 ? `
              <div class="section">
                <div class="section-title">🧭 Diagnostic Strand Insights</div>
                <div style="display: grid; gap: 10px;">
                  ${getDiagnosticSubjects(previewData.subject_grades).map((grade) => {
                    const weakTopics = getWeakDiagnosticTopics(grade.diagnostic_topics);
                    const strongTopics = getStrongDiagnosticTopics(grade.diagnostic_topics);
                    const visibleTopics = weakTopics.length > 0 ? weakTopics : getSortedDiagnosticTopics(grade.diagnostic_topics);
                    return `
                    <div style="border: 1px solid #bfdbfe; border-radius: 10px; background: #eff6ff; padding: 12px;">
                      <div style="font-weight: 700; color: #1e3a8a; margin-bottom: 6px;">${grade.subject || 'Subject'}</div>
                      ${weakTopics.length > 0 ? `<div style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: #b45309; margin-bottom: 6px;">Weak strands needing attention</div>` : `<div style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: #1d4ed8; margin-bottom: 6px;">All recorded strands are within expected range</div>`}
                      <div style="font-size: 11px; color: #334155; line-height: 1.6;">
                        ${visibleTopics
                          .map((topic) => `${isWeakDiagnosticTopic(topic) ? 'Needs attention: ' : ''}${topic.topic}: ${formatDiagnosticTopicScore(topic)}`)
                          .join(' • ')}
                      </div>
                      ${weakTopics.length > 0 && strongTopics.length > 0 ? `<div style="font-size: 10px; color: #64748b; margin-top: 6px;">${strongTopics.length} stronger strand(s) hidden from print to keep the report focused on intervention priorities.</div>` : ''}
                    </div>
                  `;
                  }).join('')}
                </div>
              </div>
            ` : ''}
            
            ${previewData.homeroom_teacher_remarks ? `
              <div class="section">
                <div class="section-title">Class Teacher Remark</div>
                <div class="remarks-box">${previewData.homeroom_teacher_remarks}</div>
              </div>
            ` : ''}
            
            ${showHeadmasterRemarks && headmasterRemarks ? `
              <div class="section">
                <div class="section-title">Headmaster Remark</div>
                <div class="remarks-box" style="border-left-color: #7c2d12;">${headmasterRemarks}</div>
              </div>
            ` : ''}
            
            ${proprietorRemarks ? `
              <div class="section">
                <div class="section-title">Proprietor Remark</div>
                <div class="remarks-box" style="border-left-color: #0369a1;">${proprietorRemarks}</div>
              </div>
            ` : ''}
            
            ${previewData.ai_performance_analysis ? `
              <div class="section">
                <div class="section-title">🤖 AI Performance Analysis & Trends</div>
                <div class="remarks-box" style="border-left-color: #7c3aed; background: #faf5ff;">
                  ${previewData.ai_performance_analysis}
                </div>
              </div>
            ` : ''}
            
            <div class="section">
              <div class="signature-grid">
                <div class="signature-block">
                  <div class="signature-line"></div>
                  <div class="signature-label">Class Teacher</div>
                </div>
                <div class="signature-block">
                  <div class="signature-line"></div>
                  <div class="signature-label">Headmaster</div>
                </div>
                <div class="signature-block">
                  <div class="signature-line"></div>
                  <div class="signature-label">Proprietor</div>
                </div>
              </div>
            </div>
            
            <div class="footer">
              <p>This is an official terminal report from ${branding.school_name || branding.name || 'the school'}</p>
              <p>Generated on ${new Date().toLocaleString()}</p>
            </div>
          </div>
        </body>
      </html>
    `;
  };

  return (
    <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-2">
        <h2 className="text-2xl font-bold text-slate-800">📄 Terminal Reports</h2>
      </div>
      <p className="text-slate-600 text-sm mb-6">
        Generate professional terminal reports with remarks from headmaster and proprietor
      </p>

      {message && (
        <div className={`mb-6 p-4 rounded-lg ${message.includes('✅') ? 'bg-green-50 text-green-800 border border-green-200' : message.includes('❌') ? 'bg-red-50 text-red-800 border border-red-200' : 'bg-blue-50 text-blue-800 border border-blue-200'}`}>
          {message}
        </div>
      )}

      {/* Selection Panel */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 bg-slate-50 p-6 rounded-2xl">
        <div>
          <label className="block text-sm font-bold text-slate-700 mb-2">📚 Class</label>
          <select
            value={selectedClass}
            onChange={(e) => setSelectedClass(e.target.value)}
            className="w-full p-3 border rounded-lg bg-white text-sm font-medium"
          >
            {classes.length === 0 ? (
              <option>Loading classes...</option>
            ) : (
              classes.map((cls) => (
                <option key={cls} value={cls}>{cls}</option>
              ))
            )}
          </select>
        </div>

        <div>
          <label className="block text-sm font-bold text-slate-700 mb-2">👤 Student</label>
          <select
            value={selectedStudent}
            onChange={(e) => setSelectedStudent(e.target.value)}
            className="w-full p-3 border rounded-lg bg-white text-sm font-medium"
          >
            {students.length === 0 ? (
              <option>Select a class first</option>
            ) : (
              students.map((s) => (
                <option key={s.id || s.student_id} value={s.id || s.student_id}>
                  {s.name}
                </option>
              ))
            )}
          </select>
        </div>

        <div>
          <label className="block text-sm font-bold text-slate-700 mb-2">🗓️ Term</label>
          <select
            value={selectedTerm}
            disabled={termContextLoading}
            aria-label="Report Term"
            onChange={(e) => setSelectedTerm(e.target.value)}
            className="w-full p-3 border rounded-lg bg-white text-sm font-medium"
          >
            {!['Term 1', 'Term 2', 'Term 3'].includes(selectedTerm) && <option>{selectedTerm}</option>}
            <option>Term 1</option>
            <option>Term 2</option>
            <option>Term 3</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-bold text-slate-700 mb-2">📅 Year</label>
          <input
            type="text"
            value={selectedYear}
            disabled={termContextLoading}
            aria-label="Report Year"
            onChange={(e) => setSelectedYear(e.target.value)}
            className="w-full p-3 border rounded-lg bg-white text-sm font-medium"
          />
        </div>
      </div>

      {/* Report Content */}
      {loading ? (
        <div className="text-center py-12">
          <p className="text-lg font-semibold text-slate-600">⏳ Loading report...</p>
        </div>
      ) : Object.keys(previewData).length > 0 ? (
        <div className="space-y-6">
          {/* Student Summary */}
          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-6">
            <h3 className="text-lg font-bold text-slate-800">{previewData.student_name}</h3>
            <p className="text-sm text-slate-600">{previewData.class_name} • {selectedTerm} • {selectedYear}</p>
            {previewData.term_average && (
              <p className="text-sm font-bold text-blue-600 mt-2">Average: {previewData.term_average}%</p>
            )}
            <div className="mt-3 pt-3 border-t border-blue-300 flex items-center gap-4 text-xs text-slate-600">
              <span><strong>Grading Scheme:</strong> Class Work {gradingScheme.classScoreMax}% • Exam {gradingScheme.examScoreMax}%</span>
            </div>
            {(previewData.term_calendar?.term_start_date || previewData.term_calendar?.vacation_date || previewData.term_calendar?.reopening_date) && (
              <div className="mt-3 text-xs text-slate-700 space-y-1">
                <p><strong>Term Start:</strong> {previewData.term_calendar?.term_start_date || '-'}</p>
                <p><strong>Vacation Day:</strong> {previewData.term_calendar?.vacation_date || '-'}</p>
                <p><strong>Reopening Date:</strong> {previewData.term_calendar?.reopening_date || '-'}</p>
              </div>
            )}
          </div>

          {/* Performance Trend Graph */}
          {performanceHistory.length > 0 && (
            <div className="bg-linear-to-br from-purple-50 to-pink-50 border border-purple-200 rounded-2xl p-6">
              <h4 className="text-lg font-bold text-purple-800 mb-4">📊 Performance Trend Analysis</h4>
              
              {/* Visual Graph */}
              <div className="bg-white rounded-lg p-4 mb-4">
                <div className="flex items-end justify-between h-40 gap-2">
                  {performanceHistory.map((record, idx) => {
                    const height = (record.average / 100) * 100; // Convert to percentage of graph height
                    const isLast = idx === performanceHistory.length - 1;
                    const prevAvg = idx > 0 ? performanceHistory[idx - 1].average : record.average;
                    const trend = record.average > prevAvg ? '📈' : record.average < prevAvg ? '📉' : '➡️';
                    
                    return (
                      <div key={idx} className="flex-1 flex flex-col items-center">
                        <div className="text-xs font-bold text-slate-700 mb-1">{record.average}%</div>
                        <div 
                          className={`w-full rounded-t-lg transition-all ${
                            isLast ? 'bg-linear-to-t from-purple-600 to-purple-400' : 
                            record.average >= 70 ? 'bg-green-400' : 
                            record.average >= 50 ? 'bg-yellow-400' : 'bg-red-400'
                          }`}
                          style={{ height: `${height}%` }}
                          title={`${record.term} ${record.year}: ${record.average}%`}
                        ></div>
                        <div className="text-xs text-slate-600 mt-2 text-center">
                          <div>{record.term}</div>
                          <div className="text-[10px] text-slate-500">{record.year}</div>
                          {!isLast && <div className="text-lg">{trend}</div>}
                        </div>
                      </div>
                    );
                  })}
                </div>
                
                {/* Reference Lines */}
                <div className="flex justify-between mt-2 pt-2 border-t text-xs text-slate-500">
                  <span>0%</span>
                  <span>50%</span>
                  <span>100%</span>
                </div>
              </div>
              
              {/* Trend Summary */}
              <div className="flex items-center gap-2 text-sm">
                <span className="font-bold text-slate-700">Trend:</span>
                {performanceHistory.length >= 2 && (
                  <>
                    {performanceHistory[performanceHistory.length - 1].average > 
                     performanceHistory[performanceHistory.length - 2].average ? (
                      <span className="text-green-700 font-semibold">📈 Improving</span>
                    ) : performanceHistory[performanceHistory.length - 1].average < 
                      performanceHistory[performanceHistory.length - 2].average ? (
                      <span className="text-orange-700 font-semibold">📉 Declining</span>
                    ) : (
                      <span className="text-blue-700 font-semibold">➡️ Stable</span>
                    )}
                    <span className="text-slate-600">
                      ({Math.abs(performanceHistory[performanceHistory.length - 1].average - 
                         performanceHistory[performanceHistory.length - 2].average).toFixed(1)}% change)
                    </span>
                  </>
                )}
              </div>
            </div>
          )}

          {/* AI Analysis Display */}
          {previewData.ai_performance_analysis && (
            <div className="bg-linear-to-br from-cyan-50 to-blue-50 border border-cyan-200 rounded-2xl p-6">
              <h4 className="text-lg font-bold text-cyan-800 mb-3">🤖 AI Performance Analysis</h4>
              <div className="text-sm text-slate-700 leading-relaxed bg-white rounded-lg p-4 border border-cyan-100">
                {previewData.ai_performance_analysis}
              </div>
            </div>
          )}

          {diagnosticSubjects.length > 0 && (
            <div className="bg-linear-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-2xl p-6">
              <h4 className="text-lg font-bold text-blue-900 mb-3">🧭 Diagnostic Strand Insights</h4>
              <div className="space-y-3">
                {diagnosticSubjects.map((grade, index) => {
                  const weakTopics = getWeakDiagnosticTopics(grade.diagnostic_topics);
                  const strongTopics = getStrongDiagnosticTopics(grade.diagnostic_topics);
                  const visibleTopics = weakTopics.length > 0 ? weakTopics : [];

                  return (
                    <div key={`${grade.subject || 'subject'}-${index}`} className="rounded-xl border border-blue-100 bg-white p-4">
                      <p className="text-sm font-bold text-blue-900 mb-2">{grade.subject || 'Subject'}</p>
                      {weakTopics.length > 0 ? (
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-700">Weak strands shown by default</p>
                      ) : (
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-blue-700">No weak strands flagged</p>
                      )}
                      {visibleTopics.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {visibleTopics.map((topic, topicIndex) => (
                            <span
                              key={`${topic.topic || 'topic'}-${topicIndex}`}
                              className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-900 ring-1 ring-amber-300"
                            >
                              Needs attention: {topic.topic}: {formatDiagnosticTopicScore(topic)}
                            </span>
                          ))}
                        </div>
                      )}
                      {strongTopics.length > 0 && (
                        <details className="mt-3 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2">
                          <summary className="cursor-pointer text-xs font-semibold text-blue-800">
                            Show all assessed strands ({strongTopics.length} more)
                          </summary>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {strongTopics.map((topic, topicIndex) => (
                              <span
                                key={`${topic.topic || 'strong-topic'}-${topicIndex}`}
                                className="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-900"
                              >
                                {topic.topic}: {formatDiagnosticTopicScore(topic)}
                              </span>
                            ))}
                          </div>
                        </details>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {previewData.academic_guidance?.printable_card?.headline && (
            <div className="bg-linear-to-br from-emerald-50 to-lime-50 border border-emerald-200 rounded-2xl p-6">
              <h4 className="text-lg font-bold text-emerald-800 mb-3">🎯 SHS Pathway Card</h4>
              <div className="bg-white rounded-lg p-4 border border-emerald-100 text-sm text-slate-700 space-y-2">
                <p className="font-bold text-emerald-900">{previewData.academic_guidance.printable_card.headline}</p>
                {previewData.academic_guidance.printable_card.pathway_fit_score !== null && (
                  <p>Fit score: {Number(previewData.academic_guidance.printable_card.pathway_fit_score || 0).toFixed(1)}%</p>
                )}
                {previewData.academic_guidance.printable_card.focus_note && (
                  <p>{previewData.academic_guidance.printable_card.focus_note}</p>
                )}
                {previewData.academic_guidance.printable_card.secondary_pathway && (
                  <p>Secondary option: {previewData.academic_guidance.printable_card.secondary_pathway}</p>
                )}
              </div>
            </div>
          )}

          {/* Headmaster Remarks */}
          <div className="bg-orange-50 border border-orange-200 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-lg font-bold text-orange-800">👨‍🏫 Headmaster Remarks</h4>
              <label className="flex items-center gap-2 text-sm font-bold">
                <input
                  type="checkbox"
                  checked={showHeadmasterRemarks}
                  onChange={(e) => setShowHeadmasterRemarks(e.target.checked)}
                  className="h-4 w-4 rounded"
                />
                Include
              </label>
            </div>
            {showHeadmasterRemarks && (
              <textarea
                value={headmasterRemarks}
                onChange={(e) => setHeadmasterRemarks(e.target.value)}
                placeholder="Headmaster remarks..."
                className="w-full p-4 border rounded-lg bg-white text-sm resize-none"
                rows={3}
                disabled={userRole === 'proprietor'}
              />
            )}
          </div>

          {/* Proprietor Remarks */}
          <div className="bg-cyan-50 border border-cyan-200 rounded-2xl p-6">
            <h4 className="text-lg font-bold text-cyan-800 mb-4">🏢 Proprietor Remarks</h4>
            <textarea
              value={proprietorRemarks}
              onChange={(e) => setProprietorRemarks(e.target.value)}
              placeholder="Proprietor remarks..."
              className="w-full p-4 border rounded-lg bg-white text-sm resize-none"
              rows={3}
            />
          </div>

          {/* Student Promotion Section - Only Show for Term 3 */}
          {selectedTerm.includes('Term 3') || selectedTerm.includes('3') ? (
            <div className="bg-linear-to-r from-indigo-50 to-purple-50 border border-indigo-300 rounded-2xl p-6">
              <h4 className="text-lg font-bold text-indigo-900 mb-4">📚 Promote to Next Class</h4>
              <p className="text-sm text-indigo-700 mb-4">Automatically promote student to next class after Term 3 approval</p>
              
              {previewData.promotion && (
                <div className="mb-4 p-3 bg-green-50 border border-green-300 rounded-lg">
                  <p className="text-sm text-green-800">
                    <strong>✅ Already Promoted:</strong> {previewData.promotion.promoted_to_class} on {new Date(previewData.promotion.promotion_date).toLocaleDateString()} by {previewData.promotion.promoted_by}
                  </p>
                  {previewData.promotion.remarks && <p className="text-xs text-green-700 mt-2">Remarks: {previewData.promotion.remarks}</p>}
                </div>
              )}
              
              {!previewData.promotion && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-bold text-indigo-900 mb-2">Current Class</label>
                      <input
                        type="text"
                        value={previewData.class_name || 'N/A'}
                        disabled
                        className="w-full p-3 border rounded-lg bg-slate-100 text-slate-700 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-bold text-indigo-900 mb-2">Promote To</label>
                      <select
                        value={promotionData.new_class}
                        onChange={(e) => setPromotionData({ ...promotionData, new_class: e.target.value })}
                        className="w-full p-3 border rounded-lg bg-white text-sm font-medium"
                      >
                        <option value="">Select new class...</option>
                        {['Nursery', 'KG', 'Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5', 'Class 6', 'JHS 1', 'JHS 2', 'JHS 3'].map(cls => (
                          <option key={cls} value={cls}>{cls}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-bold text-indigo-900 mb-2">Remarks (Optional)</label>
                    <input
                      type="text"
                      value={promotionData.remarks}
                      onChange={(e) => setPromotionData({ ...promotionData, remarks: e.target.value })}
                      placeholder="e.g., Excellent performance in all subjects"
                      className="w-full p-3 border rounded-lg bg-white text-sm"
                    />
                  </div>
                  <button
                    onClick={promoteStudent}
                    disabled={promotingStudent || !promotionData.new_class}
                    className="w-full px-6 py-3 bg-indigo-600 text-white font-bold rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {promotingStudent ? '⏳ Promoting...' : '🎓 Promote Student'}
                  </button>
                </div>
              )}
            </div>
          ) : null}

          {/* Action Buttons */}
          <div className="flex gap-4">
            <button
              onClick={saveRemarks}
              disabled={saving}
              className="flex-1 px-6 py-3 bg-slate-600 text-white font-bold rounded-lg hover:bg-slate-700 disabled:opacity-50"
            >
              {saving ? '⏳ Saving...' : '💾 Save Remarks'}
            </button>
            <button
              onClick={handlePrintReport}
              className="flex-1 px-6 py-3 bg-blue-600 text-white font-bold rounded-lg hover:bg-blue-700"
            >
              🖨️ Print Report
            </button>
          </div>
        </div>
      ) : (
        <div className="text-center py-12 bg-slate-50 rounded-2xl border-2 border-dashed border-slate-300">
          <p className="text-slate-600 text-lg">📭 No report data available</p>
          <p className="text-slate-500 text-sm mt-2">Select a student to view their terminal report</p>
          <button
            onClick={handleExportReport}
            className="mt-6 px-6 py-3 bg-slate-800 text-white rounded-xl text-sm font-bold hover:bg-slate-700 transition-all"
          >
            📥 Export Term Report
          </button>
        </div>
      )}
    </div>
  );
}
