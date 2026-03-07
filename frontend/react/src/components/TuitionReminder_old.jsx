import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';

export default function TuitionReminder() {
  const [students, setStudents] = useState([]);
  const [filteredStudents, setFilteredStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [reminderStatus, setReminderStatus] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterBy, setFilterBy] = useState('all'); // all, overdue, pending
  const [schoolInfo, setSchoolInfo] = useState({});
  const [paymentHistories, setPaymentHistories] = useState({}); // Store payment histories by student ID
  const [loadingPayments, setLoadingPayments] = useState({});

  useEffect(() => {
    fetchSchoolInfo();
    fetchStudentsWithOutstandingTuition();
  }, []);

  const fetchSchoolInfo = async () => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get('/api/school/branding', { headers });
      setSchoolInfo(res.data);
    } catch (err) {
      console.error('Failed to fetch school info');
    }
  };

  const fetchStudentsWithOutstandingTuition = async () => {
    setLoading(true);
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get('/api/finance/students-outstanding-tuition', { headers });
      setStudents(res.data);
      setFilteredStudents(res.data);
    } catch (err) {
      setReminderStatus('Failed to fetch student tuition data');
    } finally {
      setLoading(false);
    }
  };

  const fetchPaymentHistory = async (studentId) => {
    if (paymentHistories[studentId]) return; // Already loaded
    
    setLoadingPayments(prev => ({ ...prev, [studentId]: true }));
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get(`/api/students/${studentId}/payments`, { headers });
      const payments = res.data?.payments || [];
      // Filter only tuition payments
      const tuitionPayments = payments.filter(p => p.payment_type === 'Tuition');
      setPaymentHistories(prev => ({ ...prev, [studentId]: tuitionPayments }));
    } catch (err) {
      console.error('Failed to fetch payment history');
      setPaymentHistories(prev => ({ ...prev, [studentId]: [] }));
    } finally {
      setLoadingPayments(prev => ({ ...prev, [studentId]: false }));
    }
  };

  const togglePaymentHistory = (studentId) => {
    if (selectedStudent === studentId) {
      setSelectedStudent(null);
    } else {
      setSelectedStudent(studentId);
      fetchPaymentHistory(studentId);
    }
  };

  useEffect(() => {
    let filtered = students;

    // Filter by search term
    if (searchTerm.trim()) {
      filtered = filtered.filter(s =>
        s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        s.student_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (s.parent_name && s.parent_name.toLowerCase().includes(searchTerm.toLowerCase()))
      );
    }

    // Filter by payment status
    if (filterBy === 'overdue') {
      filtered = filtered.filter(s => s.is_overdue);
    } else if (filterBy === 'pending') {
      filtered = filtered.filter(s => !s.is_overdue);
    }

    setFilteredStudents(filtered);
  }, [searchTerm, filterBy, students]);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="mb-4 text-4xl">⏳</div>
          <p className="text-slate-600">Loading student data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-800 mb-2">📧 Tuition Reminders</h1>
          <p className="text-slate-600">
            Send and print payment reminders for students with outstanding tuition balances.
          </p>
        </div>

        {/* Stats */}
            background: #f5f5f5;
          }
          .container {
            max-width: 800px;
            margin: 40px auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
          }
          .header {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #1e3a8a;
          }
          .logo {
            height: 60px;
            width: 60px;
            background: #f0f0f0;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
          }
          .header-text h1 {
            margin: 0;
            color: #1e3a8a;
            font-size: 24px;
          }
          .header-text p {
            margin: 5px 0 0 0;
            color: #666;
            font-size: 14px;
          }
          .reminder-type {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            margin-bottom: 30px;
            font-size: 12px;
            letter-spacing: 1px;
          }
          .reminder-type.overdue {
            background: #fee2e2;
            color: #991b1b;
          }
          .reminder-type.pending {
            background: #fef3c7;
            color: #92400e;
          }
          .date {
            text-align: right;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
          }
          .dear {
            margin-bottom: 20px;
          }
          .dear p {
            margin: 0 0 15px 0;
          }
          .student-info {
            background: #f9fafb;
            padding: 20px;
            border-radius: 6px;
            margin: 25px 0;
            border-left: 4px solid #1e3a8a;
          }
          .info-row {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            font-size: 14px;
          }
          .info-label {
            font-weight: bold;
            color: #333;
          }
          .info-value {
            color: #666;
          }
          .amount-due {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            background: #eff6ff;
            padding: 15px 20px;
            border-radius: 6px;
            margin: 25px 0;
            border: 2px solid #0284c7;
          }
          .amount-label {
            font-weight: bold;
            color: #0c4a6e;
            font-size: 14px;
          }
          .amount-value {
            font-size: 28px;
            font-weight: bold;
            color: #0284c7;
            font-family: 'Courier New', monospace;
          }
          .deadline-section {
            background: #fef3c7;
            padding: 15px 20px;
            border-radius: 6px;
            margin: 25px 0;
            border-left: 4px solid #f59e0b;
          }
          .overdue-section {
            background: #fee2e2;
            padding: 15px 20px;
            border-radius: 6px;
            margin: 25px 0;
            border-left: 4px solid #dc2626;
          }
          .deadline-label {
            font-weight: bold;
            color: #b45309;
            margin-bottom: 5px;
            font-size: 14px;
          }
          .overdue-label {
            font-weight: bold;
            color: #7f1d1d;
            margin-bottom: 5px;
            font-size: 14px;
          }
          .deadline-value {
            color: #92400e;
            font-size: 16px;
            font-weight: bold;
          }
          .overdue-value {
            color: #991b1b;
            font-size: 16px;
            font-weight: bold;
          }
          .next-steps {
            background: #f0fdf4;
            padding: 20px;
            border-radius: 6px;
            margin: 25px 0;
            border-left: 4px solid #16a34a;
          }
          .next-steps h3 {
            margin: 0 0 15px 0;
            color: #15803d;
            font-size: 14px;
          }
          .next-steps ol {
            margin: 0;
            padding-left: 20px;
            color: #166534;
          }
          .next-steps li {
            margin: 8px 0;
            font-size: 14px;
          }
          .contact-section {
            background: #f3f4f6;
            padding: 20px;
            border-radius: 6px;
            margin: 25px 0;
          }
          .contact-section h3 {
            margin: 0 0 10px 0;
            color: #374151;
            font-size: 14px;
          }
          .contact-section p {
            margin: 5px 0;
            color: #666;
            font-size: 14px;
          }
          .closing {
            margin: 30px 0 20px 0;
            color: #666;
          }
          .signature {
            margin-top: 40px;
          }
          .signature-line {
            border-bottom: 2px solid #000;
            width: 200px;
            margin: 20px 0 5px 0;
          }
          .signature-name {
            font-weight: bold;
            font-size: 14px;
            width: 200px;
          }
          .signature-title {
            font-size: 12px;
            color: #666;
            width: 200px;
          }
          .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
            color: #999;
            font-size: 12px;
          }
          @media print {
            body {
              background: white;
            }
            .container {
              box-shadow: none;
              border: none;
              margin: 0;
              padding: 40px;
            }
          }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <div class="logo">📧</div>
            <div class="header-text">
              <h1>${schoolInfo.name || 'School Name'}</h1>
              <p>Tuition Payment Reminder</p>
            </div>
          </div>

          <div class="reminder-type ${student.is_overdue ? 'overdue' : 'pending'}">
            ${student.is_overdue ? '⚠️ OVERDUE PAYMENT' : '📌 PAYMENT DUE'}
          </div>

          <div class="date">${today}</div>

          <div class="dear">
            <p>Dear ${student.parent_name || 'Parent/Guardian'},</p>
            <p>
              This letter is a reminder that <strong>${student.name}</strong> 
              (Student Code: ${student.student_code}, Class: ${student.current_class || 'N/A'}) 
              has an outstanding tuition balance.
            </p>
          </div>

          <div class="student-info">
            <div class="info-row">
              <span class="info-label">Student Name:</span>
              <span class="info-value">${student.name}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Student Code:</span>
              <span class="info-value">${student.student_code}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Current Class:</span>
              <span class="info-value">${student.current_class || 'N/A'}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Parent/Guardian:</span>
              <span class="info-value">${student.parent_name || 'N/A'}</span>
            </div>
          </div>

          <div class="amount-due">
            <span class="amount-label">Total Tuition Owed:</span>
            <span class="amount-value">GHS ${student.total_tuition_owed.toFixed(2)}</span>
          </div>

          ${student.is_overdue ? `
            <div class="overdue-section">
              <div class="overdue-label">⚠️ PAYMENT IS OVERDUE</div>
              <div class="overdue-value">
                Payment was due on ${new Date(student.tuition_deadline).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
              </div>
              <div style="margin-top: 10px; color: #991b1b; font-size: 14px;">
                This payment is <strong>${daysOverdue} days overdue</strong>. Immediate action is required.
              </div>
            </div>
          ` : `
            <div class="deadline-section">
              <div class="deadline-label">📅 Payment Due Date:</div>
              <div class="deadline-value">
                ${new Date(student.tuition_deadline).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
              </div>
            </div>
          `}

          <div class="next-steps">
            <h3>Required Action:</h3>
            <ol>
              <li>Review the outstanding balance amount above</li>
              <li>Make payment using any of the accepted payment methods</li>
              <li>
                ${student.is_overdue ? 'Contact the school office immediately to discuss payment arrangements if needed' : 'Ensure payment is made before the deadline to avoid late charges'}
              </li>
              <li>Keep your payment receipt/confirmation for your records</li>
            </ol>
          </div>

          <div class="contact-section">
            <h3>📍 Contact Information</h3>
            <p><strong>${schoolInfo.name || 'School Name'}</strong></p>
            ${schoolInfo.address ? `<p>📮 ${schoolInfo.address}</p>` : ''}
            ${schoolInfo.phone ? `<p>📱 ${schoolInfo.phone}</p>` : ''}
            ${schoolInfo.email ? `<p>📧 ${schoolInfo.email}</p>` : ''}
            ${schoolInfo.website ? `<p>🌐 ${schoolInfo.website}</p>` : ''}
            <p style="margin-top: 10px; color: #999; font-size: 13px;">
              For payment inquiries or to request a payment schedule, please contact the Finance/Bursar's office
            </p>
          </div>

          <div class="closing">
            <p>We appreciate your prompt attention to this matter. Your cooperation ensures that ${student.name} continues their education without interruption.</p>
            <p>Thank you for your cooperation.</p>
          </div>

          <div class="signature">
            <div class="signature-line"></div>
            <div class="signature-name">${schoolInfo.name || 'School Representative'}</div>
            <div class="signature-title">Finance/Bursar Office</div>
          </div>

          <div class="footer">
            <p>This is an automated reminder generated on ${today}. For further clarification, please contact your school's Finance/Bursar office.</p>
          </div>
        </div>
      </body>
      </html>
    `;
  };

  const handlePrintReminder = (student) => {
    const html = buildReminderHtml(student);
    const win = window.open('', '_blank', 'width=900,height=1200');
    if (!win) return;
    win.document.open();
    win.document.write(html);
    win.document.close();
    win.focus();
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="mb-4 text-4xl">⏳</div>
          <p className="text-slate-600">Loading student data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-800 mb-2">📧 Tuition Reminders</h1>
          <p className="text-slate-600">
            Send and print payment reminders for students with outstanding tuition balances.
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
            <div className="text-2xl mb-2">👥</div>
            <p className="text-slate-600 text-sm">Total Outstanding</p>
            <p className="text-2xl font-bold text-slate-800">{students.length}</p>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
            <div className="text-2xl mb-2">⚠️</div>
            <p className="text-slate-600 text-sm">Overdue Payments</p>
            <p className="text-2xl font-bold text-red-600">{students.filter(s => s.is_overdue).length}</p>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
            <div className="text-2xl mb-2">💰</div>
            <p className="text-slate-600 text-sm">Total Amount Owed</p>
            <p className="text-2xl font-bold text-blue-600">
              GHS {students.reduce((sum, s) => sum + (s.total_tuition_owed || 0), 0).toFixed(2)}
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Search Student</label>
              <input
                type="text"
                placeholder="Name, code, or parent name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full p-2 border rounded-lg bg-slate-50 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Filter</label>
              <select
                value={filterBy}
                onChange={(e) => setFilterBy(e.target.value)}
                className="w-full p-2 border rounded-lg bg-slate-50 text-sm"
              >
                <option value="all">All Students</option>
                <option value="overdue">Overdue Only</option>
                <option value="pending">Pending (Due Soon)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Results</label>
              <div className="p-2 bg-slate-50 rounded-lg text-sm text-slate-600 font-semibold">
                {filteredStudents.length} of {students.length} students
              </div>
            </div>
          </div>
        </div>

        {/* Status Messages */}
        {reminderStatus && (
          <div className={`mb-8 p-4 rounded-lg ${
            reminderStatus.includes('Failed') 
              ? 'bg-red-50 text-red-700 border border-red-200' 
              : 'bg-green-50 text-green-700 border border-green-200'
          }`}>
            {reminderStatus}
          </div>
        )}

        {/* Students List */}
        {filteredStudents.length === 0 ? (
          <div className="bg-white p-12 rounded-xl shadow-sm border border-slate-100 text-center">
            <div className="text-4xl mb-4">✅</div>
            <p className="text-slate-600 mb-2">No students found with outstanding tuition.</p>
            <p className="text-slate-500 text-sm">All accounts are up to date! 🎉</p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredStudents.map((student) => (
              <div
                key={student.id}
                className={`bg-white p-6 rounded-xl shadow-sm border-l-4 ${
                  student.is_overdue ? 'border-red-400' : 'border-yellow-400'
                } hover:shadow-md transition-shadow`}
              >
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center">
                        👤
                      </div>
                      <div>
                        <h3 className="font-bold text-slate-800">{student.name}</h3>
                        <p className="text-xs text-slate-500">
                          {student.student_code} • Class: {student.current_class || 'N/A'}
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <p className="text-slate-600 text-xs uppercase font-bold">Parent</p>
                        <p className="text-slate-800 font-semibold">{student.parent_name || 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-slate-600 text-xs uppercase font-bold">Amount Owed</p>
                        <p className="text-blue-600 font-bold">GHS {student.total_tuition_owed.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-slate-600 text-xs uppercase font-bold">Status</p>
                        <p className={`font-semibold ${student.is_overdue ? 'text-red-600' : 'text-yellow-600'}`}>
                          {student.is_overdue ? '⚠️ Overdue' : '📌 Pending'}
                        </p>
                      </div>
                      {student.tuition_deadline && (
                        <div>
                          <p className="text-slate-600 text-xs uppercase font-bold">Due Date</p>
                          <p className="text-slate-800 font-semibold">
                            {new Date(student.tuition_deadline).toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric'
                            })}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => togglePaymentHistory(student.id)}
                      className="px-4 py-2 bg-slate-600 text-white rounded-lg font-bold hover:bg-slate-700 transition-colors whitespace-nowrap flex items-center gap-2 text-sm"
                    >
                      {selectedStudent === student.id ? '📊 Hide History' : '📊 View History'}
                    </button>
                    <Link
                      to={`/proprietor?tab=payment-tracker`}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 transition-colors whitespace-nowrap flex items-center gap-2 text-sm"
                    >
                      💳 Payment Tracker
                    </Link>
                  </div>
                </div>

                {/* Transaction History */}
                {selectedStudent === student.id && (
                  <div className="mt-4 border-t pt-4">
                    {loadingPayments[student.id] ? (
                      <div className="text-center py-4 text-slate-500">
                        <div className="mb-2">⏳</div>
                        Loading payment history...
                      </div>
                    ) : paymentHistories[student.id]?.length > 0 ? (
                      <div>
                        <h4 className="font-bold text-slate-700 mb-3 flex items-center gap-2">
                          💳 Tuition Payment History
                        </h4>
                        <div className="space-y-2">
                          {paymentHistories[student.id].map((payment) => (
                            <div
                              key={payment.id}
                              className="flex justify-between items-center p-3 bg-slate-50 rounded-lg border border-slate-200"
                            >
                              <div className="flex-1">
                                <p className="text-sm font-semibold text-slate-800">
                                  {payment.method} Payment
                                </p>
                                <p className="text-xs text-slate-500">
                                  {new Date(payment.date_paid).toLocaleDateString('en-US', {
                                    year: 'numeric',
                                    month: 'long',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit'
                                  })}
                                </p>
                                {payment.reference_id && (
                                  <p className="text-xs text-slate-400 mt-1">
                                    Ref: {payment.reference_id}
                                  </p>
                                )}
                              </div>
                              <div className="text-right">
                                <p className="text-lg font-bold text-green-600">
                                  GHS {payment.amount.toFixed(2)}
                                </p>
                                <p className={`text-xs font-semibold ${
                                  payment.status === 'Confirmed' || payment.status === 'Verified'
                                    ? 'text-green-600'
                                    : 'text-yellow-600'
                                }`}>
                                  {payment.status}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                          <div className="flex justify-between items-center">
                            <span className="text-sm font-bold text-blue-900">Total Paid (Tuition):</span>
                            <span className="text-lg font-bold text-blue-600">
                              GHS {paymentHistories[student.id]
                                .filter(p => p.status === 'Confirmed' || p.status === 'Verified')
                                .reduce((sum, p) => sum + p.amount, 0)
                                .toFixed(2)}
                            </span>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-6 text-slate-500 bg-slate-50 rounded-lg">
                        <div className="mb-2">📭</div>
                        <p className="text-sm">No tuition payments recorded yet</p>
                        <p className="text-xs mt-1 text-slate-400">
                          Visit Payment Tracker to record payments
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
