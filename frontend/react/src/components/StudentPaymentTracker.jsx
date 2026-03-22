import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useBranding } from '../hooks/useBranding';

export default function StudentPaymentTracker() {
  const [students, setStudents] = useState([]);
  const [schoolFees, setSchoolFees] = useState(null);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [studentPayments, setStudentPayments] = useState([]);
  const [paymentCodes, setPaymentCodes] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all'); // all, paid, pending, overdue
  const [sendingBulkWhatsapp, setSendingBulkWhatsapp] = useState(false);
  const [isPremium, setIsPremium] = useState(false);
  const [whatsappTargetMode, setWhatsappTargetMode] = useState('class');
  const [whatsappClassName, setWhatsappClassName] = useState('');
  const [whatsappStudentIds, setWhatsappStudentIds] = useState([]);
  const [whatsappResult, setWhatsappResult] = useState(null);
  const { branding } = useBranding();

  useEffect(() => {
    fetchStudents();
    fetchSchoolFees();
    // Get subscription plan from localStorage
    const subscriptionPlan = localStorage.getItem('subscription_plan');
    setIsPremium(subscriptionPlan === 'Premium');
  }, []);

  const fetchStudents = async () => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get('/api/students', { headers });
      const studentList = Array.isArray(res.data) ? res.data : res.data?.students || [];
      setStudents(studentList);
      const classOptions = Array.from(new Set(studentList.map(s => s.current_class).filter(Boolean))).sort();
      if (!whatsappClassName && classOptions.length > 0) {
        setWhatsappClassName(classOptions[0]);
      }
    } catch (err) {
      console.error('Failed to load students');
    }
  };

  const fetchSchoolFees = async () => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get('/api/school/fees', { headers });
      setSchoolFees(res.data);
    } catch (err) {
      console.error('Failed to load school fees');
    }
  };

  const fetchStudentPayments = async (studentId) => {
    try {
      setLoading(true);
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get(`/api/students/${studentId}/payments`, { headers });
      setStudentPayments(Array.isArray(res.data) ? res.data : res.data?.payments || []);
    } catch (err) {
      console.error('Failed to load student payments');
      setStudentPayments([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectStudent = (student) => {
    setSelectedStudent(student);
    fetchStudentPayments(student.id);
    fetchPaymentCodes(student.id);
  };

  const fetchPaymentCodes = async (studentId) => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get(`/api/students/${studentId}/payment-codes`, { headers });
      setPaymentCodes(res.data);
    } catch (err) {
      console.error('Failed to load payment codes');
      setPaymentCodes(null);
    }
  };

  const handleBulkWhatsappPaymentReminders = async () => {
    if (!isPremium) {
      alert('Bulk WhatsApp payment reminders are available for Premium plan only.');
      return;
    }

    setSendingBulkWhatsapp(true);
    setWhatsappResult(null);
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id'),
        'Content-Type': 'application/json'
      };

      let payload = { target_mode: whatsappTargetMode };

      if (whatsappTargetMode === 'class') {
        if (!whatsappClassName) {
          alert('Please select a class for class-targeted sending.');
          setSendingBulkWhatsapp(false);
          return;
        }
        payload.class_name = whatsappClassName;
      } else if (whatsappTargetMode === 'single') {
        if (!selectedStudent?.id) {
          alert('Select a student first for single-target sending.');
          setSendingBulkWhatsapp(false);
          return;
        }
        payload.student_ids = [selectedStudent.id];
      } else {
        if (whatsappStudentIds.length === 0) {
          alert('Select one or more students.');
          setSendingBulkWhatsapp(false);
          return;
        }
        payload.student_ids = whatsappStudentIds;
      }

      const response = await axios.post('/api/proprietor/payment-tracker/whatsapp/bulk-send', payload, { headers });
      setWhatsappResult(response.data);

      if (response.data.sent_count > 0) {
        alert(`✅ Sent: ${response.data.sent_count} | Skipped: ${response.data.skipped_count}`);
      } else {
        alert(`No successful sends. Check the result summary for reasons.`);
      }
    } catch (err) {
      const errorMsg = err.response?.data?.message || err.message || 'Failed to send bulk WhatsApp reminders';
      alert(`❌ Error: ${errorMsg}`);
      console.error('Bulk WhatsApp error:', err);
    } finally {
      setSendingBulkWhatsapp(false);
    }
  };

  const printPaymentInstructions = () => {
    if (!paymentCodes) return;

    const schoolName = branding.school_name || branding.name || 'School';
    const schoolEmail = branding.school_email || branding.email || '';
    const schoolPhone = branding.school_phone || branding.phone || '';
    const schoolAddress = branding.school_address || branding.address || '';
    const themeColor = branding.theme_color || '#3b82f6';

    const totalVirtualRouteAmount = paymentCodes.payment_codes.reduce((sum, code) => sum + Number(code.total_amount || code.amount || 0), 0);
    const totalCashAmount = paymentCodes.payment_codes.reduce((sum, code) => sum + Number(code.base_amount || code.cash_amount || 0), 0);
    const totalConvenienceFees = paymentCodes.payment_codes.reduce((sum, code) => sum + Number(code.convenience_fee_amount || 0), 0);

    const printWindow = window.open('', '', 'width=900,height=1200');
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Payment Instructions - ${paymentCodes.student_name}</title>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
          }
          .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
          }
          .header {
            text-align: center;
            border-bottom: 3px solid ${themeColor};
            padding-bottom: 20px;
            margin-bottom: 30px;
          }
          .school-name {
            font-size: 24px;
            font-weight: bold;
            color: ${themeColor};
            margin-bottom: 10px;
          }
          .school-contact {
            font-size: 12px;
            color: #666;
            line-height: 1.8;
          }
          .document-title {
            text-align: center;
            font-size: 20px;
            font-weight: bold;
            color: #333;
            margin-bottom: 30px;
            text-transform: uppercase;
            letter-spacing: 1px;
          }
          .student-info {
            background: #f8f9fa;
            padding: 15px;
            border-left: 4px solid ${themeColor};
            margin-bottom: 30px;
            border-radius: 4px;
          }
          .student-info p {
            margin: 8px 0;
            font-size: 14px;
          }
          .info-label {
            font-weight: bold;
            color: ${themeColor};
            display: inline-block;
            width: 120px;
          }
          .section {
            margin-bottom: 30px;
          }
          .section-title {
            font-size: 16px;
            font-weight: bold;
            color: white;
            background: ${themeColor};
            padding: 12px 15px;
            margin-bottom: 15px;
            border-radius: 4px;
          }
          .payment-codes-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
          }
          .payment-codes-table th {
            background: #f0f0f0;
            color: #333;
            padding: 12px;
            text-align: left;
            font-weight: bold;
            border-bottom: 2px solid ${themeColor};
            font-size: 13px;
          }
          .payment-codes-table td {
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
            font-size: 13px;
          }
          .payment-codes-table tr:nth-child(even) {
            background: #fafafa;
          }
          .payment-summary-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
          }
          .payment-summary-table th {
            background: #f0f0f0;
            color: #333;
            padding: 12px;
            text-align: left;
            font-weight: bold;
            border-bottom: 2px solid ${themeColor};
            font-size: 13px;
          }
          .payment-summary-table td {
            padding: 10px 12px;
            border-bottom: 1px solid #e0e0e0;
            font-size: 13px;
          }
          .payment-summary-table tfoot td {
            font-weight: bold;
            border-top: 2px solid ${themeColor};
          }
          .code-column {
            font-family: 'Courier New', monospace;
            font-size: 14px;
            font-weight: bold;
            color: ${themeColor};
            background: #f0f7ff;
            padding: 8px 12px;
            border-radius: 4px;
            letter-spacing: 1px;
          }
          .amount-column {
            text-align: right;
            font-weight: bold;
            color: #333;
          }
          .instructions {
            background: #fffbea;
            border-left: 4px solid #f59e0b;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
          }
          .instructions-title {
            font-weight: bold;
            color: #d97706;
            margin-bottom: 10px;
            font-size: 14px;
          }
          .instruction-text {
            font-size: 13px;
            color: #666;
            line-height: 1.8;
            margin: 8px 0;
          }
          .instruction-text code {
            background: #fff3cd;
            padding: 4px 8px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-weight: bold;
            color: #d97706;
          }
          .payment-method {
            background: #f8f9fa;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 4px;
            border-left: 4px solid ${themeColor};
          }
          .payment-method-title {
            font-weight: bold;
            color: ${themeColor};
            margin-bottom: 10px;
            font-size: 14px;
          }
          .payment-method-content {
            font-size: 13px;
            color: #666;
            line-height: 1.8;
          }
          .footer {
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            margin-top: 30px;
            font-size: 12px;
            color: #999;
          }
          .important {
            background: #fee;
            border-left: 4px solid #dc2626;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
            font-size: 13px;
            color: #dc2626;
          }
          .important strong {
            display: block;
            margin-bottom: 5px;
          }
          @media print {
            body { background: white; }
            .container { box-shadow: none; }
          }
        </style>
      </head>
      <body>
        <div class="container">
          <!-- Header -->
          <div class="header">
            <div class="school-name">${schoolName}</div>
            <div class="school-contact">
              ${schoolAddress ? `<div>${schoolAddress}</div>` : ''}
              ${schoolPhone ? `<div>📞 ${schoolPhone}</div>` : ''}
              ${schoolEmail ? `<div>✉️ ${schoolEmail}</div>` : ''}
            </div>
          </div>

          <!-- Document Title -->
          <div class="document-title">📋 Payment Instructions & Fee Summary</div>

          <!-- Student Information -->
          <div class="student-info">
            <p><span class="info-label">Student Name:</span> ${paymentCodes.student_name}</p>
            <p><span class="info-label">Student ID:</span> <strong>${paymentCodes.student_code}</strong></p>
            <p><span class="info-label">Class:</span> ${paymentCodes.class || 'Not assigned'}</p>
            ${paymentCodes.parent_phone ? `<p><span class="info-label">Parent/Guardian:</span> ${paymentCodes.parent_name || ''} (${paymentCodes.parent_phone})</p>` : ''}
          </div>

          <!-- Payment Routes Section -->
          <div class="section">
            <div class="section-title">💳 Payment Routes by Fee Type</div>
            <table class="payment-codes-table">
              <thead>
                <tr>
                  <th>Fee Type</th>
                  <th>Virtual Route</th>
                  <th>Reference (Backup)</th>
                  <th class="amount-column">School Fee</th>
                  <th class="amount-column">Convenience Fee</th>
                  <th class="amount-column">Total via Route</th>
                </tr>
              </thead>
              <tbody>
                ${paymentCodes.payment_codes.map(code => `
                  <tr>
                    <td><strong>${code.fee_type}</strong></td>
                    <td>
                      ${code.virtual_bank_account ? `<div><strong>Acct:</strong> <span class="code-column">${code.virtual_bank_account}</span></div>` : ''}
                      ${!code.virtual_bank_account ? '<span style="color:#b91c1c;">Not configured</span>' : ''}
                    </td>
                    <td><span class="code-column">${code.reference_code || code.code}</span></td>
                    <td class="amount-column">GH₵ ${Number(code.base_amount || 0).toFixed(2)}</td>
                    <td class="amount-column">GH₵ ${Number(code.convenience_fee_amount || 0).toFixed(2)}</td>
                    <td class="amount-column">GH₵ ${Number(code.total_amount || code.amount || 0).toFixed(2)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>

          <!-- Important Notice -->
          <div class="important">
            <strong>⚠️ Important:</strong> Each virtual-route total already includes the convenience fee. If a parent wants to avoid the convenience fee, they can pay the school fee amount by cash at the school office instead. During USSD wallet-to-bank transfer, select the bank shown with that virtual account. Reference code is backup only.
          </div>

          <!-- Payment Methods Section -->
          <div class="section">
            <div class="section-title">💰 How to Pay (Per Fee Type)</div>
            ${paymentCodes.payment_codes.map(code => `
              <div class="payment-method">
                <div class="payment-method-title">${code.fee_type}</div>
                <div class="payment-method-content">
                  ${code.virtual_bank_account ? `<p><strong>Bank Transfer (Virtual):</strong> ${code.virtual_bank_account}${code.virtual_bank_name ? ` (${code.virtual_bank_name})` : ''}</p>` : ''}
                  ${!code.virtual_bank_account ? '<p style="color:#b91c1c;"><strong>Virtual account not configured for this fee type.</strong></p>' : ''}
                  <p><strong>School Fee:</strong> GH₵ ${Number(code.base_amount || 0).toFixed(2)}</p>
                  <p><strong>Convenience Fee:</strong> GH₵ ${Number(code.convenience_fee_amount || 0).toFixed(2)} (${Number(code.convenience_fee_percent || 0).toFixed(2)}%)</p>
                  <p><strong>Total by Virtual Route:</strong> GH₵ ${Number(code.total_amount || code.amount || 0).toFixed(2)}</p>
                  <p><strong>Cash at School Office:</strong> GH₵ ${Number(code.base_amount || 0).toFixed(2)}</p>
                  <p><strong>Backup Reference:</strong> ${code.reference_code || code.code}</p>
                  ${code.virtual_bank_account ? `
                    <p style="margin-top: 8px;"><strong>USSD Wallet-to-Bank:</strong></p>
                    <p style="margin-left: 12px;">1) Dial your mobile money USSD code (e.g., MTN *170#)</p>
                    <p style="margin-left: 12px;">2) Choose transfer/wallet-to-bank</p>
                    <p style="margin-left: 12px;">3) Select bank: <strong>${code.virtual_bank_name || 'Bank shown with this virtual account'}</strong></p>
                    <p style="margin-left: 12px;">4) Enter account number: <strong>${code.virtual_bank_account}</strong></p>
                    <p style="margin-left: 12px;">5) Confirm account number, enter amount, and approve payment</p>
                  ` : ''}
                </div>
              </div>
            `).join('')}

          </div>

          <!-- Summary Section -->
          <div class="section">
            <div class="section-title">📊 Amount Summary</div>
            <div class="instructions">
              <div class="instructions-title">Virtual Route Totals vs Cash Office Totals:</div>
              <div class="instruction-text">
                ${paymentCodes.payment_codes.map(code => 
                  `• <strong>${code.fee_type}:</strong> GH₵ ${Number(code.base_amount || 0).toFixed(2)} school fee + GH₵ ${Number(code.convenience_fee_amount || 0).toFixed(2)} convenience fee = GH₵ ${Number(code.total_amount || code.amount || 0).toFixed(2)} via route. Cash at office stays GH₵ ${Number(code.base_amount || 0).toFixed(2)}.`
                ).join('<br>')}
              </div>
              <div class="instruction-text" style="margin-top: 15px; font-weight: bold; border-top: 1px solid #ddd; padding-top: 10px;">
                Total via route: GH₵ ${totalVirtualRouteAmount.toFixed(2)} • Total convenience fees: GH₵ ${totalConvenienceFees.toFixed(2)} • Total by cash at school office: GH₵ ${totalCashAmount.toFixed(2)}
              </div>
            </div>
          </div>

          <!-- Contact Instructions -->
          <div class="section">
            <div class="section-title">❓ Questions?</div>
            <div class="instructions">
              <div class="instruction-text">
                If you have any questions about these payment routes or which fee route to use:
              </div>
              ${schoolPhone ? `<div class="instruction-text">📞 Call: ${schoolPhone}</div>` : ''}
              ${schoolEmail ? `<div class="instruction-text">✉️ Email: ${schoolEmail}</div>` : ''}
              <div class="instruction-text" style="margin-top: 10px;">
                Or visit the school office during office hours.
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="footer">
            <p>Generated on ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</p>
            <p>Please keep this document for your records</p>
          </div>
        </div>
      </body>
      </html>
    `;
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => printWindow.print(), 500);
  };

  const printPaymentReceipt = (student, payment, feeTypeSummary) => {
    if (!student || !payment) return;

    const schoolName = branding.school_name || branding.name || 'School';
    const schoolEmail = branding.school_email || branding.email || '';
    const schoolPhone = branding.school_phone || branding.phone || '';
    const schoolAddress = branding.school_address || branding.address || '';
    const themeColor = branding.theme_color || '#3b82f6';

    const receiptNumber = `RCPT-${payment.id}`;
    const paidAmount = Number(payment.amount || 0);
    const baseAmount = Number(payment.base_amount || paidAmount);
    const convenienceFee = Number(payment.convenience_fee_amount || 0);
    const isConfirmed = payment.status === 'Verified' || payment.status === 'Confirmed';

    const printWindow = window.open('', '', 'width=900,height=1100');
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Payment Receipt - ${student.name}</title>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.55;
            color: #1f2937;
            background: #f5f5f5;
            padding: 20px;
          }
          .container {
            max-width: 760px;
            margin: 0 auto;
            background: #fff;
            padding: 36px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
          }
          .header {
            border-bottom: 3px solid ${themeColor};
            padding-bottom: 14px;
            margin-bottom: 24px;
          }
          .school-name {
            font-size: 24px;
            font-weight: 700;
            color: ${themeColor};
            margin-bottom: 4px;
          }
          .contact {
            font-size: 12px;
            color: #6b7280;
          }
          .title-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
          }
          .title {
            font-size: 20px;
            font-weight: 800;
            letter-spacing: 0.5px;
          }
          .status {
            font-size: 12px;
            font-weight: 700;
            padding: 6px 10px;
            border-radius: 999px;
            background: ${isConfirmed ? '#dcfce7' : '#fef9c3'};
            color: ${isConfirmed ? '#166534' : '#854d0e'};
          }
          .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            margin-bottom: 22px;
          }
          .card {
            background: #f8fafc;
            border-left: 4px solid ${themeColor};
            padding: 12px;
            border-radius: 4px;
          }
          .label {
            font-size: 11px;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            margin-bottom: 5px;
          }
          .value {
            font-size: 14px;
            color: #0f172a;
            font-weight: 600;
            word-break: break-word;
          }
          .summary {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 18px;
          }
          .summary-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 14px;
            border-bottom: 1px solid #f1f5f9;
            font-size: 14px;
          }
          .summary-row:last-child { border-bottom: none; }
          .total {
            font-weight: 800;
            font-size: 16px;
            background: #eff6ff;
          }
          .footer {
            margin-top: 22px;
            padding-top: 14px;
            border-top: 1px solid #e5e7eb;
            font-size: 12px;
            color: #6b7280;
            text-align: center;
          }
          @media print {
            body { background: #fff; padding: 0; }
            .container { box-shadow: none; border-radius: 0; }
          }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <div class="school-name">${schoolName}</div>
            <div class="contact">
              ${schoolAddress ? `${schoolAddress}<br>` : ''}
              ${schoolPhone ? `📞 ${schoolPhone} ` : ''}
              ${schoolEmail ? `• ✉️ ${schoolEmail}` : ''}
            </div>
          </div>

          <div class="title-row">
            <div class="title">🧾 PAYMENT RECEIPT</div>
            <div class="status">${isConfirmed ? 'CONFIRMED' : 'PENDING VERIFICATION'}</div>
          </div>

          <div class="grid">
            <div class="card">
              <div class="label">Receipt Number</div>
              <div class="value">${receiptNumber}</div>
            </div>
            <div class="card">
              <div class="label">Payment Date</div>
              <div class="value">${payment.date_paid || '-'}</div>
            </div>
            <div class="card">
              <div class="label">Student</div>
              <div class="value">${student.name} (${student.student_code || 'N/A'})</div>
            </div>
            <div class="card">
              <div class="label">Fee Type</div>
              <div class="value">${getFeeTypeLabel(payment.payment_type || '')}</div>
            </div>
            <div class="card">
              <div class="label">Payment Method</div>
              <div class="value">${payment.method || '-'}</div>
            </div>
            <div class="card">
              <div class="label">Reference</div>
              <div class="value">${payment.reference_id || '-'}</div>
            </div>
          </div>

          <div class="summary">
            <div class="summary-row"><span>Base Amount</span><strong>GH₵ ${baseAmount.toFixed(2)}</strong></div>
            <div class="summary-row"><span>Convenience Fee</span><strong>GH₵ ${convenienceFee.toFixed(2)}</strong></div>
            <div class="summary-row total"><span>Total Paid</span><strong>GH₵ ${paidAmount.toFixed(2)}</strong></div>
          </div>

          <div class="summary">
            <div class="summary-row"><span>Required for ${getFeeTypeLabel(payment.payment_type || '')}</span><strong>GH₵ ${Number(feeTypeSummary?.requiredAmount || 0).toFixed(2)}</strong></div>
            <div class="summary-row"><span>Total Paid so far (${getFeeTypeLabel(payment.payment_type || '')})</span><strong>GH₵ ${Number(feeTypeSummary?.totalPaid || 0).toFixed(2)}</strong></div>
            <div class="summary-row"><span>Outstanding Balance</span><strong>GH₵ ${Number(feeTypeSummary?.outstanding || 0).toFixed(2)}</strong></div>
            <div class="summary-row"><span>Refundable Credit</span><strong>GH₵ ${Number(feeTypeSummary?.refundable || 0).toFixed(2)}</strong></div>
          </div>

          <div class="footer">
            Generated on ${new Date().toLocaleString()} • Keep this receipt for records
          </div>
        </div>
      </body>
      </html>
    `;

    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => printWindow.print(), 500);
  };

  const calculatePaymentSummary = (student, paymentType) => {
    const relatedPayments = studentPayments.filter(p => p.payment_type === paymentType);
    const totalPaid = relatedPayments.reduce((sum, p) => {
      return (p.status === 'Verified' || p.status === 'Confirmed') ? sum + p.amount : sum;
    }, 0);

    let requiredAmount = 0;
    if (paymentType === 'Tuition' && schoolFees?.tuition_fee) {
      // Combine tuition and terminal report fees
      requiredAmount = schoolFees.tuition_fee + (schoolFees.terminal_report_fee || 0);
    } else if (paymentType === 'Feeding' && schoolFees?.feeding_fee) {
      requiredAmount = schoolFees.feeding_fee;
    } else if (paymentType === 'Uniform' && schoolFees?.uniform_fee) {
      requiredAmount = schoolFees.uniform_fee;
    } else if (paymentType === 'Transport' && schoolFees?.transport_fee) {
      requiredAmount = schoolFees.transport_fee;
    }

    const outstanding = Math.max(0, requiredAmount - totalPaid);
    const refundable = Math.max(0, totalPaid - requiredAmount);
    const isPaid = outstanding === 0;
    const isPending = totalPaid > 0 && outstanding > 0;

    return {
      totalPaid,
      requiredAmount,
      outstanding,
      refundable,
      isPaid,
      isPending,
      paymentHistory: relatedPayments
    };
  };

  const filteredStudents = students.filter(student => {
    const matchesSearch = student.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (student.student_code && student.student_code.toLowerCase().includes(searchTerm.toLowerCase()));
    
    if (filterStatus === 'all') return matchesSearch;
    
    if (matchesSearch && selectedStudent?.id === student.id) {
      // Check payment status
      const feeTypes = ['Tuition', 'Feeding', 'Uniform', 'Transport'];
      const paymentStatus = feeTypes.map(type => calculatePaymentSummary(student, type));
      
      if (filterStatus === 'paid') {
        return paymentStatus.some(p => p.isPaid);
      } else if (filterStatus === 'pending') {
        return paymentStatus.some(p => p.isPending);
      }
    }
    
    return matchesSearch;
  });

  const classOptionsForWhatsapp = Array.from(new Set(students.map(s => s.current_class).filter(Boolean))).sort();
  const outstandingStudents = students.filter((student) =>
    (student.total_tuition_owed || 0) > 0 ||
    (student.total_feeding_owed || 0) > 0 ||
    (student.total_transport_owed || 0) > 0 ||
    (student.total_uniform_owed || 0) > 0
  );
  const classScopedOutstandingStudents = outstandingStudents;

  const feeTypes = ['Tuition', 'Feeding', 'Uniform', 'Transport'];

  // Helper function to display fee type label (includes terminal report for tuition)
  const getFeeTypeLabel = (feeType) => {
    return feeType === 'Tuition' ? 'Tuition + Terminal Report' : feeType;
  };

  const latestReceiptPayment = [...studentPayments]
    .sort((left, right) => new Date(right.date_paid || 0) - new Date(left.date_paid || 0))[0] || null;
  const latestReceiptSummary = latestReceiptPayment && selectedStudent
    ? calculatePaymentSummary(selectedStudent, latestReceiptPayment.payment_type)
    : null;

  return (
    <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-slate-800">💳 Student Payment Tracker</h2>
        <button
          onClick={handleBulkWhatsappPaymentReminders}
          disabled={!isPremium || sendingBulkWhatsapp}
          className={`px-4 py-2 rounded-lg font-bold text-sm transition-colors ${
            isPremium
              ? 'bg-emerald-600 text-white hover:bg-emerald-700'
              : 'bg-slate-200 text-slate-400 cursor-not-allowed'
          }`}
          title={isPremium ? 'Send payment reminders using selected targeting mode' : 'Premium plan required'}
        >
          {sendingBulkWhatsapp ? '⏳ Sending...' : '🟢 WhatsApp Payment Reminders'}
        </button>
      </div>

      <div className="mb-6 p-4 rounded-lg border bg-slate-50">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs font-bold text-slate-600 mb-1">Target Mode</label>
            <select
              value={whatsappTargetMode}
              onChange={(e) => setWhatsappTargetMode(e.target.value)}
              className="w-full p-2 border rounded-lg bg-white"
            >
              <option value="class">All by Class</option>
              <option value="single">Single Student</option>
              <option value="selected">Select Multiple Students</option>
            </select>
          </div>

          {whatsappTargetMode === 'class' && (
            <div>
              <label className="block text-xs font-bold text-slate-600 mb-1">Class</label>
              <select
                value={whatsappClassName}
                onChange={(e) => setWhatsappClassName(e.target.value)}
                className="w-full p-2 border rounded-lg bg-white"
              >
                {classOptionsForWhatsapp.length === 0 ? (
                  <option value="">No classes</option>
                ) : (
                  classOptionsForWhatsapp.map((cls) => (
                    <option key={cls} value={cls}>{cls}</option>
                  ))
                )}
              </select>
            </div>
          )}

          {whatsappTargetMode === 'selected' && (
            <div className="md:col-span-2">
              <label className="block text-xs font-bold text-slate-600 mb-1">Select Students</label>
              <select
                multiple
                value={whatsappStudentIds.map(String)}
                onChange={(e) => {
                  const values = Array.from(e.target.selectedOptions).map((option) => Number(option.value));
                  setWhatsappStudentIds(values);
                }}
                className="w-full p-2 border rounded-lg bg-white h-24"
              >
                {classScopedOutstandingStudents.map((student) => (
                  <option key={student.id} value={student.id}>
                    {student.name} ({student.current_class || 'No Class'})
                  </option>
                ))}
              </select>
              <p className="text-xs text-slate-500 mt-1">Hold Ctrl/Cmd to select multiple students.</p>
            </div>
          )}
        </div>

        {whatsappResult && (
          <div className="mt-4 p-3 rounded bg-white border">
            <p className="text-sm font-bold text-slate-800">WhatsApp Send Result</p>
            <p className="text-xs text-slate-600 mt-1">
              Mode: {whatsappResult.target_mode || '-'} • Attempted: {whatsappResult.attempted_count || 0} • Sent: {whatsappResult.sent_count || 0} • Skipped: {whatsappResult.skipped_count || 0}
            </p>
            {(whatsappResult.skipped || []).length > 0 && (
              <div className="mt-2 text-xs text-red-700 max-h-24 overflow-y-auto">
                {(whatsappResult.skipped || []).slice(0, 10).map((item) => (
                  <div key={`${item.student_id}-${item.reason}`}>
                    {item.student_name}: {item.verification_status || item.reason}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      
      {/* Search & Filter */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div>
          <input
            type="text"
            placeholder="Search by student name or ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full p-3 border rounded-lg bg-slate-50"
          />
        </div>
        <div>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="w-full p-3 border rounded-lg bg-slate-50"
          >
            <option value="all">All Status</option>
            <option value="paid">Fully Paid</option>
            <option value="pending">Partially Paid</option>
          </select>
        </div>
      </div>

      {/* Students List */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Student List Sidebar */}
        <div className="lg:col-span-1 border rounded-lg bg-slate-50 max-h-96 overflow-y-auto">
          <div className="p-4 border-b sticky top-0 bg-slate-50">
            <p className="text-sm font-bold text-slate-700">Select Student</p>
          </div>
          <div>
            {filteredStudents.slice(0, 50).map((student) => (
              <button
                key={student.id}
                onClick={() => handleSelectStudent(student)}
                className={`w-full text-left p-4 border-b transition-colors ${
                  selectedStudent?.id === student.id
                    ? 'bg-blue-100 border-l-4 border-l-blue-600'
                    : 'hover:bg-slate-100'
                }`}
              >
                <p className="font-semibold text-slate-800">{student.name}</p>
                <p className="text-xs text-slate-600">{student.student_code || student.current_class || 'No class'}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Payment Details Panel */}
        <div className="lg:col-span-2">
          {selectedStudent ? (
            <div className="space-y-4">
              {/* Student Header */}
              <div className="bg-linear-to-r from-blue-50 to-slate-50 p-4 rounded-lg border border-blue-200">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <h3 className="text-lg font-bold text-slate-800">{selectedStudent.name}</h3>
                    <p className="text-sm text-slate-600">ID: {selectedStudent.student_code || 'N/A'} • Class: {selectedStudent.current_class || 'Not assigned'}</p>
                    {selectedStudent.parent_phone && <p className="text-sm text-slate-600">👤 {selectedStudent.parent_name || 'Guardian'} • {selectedStudent.parent_phone}</p>}
                  </div>
                  {latestReceiptPayment && latestReceiptSummary && (
                    <div className="flex flex-col items-start gap-2 md:items-end">
                      <button
                        onClick={() => printPaymentReceipt(selectedStudent, latestReceiptPayment, latestReceiptSummary)}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 transition-colors"
                        title="Print latest recorded payment receipt"
                      >
                        🧾 Print Latest Receipt
                      </button>
                      <p className="text-xs text-slate-600">
                        Latest receipt: {getFeeTypeLabel(latestReceiptPayment.payment_type || 'Payment')} • {new Date(latestReceiptPayment.date_paid).toLocaleDateString()}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Payment Routes Section */}
              {paymentCodes && paymentCodes.payment_codes && paymentCodes.payment_codes.length > 0 && (
                <div className="bg-amber-50 border-l-4 border-l-amber-600 p-4 rounded-lg">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-bold text-amber-900 flex items-center gap-2">
                      📋 Payment Routes to Share with Parent
                    </h4>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          const codesText = paymentCodes.payment_codes
                            .map(c => {
                              const routeText = c.virtual_bank_account
                                ? `Virtual Account ${c.virtual_bank_account}${c.virtual_bank_name ? ` (${c.virtual_bank_name})` : ''}`
                                : 'Virtual route pending - contact school accounts office';
                              return `${c.fee_type}: ${routeText} | School fee GH₵ ${Number(c.base_amount || 0).toFixed(2)} + convenience fee GH₵ ${Number(c.convenience_fee_amount || 0).toFixed(2)} = GH₵ ${Number(c.total_amount || c.amount || 0).toFixed(2)} via route | Cash at school office GH₵ ${Number(c.base_amount || 0).toFixed(2)} | Ref ${c.reference_code || c.code}`;
                            })
                            .join('\n');
                          const instructions = `Payment Instructions for ${paymentCodes.student_name}\n\nStudent ID: ${paymentCodes.student_code}\n\n${codesText}\n\nUse the matching route for each fee type. Virtual-route amounts already include the convenience fee. If a parent wants to avoid the convenience fee, they can pay the school fee amount by cash at the school office instead. If a virtual account is not yet available, contact the school's accounts office and include the backup reference.`;
                          navigator.clipboard.writeText(instructions);
                          alert('Instructions copied to clipboard!');
                        }}
                        className="px-3 py-1 bg-amber-600 text-white rounded text-xs font-bold hover:bg-amber-700 transition-colors"
                      >
                        📋 Copy Instructions
                      </button>
                      <button
                        onClick={printPaymentInstructions}
                        className="px-3 py-1 bg-blue-600 text-white rounded text-xs font-bold hover:bg-blue-700 transition-colors"
                      >
                        🖨️ Print Instructions
                      </button>
                    </div>
                  </div>
                  <div className="space-y-2">
                    {paymentCodes.payment_codes.map((code, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-3 bg-white rounded border border-amber-200 text-sm"
                      >
                        <div className="flex-1">
                          <p className="font-semibold text-slate-800">{code.fee_type}</p>
                          <p className="text-xs text-slate-600">Amount: GH₵ {code.amount.toFixed(2)}</p>
                          <p className="text-xs text-slate-600">School Fee: GH₵ {Number(code.base_amount || 0).toFixed(2)}</p>
                          <p className="text-xs text-slate-600">Convenience Fee: GH₵ {Number(code.convenience_fee_amount || 0).toFixed(2)} ({Number(code.convenience_fee_percent || 0).toFixed(2)}%)</p>
                          <p className="text-xs font-semibold text-slate-700">Total via Route: GH₵ {Number(code.total_amount || code.amount || 0).toFixed(2)}</p>
                          <p className="text-xs text-slate-600">Cash at School Office: GH₵ {Number(code.base_amount || 0).toFixed(2)}</p>
                          <p className="text-xs text-slate-700">
                            {code.virtual_bank_account
                              ? `🏦 Virtual Account: ${code.virtual_bank_account}${code.virtual_bank_name ? ` (${code.virtual_bank_name})` : ''}`
                              : '🏦 Virtual route pending: Pay by cash at the school office or contact accounts office for approved manual instructions'}
                          </p>

                          <p className="text-xs text-slate-600">Backup Ref: {code.reference_code || code.code}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <code className="block bg-amber-100 text-amber-900 px-3 py-2 rounded font-mono font-bold text-sm">
                            {code.virtual_bank_account || (code.reference_code || code.code)}
                          </code>
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(code.virtual_bank_account || (code.reference_code || code.code));
                              alert('Route copied!');
                            }}
                            className="px-2 py-2 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors text-xs font-bold"
                          >
                            📋 Copy
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-amber-800 mt-3 italic">
                    💬 Example instruction: "Pay GH₵ <strong>{Number(paymentCodes.payment_codes[0]?.base_amount || 0).toFixed(2)}</strong> school fee + GH₵ <strong>{Number(paymentCodes.payment_codes[0]?.convenience_fee_amount || 0).toFixed(2)}</strong> convenience fee = GH₵ <strong>{Number(paymentCodes.payment_codes[0]?.total_amount || paymentCodes.payment_codes[0]?.amount || 0).toFixed(2)}</strong> via <strong>{paymentCodes.payment_codes[0]?.virtual_bank_account ? `virtual route ${paymentCodes.payment_codes[0]?.virtual_bank_account}` : 'approved manual instruction from the accounts office'}</strong>. If you want to avoid the convenience fee, pay GH₵ <strong>{Number(paymentCodes.payment_codes[0]?.base_amount || 0).toFixed(2)}</strong> by cash at the school office. Backup ref: <strong>{paymentCodes.payment_codes[0]?.reference_code || paymentCodes.payment_codes[0]?.code || 'S0011'}</strong>."
                  </p>
                </div>
              )}

              {/* Fee Breakdown */}
              {loading ? (
                <p className="text-center text-slate-600 py-8">Loading payment data...</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {feeTypes.map((feeType) => {
                    const summary = calculatePaymentSummary(selectedStudent, feeType);
                    if (summary.requiredAmount === 0) return null;

                    return (
                      <div key={feeType} className="border rounded-lg p-4 bg-slate-50">
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="font-bold text-slate-800">{getFeeTypeLabel(feeType)}</h4>
                          <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                            summary.isPaid ? 'bg-green-100 text-green-700' :
                            summary.isPending ? 'bg-yellow-100 text-yellow-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {summary.isPaid ? '✅ Paid' : summary.isPending ? '⏳ Partial' : '❌ Outstanding'}
                          </span>
                        </div>

                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-slate-600">Required:</span>
                            <span className="font-semibold text-slate-800">GH₵ {summary.requiredAmount.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-600">Paid:</span>
                            <span className="font-semibold text-green-700">GH₵ {summary.totalPaid.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between pt-2 border-t">
                            <span className="font-bold text-slate-700">Outstanding:</span>
                            <span className={`font-bold ${summary.outstanding > 0 ? 'text-red-600' : 'text-green-600'}`}>
                              GH₵ {summary.outstanding.toFixed(2)}
                            </span>
                          </div>
                          {summary.refundable > 0 && (
                            <div className="flex justify-between">
                              <span className="font-bold text-slate-700">Refundable:</span>
                              <span className="font-bold text-blue-700">
                                GH₵ {summary.refundable.toFixed(2)}
                              </span>
                            </div>
                          )}

                          {/* Progress Bar */}
                          <div className="mt-3">
                            <div className="w-full bg-slate-300 rounded-full h-2">
                              <div
                                className={`h-2 rounded-full transition-all ${
                                  summary.isPaid ? 'bg-green-600' : 'bg-yellow-500'
                                }`}
                                style={{ width: `${Math.min(100, (summary.totalPaid / summary.requiredAmount) * 100)}%` }}
                              />
                            </div>
                            <p className="text-xs text-slate-600 mt-1">{Math.round((summary.totalPaid / summary.requiredAmount) * 100)}% paid</p>
                          </div>
                        </div>

                        {/* Payment History */}
                        {summary.paymentHistory.length > 0 && (
                          <div className="mt-4 pt-4 border-t">
                            <p className="text-xs font-bold text-slate-700 mb-2">Recent Payments:</p>
                            <div className="space-y-1 max-h-32 overflow-y-auto">
                              {summary.paymentHistory.slice(0, 5).map((payment) => (
                                <div key={payment.id} className="text-xs flex items-center justify-between gap-2">
                                  <div>
                                    <span>{payment.method} - {new Date(payment.date_paid).toLocaleDateString()}</span>
                                    {payment.reference_id && (
                                      <span className="ml-2 text-slate-500">Ref: {payment.reference_id}</span>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <span className={(payment.status === 'Verified' || payment.status === 'Confirmed') ? 'text-green-700 font-bold' : 'text-yellow-700'}>
                                      GH₵ {payment.amount.toFixed(2)}
                                    </span>
                                    <button
                                      onClick={() => printPaymentReceipt(selectedStudent, payment, summary)}
                                      className="px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors font-bold"
                                      title="Print payment receipt"
                                    >
                                      🧾 Print Receipt
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Total Summary */}
              {!loading && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="font-bold text-slate-800 mb-3">📊 Total Summary</h4>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-slate-600">Total Required</p>
                      <p className="text-xl font-bold text-slate-800">
                        GH₵ {feeTypes.reduce((sum, type) => {
                          const summary = calculatePaymentSummary(selectedStudent, type);
                          return sum + summary.requiredAmount;
                        }, 0).toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-slate-600">Total Paid</p>
                      <p className="text-xl font-bold text-green-700">
                        GH₵ {feeTypes.reduce((sum, type) => {
                          const summary = calculatePaymentSummary(selectedStudent, type);
                          return sum + summary.totalPaid;
                        }, 0).toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-slate-600 col-span-2">Total Outstanding</p>
                      <p className="text-xl font-bold text-red-600 col-span-2">
                        GH₵ {feeTypes.reduce((sum, type) => {
                          const summary = calculatePaymentSummary(selectedStudent, type);
                          return sum + summary.outstanding;
                        }, 0).toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-slate-600 col-span-2">Total Refundable</p>
                      <p className="text-xl font-bold text-blue-700 col-span-2">
                        GH₵ {feeTypes.reduce((sum, type) => {
                          const summary = calculatePaymentSummary(selectedStudent, type);
                          return sum + summary.refundable;
                        }, 0).toFixed(2)}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-96 text-slate-600">
              <p className="text-center">
                <span className="text-3xl mb-2 block">👆</span>
                Select a student to view payment details
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
