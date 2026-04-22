import React, { useEffect, useState } from 'react';
import axios from 'axios';

function getRiskTone(riskLevel) {
  switch (riskLevel) {
    case 'Critical':
      return 'bg-red-100 text-red-700 border-red-200';
    case 'High':
      return 'bg-orange-100 text-orange-700 border-orange-200';
    case 'Moderate':
      return 'bg-amber-100 text-amber-700 border-amber-200';
    default:
      return 'bg-slate-100 text-slate-700 border-slate-200';
  }
}

function getUrgencyLabel(urgency) {
  switch (urgency) {
    case 'today':
      return 'Today';
    case 'this_week':
      return 'This week';
    default:
      return 'Review';
  }
}

function buildClientReport(students, currentReport = {}) {
  return {
    ...currentReport,
    open_cases: students.filter((student) => student.case_status === 'Open').length,
    in_progress_cases: students.filter((student) => student.case_status === 'In Progress').length,
    resolved_cases: students.filter((student) => student.case_status === 'Resolved').length,
    critical_cases: students.filter((student) => student.risk_level === 'Critical').length
  };
}

export default function StudentRescueAgent({
  showPremiumOnly = false,
  endpointBase = '/api/proprietor/student-rescue-agent',
  premiumUpgradePath = '?tab=subscription'
}) {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [loggingOutcome, setLoggingOutcome] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [outcomeMessage, setOutcomeMessage] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [riskFilter, setRiskFilter] = useState('All');
  const [emailDraft, setEmailDraft] = useState({ subject: '', body: '' });

  const authHeaders = {
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id')
  };

  useEffect(() => {
    let mounted = true;

    const fetchRescuePayload = async () => {
      try {
        const res = await axios.get(endpointBase, {
          headers: authHeaders
        });

        if (mounted) {
          setPayload(res.data);
          setLoading(false);
        }
      } catch (error) {
        console.error('Failed to fetch student rescue agent payload', error);
        if (mounted) {
          setPayload({ summary: {}, students: [] });
          setLoading(false);
        }
      }
    };

    fetchRescuePayload();
    const interval = setInterval(fetchRescuePayload, 60000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [endpointBase]);

  useEffect(() => {
    if (!selectedStudent) {
      setEmailDraft({ subject: '', body: '' });
      return;
    }

    setEmailDraft({
      subject: selectedStudent.contact_templates?.email_subject || '',
      body: selectedStudent.contact_templates?.email_body || ''
    });
  }, [selectedStudent]);

  const syncStudentInPayload = (studentId, updates) => {
    setPayload((currentPayload) => {
      if (!currentPayload?.students) return currentPayload;
      const nextStudents = currentPayload.students.map((student) => (
        student.id === studentId ? { ...student, ...updates } : student
      ));
      return {
        ...currentPayload,
        students: nextStudents,
        report: buildClientReport(nextStudents, currentPayload.report)
      };
    });
    setSelectedStudent((currentStudent) => {
      if (!currentStudent || currentStudent.id !== studentId) return currentStudent;
      return { ...currentStudent, ...updates };
    });
  };

  const handleCopy = async (text, label) => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setOutcomeMessage(`${label} copied.`);
      setTimeout(() => setOutcomeMessage(''), 2500);
    } catch (error) {
      console.error(`Failed to copy ${label.toLowerCase()}`, error);
      setOutcomeMessage(`Failed to copy ${label.toLowerCase()}.`);
      setTimeout(() => setOutcomeMessage(''), 2500);
    }
  };

  const handleLogOutcome = async (actionCode) => {
    if (!selectedStudent) return;

    const needsNotes = actionCode === 'payment_plan_agreed' || actionCode === 'resolved';
    const notes = needsNotes
      ? window.prompt('Add a short note for this rescue outcome (optional):', '')
      : '';

    if (notes === null) return;

    setLoggingOutcome(true);
    try {
      const response = await axios.post(
        `${endpointBase}/outcome`,
        {
          student_id: selectedStudent.id,
          action_code: actionCode,
          notes: notes || ''
        },
        { headers: authHeaders }
      );

      const recentOutcomes = response.data.recent_outcomes || [];
      syncStudentInPayload(selectedStudent.id, {
        recent_outcomes: recentOutcomes,
        last_outcome: recentOutcomes[0] || null,
        case_status: actionCode === 'resolved' ? 'Resolved' : 'In Progress'
      });
      setOutcomeMessage(response.data.message || 'Outcome logged.');
      setTimeout(() => setOutcomeMessage(''), 3000);
    } catch (error) {
      console.error('Failed to log rescue outcome', error);
      setOutcomeMessage(error.response?.data?.message || 'Failed to log rescue outcome.');
      setTimeout(() => setOutcomeMessage(''), 3000);
    } finally {
      setLoggingOutcome(false);
    }
  };

  const handleSendEmail = async () => {
    if (!selectedStudent) return;
    setSendingEmail(true);
    try {
      const response = await axios.post(
        `${endpointBase}/send-email`,
        {
          student_id: selectedStudent.id,
          subject: emailDraft.subject || '',
          body: emailDraft.body || ''
        },
        { headers: authHeaders }
      );

      const recentOutcomes = response.data.recent_outcomes || [];
      syncStudentInPayload(selectedStudent.id, {
        recent_outcomes: recentOutcomes,
        last_outcome: recentOutcomes[0] || null,
        case_status: recentOutcomes[0]?.action_code === 'resolved' ? 'Resolved' : 'In Progress'
      });
      setOutcomeMessage(response.data.message || 'Rescue email sent.');
      setTimeout(() => setOutcomeMessage(''), 3000);
    } catch (error) {
      console.error('Failed to send rescue email', error);
      setOutcomeMessage(error.response?.data?.message || 'Failed to send rescue email.');
      setTimeout(() => setOutcomeMessage(''), 3000);
    } finally {
      setSendingEmail(false);
    }
  };

  const students = payload?.students || [];
  const summary = payload?.summary || {};
  const report = payload?.report || {};
  const filteredStudents = students.filter((student) => {
    const statusMatch = statusFilter === 'All' || student.case_status === statusFilter;
    const riskMatch = riskFilter === 'All' || student.risk_level === riskFilter;
    return statusMatch && riskMatch;
  });
  const displayStudents = showPremiumOnly ? filteredStudents.slice(0, 2) : filteredStudents;

  return (
    <>
      <div className="rounded-3xl border border-red-100 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.2em] text-red-500">AI Intervention Engine</p>
            <h3 className="mt-2 text-2xl font-black text-slate-900">Student Rescue Agent</h3>
            <p className="mt-2 max-w-2xl text-sm text-slate-500">
              Prioritized students who need financial, attendance, or academic intervention before the problem spreads.
            </p>
          </div>
          <div className="rounded-2xl bg-red-50 px-4 py-3 text-right">
            <p className="text-xs font-bold uppercase text-red-500">Average Risk</p>
            <p className="text-3xl font-black text-red-700">{summary.average_risk_score || 0}</p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-bold uppercase text-slate-500">Flagged Students</p>
            <p className="mt-2 text-3xl font-black text-slate-900">{summary.total_flagged_students || 0}</p>
          </div>
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
            <p className="text-xs font-bold uppercase text-red-500">Critical</p>
            <p className="mt-2 text-3xl font-black text-red-700">{summary.critical_count || 0}</p>
          </div>
          <div className="rounded-2xl border border-orange-200 bg-orange-50 p-4">
            <p className="text-xs font-bold uppercase text-orange-500">Need Contact</p>
            <p className="mt-2 text-3xl font-black text-orange-700">{summary.contact_queue_count || 0}</p>
          </div>
          <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4">
            <p className="text-xs font-bold uppercase text-blue-500">High Priority</p>
            <p className="mt-2 text-3xl font-black text-blue-700">{summary.high_priority_count || 0}</p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-bold uppercase text-slate-500">Open Cases</p>
            <p className="mt-2 text-3xl font-black text-slate-900">{report.open_cases || 0}</p>
          </div>
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
            <p className="text-xs font-bold uppercase text-amber-600">In Progress</p>
            <p className="mt-2 text-3xl font-black text-amber-700">{report.in_progress_cases || 0}</p>
          </div>
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-xs font-bold uppercase text-emerald-600">Resolved</p>
            <p className="mt-2 text-3xl font-black text-emerald-700">{report.resolved_cases || 0}</p>
          </div>
          <div className="rounded-2xl border border-violet-200 bg-violet-50 p-4">
            <p className="text-xs font-bold uppercase text-violet-600">Actions Last 7 Days</p>
            <p className="mt-2 text-3xl font-black text-violet-700">{report.outcomes_last_7_days || 0}</p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          {['All', 'Open', 'In Progress', 'Resolved'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`rounded-full px-4 py-2 text-xs font-bold ${statusFilter === status ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
            >
              {status}
            </button>
          ))}
          {['All', 'Critical', 'High', 'Moderate'].map((riskLevel) => (
            <button
              key={riskLevel}
              onClick={() => setRiskFilter(riskLevel)}
              className={`rounded-full px-4 py-2 text-xs font-bold ${riskFilter === riskLevel ? 'bg-red-600 text-white' : 'bg-red-50 text-red-700 hover:bg-red-100'}`}
            >
              {riskLevel}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="mt-6 space-y-3">
            <div className="h-20 animate-pulse rounded-2xl bg-slate-100" />
            <div className="h-20 animate-pulse rounded-2xl bg-slate-100" />
          </div>
        ) : displayStudents.length === 0 ? (
          <div className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-6 text-center">
            <p className="text-sm font-bold text-emerald-800">No urgent rescue cases detected</p>
            <p className="mt-1 text-xs text-emerald-700">Current financial and learning signals look stable.</p>
          </div>
        ) : (
          <div className="mt-6 space-y-3">
            {displayStudents.map((student) => (
              <div key={student.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        onClick={() => setSelectedStudent(student)}
                        className="text-left text-lg font-black text-slate-900 hover:underline"
                      >
                        {student.priority_rank}. {student.name}
                      </button>
                      <span className={`rounded-full border px-3 py-1 text-xs font-bold ${getRiskTone(student.risk_level)}`}>
                        {student.risk_level} risk
                      </span>
                      <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-bold text-white">
                        Score {student.risk_score}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-slate-500">
                      {student.student_code || 'No code'} • {student.current_class || 'Class not assigned'}
                    </p>
                    <p className="mt-1 text-xs font-bold uppercase tracking-wide text-slate-400">{student.case_status || 'Open'}</p>
                    <p className="mt-2 text-sm text-slate-700">{student.rescue_summary}</p>
                  </div>
                  <button
                    onClick={() => setSelectedStudent(student)}
                    className="rounded-full border border-red-200 bg-white px-4 py-2 text-xs font-bold text-red-700 hover:bg-red-50"
                  >
                    View Rescue Plan
                  </button>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div className="rounded-xl bg-white p-3">
                    <p className="text-[11px] font-bold uppercase text-slate-400">Risk Drivers</p>
                    <p className="mt-2 text-sm font-semibold text-slate-800">{student.intervention_reasons?.slice(0, 2).map((reason) => reason.label).join(' • ') || 'Manual review'}</p>
                  </div>
                  <div className="rounded-xl bg-white p-3">
                    <p className="text-[11px] font-bold uppercase text-slate-400">Latest Average</p>
                    <p className="mt-2 text-sm font-semibold text-slate-800">
                      {student.latest_report?.term_average == null ? 'No report yet' : `${student.latest_report.term_average.toFixed(1)}%`}
                    </p>
                  </div>
                  <div className="rounded-xl bg-white p-3">
                    <p className="text-[11px] font-bold uppercase text-slate-400">Recommended First Move</p>
                    <p className="mt-2 text-sm font-semibold text-slate-800">{student.recommended_actions?.[0]?.label || 'Review case'}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {showPremiumOnly && students.length > displayStudents.length && (
          <div className="mt-6 rounded-2xl border-2 border-dashed border-red-200 bg-red-50 p-4 text-center">
            <p className="text-sm font-bold text-red-800">
              {filteredStudents.length - displayStudents.length} more rescue cases are available in Premium
            </p>
            <p className="mt-1 text-xs text-red-600">Upgrade to see the full rescue queue and action list.</p>
            <button
              onClick={() => { window.location.href = premiumUpgradePath; }}
              className="mt-3 rounded-full bg-red-600 px-4 py-2 text-xs font-bold text-white hover:bg-red-700"
            >
              Upgrade Now
            </button>
          </div>
        )}
      </div>

      {selectedStudent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setSelectedStudent(null)}>
          <div className="w-full max-w-3xl rounded-3xl bg-white shadow-2xl" onClick={(event) => event.stopPropagation()}>
            <div className="rounded-t-3xl bg-linear-to-r from-red-700 to-orange-500 px-6 py-5 text-white">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-red-100">Student Rescue Plan</p>
                  <h2 className="mt-1 text-2xl font-black">{selectedStudent.name}</h2>
                  <p className="mt-1 text-sm text-red-50">{selectedStudent.student_code || 'No code'} • {selectedStudent.current_class || 'Class not assigned'}</p>
                </div>
                <button
                  onClick={() => setSelectedStudent(null)}
                  className="rounded-full bg-white/15 px-3 py-1 text-sm font-bold hover:bg-white/25"
                >
                  Close
                </button>
              </div>
            </div>

            <div className="space-y-6 p-6">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-bold uppercase text-slate-500">Risk Score</p>
                  <p className="mt-2 text-3xl font-black text-slate-900">{selectedStudent.risk_score}</p>
                  <p className="mt-1 text-sm text-slate-600">{selectedStudent.risk_level} priority</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-bold uppercase text-slate-500">Outstanding Tuition</p>
                  <p className="mt-2 text-3xl font-black text-red-600">GH₵ {Number(selectedStudent.total_tuition_owed || 0).toLocaleString()}</p>
                  <p className="mt-1 text-sm text-slate-600">Deadline: {selectedStudent.tuition_deadline ? new Date(selectedStudent.tuition_deadline).toLocaleDateString() : 'Not set'}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-bold uppercase text-slate-500">Latest Academic Signal</p>
                  <p className="mt-2 text-3xl font-black text-blue-700">
                    {selectedStudent.latest_report?.term_average == null ? 'N/A' : `${selectedStudent.latest_report.term_average.toFixed(1)}%`}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    {selectedStudent.latest_report?.trend_direction === 'declining'
                      ? `Down ${Math.abs(selectedStudent.latest_report?.trend_delta || 0).toFixed(1)} point(s)`
                      : selectedStudent.latest_report?.trend_direction === 'improving'
                        ? `Up ${(selectedStudent.latest_report?.trend_delta || 0).toFixed(1)} point(s)`
                        : 'Trend stable'}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-xs font-bold uppercase text-slate-500">Guardian Contact</p>
                  <p className="mt-2 text-lg font-bold text-slate-900">{selectedStudent.guardian_name || selectedStudent.parent_name || 'Not recorded'}</p>
                  <p className="mt-2 text-sm text-slate-600">Phone: {selectedStudent.parent_phone || 'Not recorded'}</p>
                  <p className="text-sm text-slate-600">Email: {selectedStudent.parent_email || 'Not recorded'}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-xs font-bold uppercase text-slate-500">Attendance / Feeding</p>
                  <p className="mt-2 text-sm text-slate-700">Present today: {selectedStudent.is_present ? 'Yes' : 'No'}</p>
                  <p className="mt-1 text-sm text-slate-700">Feeding cleared: {selectedStudent.feeding_paid ? 'Yes' : 'No'}</p>
                  <p className="mt-1 text-sm text-slate-700">
                    Latest attendance: {selectedStudent.latest_report?.attendance_percentage == null ? 'No report yet' : `${selectedStudent.latest_report.attendance_percentage.toFixed(1)}%`}
                  </p>
                </div>
              </div>

              <div className="rounded-2xl border border-red-100 bg-red-50 p-4">
                <p className="text-xs font-bold uppercase text-red-500">Why The Agent Flagged This Student</p>
                <div className="mt-3 space-y-3">
                  {(selectedStudent.intervention_reasons || []).map((reason) => (
                    <div key={reason.code} className="rounded-xl border border-red-200 bg-white p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-bold text-slate-900">{reason.label}</p>
                        <span className="rounded-full bg-red-100 px-2 py-1 text-[11px] font-bold text-red-700">Severity {reason.severity}</span>
                      </div>
                      <p className="mt-1 text-sm text-slate-600">{reason.detail}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4">
                <p className="text-xs font-bold uppercase text-blue-500">Recommended Actions</p>
                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                  {(selectedStudent.recommended_actions || []).map((action) => (
                    <div key={action.code} className="rounded-xl border border-blue-200 bg-white p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-bold text-slate-900">{action.label}</p>
                        <span className="rounded-full bg-blue-100 px-2 py-1 text-[11px] font-bold text-blue-700">{getUrgencyLabel(action.urgency)}</span>
                      </div>
                      <p className="mt-1 text-xs uppercase tracking-wide text-slate-400">Channel: {action.channel}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-bold uppercase text-emerald-600">Outcome Logging</p>
                  {loggingOutcome && <span className="text-xs font-semibold text-emerald-700">Saving...</span>}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button onClick={() => handleLogOutcome('guardian_called')} className="rounded-full bg-white px-3 py-2 text-xs font-bold text-emerald-800 hover:bg-emerald-100">Guardian Called</button>
                  <button onClick={() => handleLogOutcome('email_sent')} className="rounded-full bg-white px-3 py-2 text-xs font-bold text-emerald-800 hover:bg-emerald-100">Email Sent</button>
                  <button onClick={() => handleLogOutcome('payment_plan_agreed')} className="rounded-full bg-white px-3 py-2 text-xs font-bold text-emerald-800 hover:bg-emerald-100">Payment Plan Agreed</button>
                  <button onClick={() => handleLogOutcome('academic_support_assigned')} className="rounded-full bg-white px-3 py-2 text-xs font-bold text-emerald-800 hover:bg-emerald-100">Academic Support Assigned</button>
                  <button onClick={() => handleLogOutcome('resolved')} className="rounded-full bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700">Mark Resolved</button>
                </div>
                {outcomeMessage && (
                  <p className="mt-3 text-sm font-semibold text-emerald-700">{outcomeMessage}</p>
                )}
              </div>

              <div className="rounded-2xl border border-violet-100 bg-violet-50 p-4">
                <p className="text-xs font-bold uppercase text-violet-600">Guardian Contact Templates</p>
                <p className="mt-2 text-xs text-violet-700">WhatsApp sending is intentionally deferred for now due to cost. Use the draft copy tools until that integration is enabled later.</p>
                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div className="rounded-xl border border-violet-200 bg-white p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-bold text-slate-900">Call Script</p>
                      <button onClick={() => handleCopy(selectedStudent.contact_templates?.call_script, 'Call script')} className="text-xs font-bold text-violet-700 hover:underline">Copy</button>
                    </div>
                    <p className="mt-2 text-sm text-slate-600">{selectedStudent.contact_templates?.call_script || 'No script available.'}</p>
                  </div>
                  <div className="rounded-xl border border-violet-200 bg-white p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-bold text-slate-900">SMS / WhatsApp Draft</p>
                      <button onClick={() => handleCopy(selectedStudent.contact_templates?.sms_body, 'SMS draft')} className="text-xs font-bold text-violet-700 hover:underline">Copy</button>
                    </div>
                    <p className="mt-2 text-sm text-slate-600">{selectedStudent.contact_templates?.sms_body || 'No draft available.'}</p>
                  </div>
                  <div className="rounded-xl border border-violet-200 bg-white p-3 md:col-span-2">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-bold text-slate-900">Email Template</p>
                      <button
                        onClick={() => handleCopy(`${emailDraft.subject || ''}\n\n${emailDraft.body || ''}`.trim(), 'Email template')}
                        className="text-xs font-bold text-violet-700 hover:underline"
                      >
                        Copy
                      </button>
                    </div>
                    <p className="mt-2 text-xs font-bold uppercase tracking-wide text-slate-400">Subject</p>
                    <input
                      type="text"
                      value={emailDraft.subject}
                      onChange={(event) => setEmailDraft((currentDraft) => ({ ...currentDraft, subject: event.target.value }))}
                      className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-800"
                      placeholder="Email subject"
                    />
                    <p className="mt-3 text-xs font-bold uppercase tracking-wide text-slate-400">Body</p>
                    <textarea
                      value={emailDraft.body}
                      onChange={(event) => setEmailDraft((currentDraft) => ({ ...currentDraft, body: event.target.value }))}
                      rows={8}
                      className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600"
                      placeholder="Email body"
                    />
                  </div>
                  <div className="rounded-xl border border-violet-200 bg-white p-3 md:col-span-2">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-bold text-slate-900">Meeting Brief</p>
                      <button onClick={() => handleCopy(selectedStudent.contact_templates?.meeting_brief, 'Meeting brief')} className="text-xs font-bold text-violet-700 hover:underline">Copy</button>
                    </div>
                    <p className="mt-2 text-sm text-slate-600">{selectedStudent.contact_templates?.meeting_brief || 'No meeting brief available.'}</p>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-bold uppercase text-slate-500">Recent Rescue Outcomes</p>
                <div className="mt-3 space-y-3">
                  {(selectedStudent.recent_outcomes || []).length === 0 ? (
                    <p className="text-sm text-slate-500">No action has been logged on this rescue case yet.</p>
                  ) : (
                    (selectedStudent.recent_outcomes || []).map((outcome) => (
                      <div key={outcome.log_id} className="rounded-xl border border-slate-200 bg-white p-3">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <p className="text-sm font-bold text-slate-900">{outcome.action_label}</p>
                          <p className="text-xs font-semibold text-slate-400">{outcome.created_at ? new Date(outcome.created_at).toLocaleString() : ''}</p>
                        </div>
                        <p className="mt-1 text-xs uppercase tracking-wide text-slate-400">Logged by {outcome.actor_name || 'Unknown'}</p>
                        {outcome.notes && <p className="mt-2 text-sm text-slate-600">{outcome.notes}</p>}
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                {selectedStudent.parent_email && (
                  <button
                    onClick={handleSendEmail}
                    disabled={sendingEmail}
                    className="rounded-xl bg-slate-900 px-4 py-3 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {sendingEmail ? 'Sending Email...' : 'Send Rescue Email'}
                  </button>
                )}
                {selectedStudent.parent_phone && (
                  <a
                    href={`tel:${selectedStudent.parent_phone.replace(/\s+/g, '')}`}
                    className="rounded-xl bg-red-600 px-4 py-3 text-sm font-bold text-white hover:bg-red-700"
                  >
                    Call Guardian
                  </a>
                )}
                {selectedStudent.parent_email && (
                  <a
                    href={`mailto:${selectedStudent.parent_email}`}
                    className="rounded-xl border border-slate-300 px-4 py-3 text-sm font-bold text-slate-700 hover:bg-slate-50"
                  >
                    Email Guardian
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}