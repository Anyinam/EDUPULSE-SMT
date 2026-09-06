import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useBranding } from '../hooks/useBranding';

export default function StudentPaymentTracker() {
  const [students, setStudents] = useState([]);
  const [schoolFees, setSchoolFees] = useState(null);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [studentPayments, setStudentPayments] = useState([]);
  const [paymentCodes, setPaymentCodes] = useState(null);
  const [paymentCodesError, setPaymentCodesError] = useState(null);
  const [linkLoadingCode, setLinkLoadingCode] = useState('');
  const [generatedLinks, setGeneratedLinks] = useState({});
  const [transferRouteLoadingCode, setTransferRouteLoadingCode] = useState('');
  const [generatedVirtualRoutes, setGeneratedVirtualRoutes] = useState({});
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedClass, setSelectedClass] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all'); // all, paid, pending, overdue
  const { branding } = useBranding();

  useEffect(() => {
    fetchStudents();
    fetchSchoolFees();
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
      if (err.response?.data?.error !== 'school_verification_required' && err.response?.data?.error !== 'payment_collection_blocked') {
        console.error('Failed to load student payments');
      }
      setStudentPayments([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectStudent = (student) => {
    setSelectedStudent(student);
    setPaymentCodesError(null);
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
      setPaymentCodesError(null);
    } catch (err) {
      const responseData = err.response?.data || null;
      if (responseData?.error === 'payment_collection_blocked' || responseData?.error === 'school_verification_required') {
        setPaymentCodesError(responseData);
      } else {
        console.error('Failed to load payment codes');
        setPaymentCodesError({
          message: responseData?.message || 'Unable to load payment references right now.',
        });
      }
      setPaymentCodes(null);
    }
  };

  const generateTrackedPaymentLink = async (paymentCode) => {
    if (!selectedStudent || !paymentCode?.reference_code) {
      return;
    }

    try {
      setLinkLoadingCode(paymentCode.reference_code);
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const callbackUrl = `${window.location.origin}/payment-callback`;
      const res = await axios.post('/api/finance/paystack/initialize-payment', {
        student_id: selectedStudent.id,
        reference_code: paymentCode.reference_code,
        payment_type: paymentCode.payment_category?.fee_type || paymentCode.fee_type,
        amount: Number(paymentCode.base_amount || paymentCode.amount || 0),
        payment_category: paymentCode.payment_category || {},
        callback_url: callbackUrl,
      }, { headers });

      const checkoutUrl = res.data?.authorization_url;
      if (!checkoutUrl) {
        alert(res.data?.message || 'Unable to generate tracked payment link.');
        return;
      }

      setGeneratedLinks((current) => ({
        ...current,
        [paymentCode.reference_code]: checkoutUrl,
      }));
      window.open(checkoutUrl, '_blank', 'noopener,noreferrer');
    } catch (err) {
      alert(err.response?.data?.message || 'Unable to generate tracked payment link right now.');
    } finally {
      setLinkLoadingCode('');
    }
  };

  const generateTrackedTransferRoute = async (paymentCode) => {
    if (!selectedStudent || !paymentCode?.reference_code) {
      return;
    }

    try {
      setTransferRouteLoadingCode(paymentCode.reference_code);
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.post(
        `/api/students/${selectedStudent.id}/payment-codes/${encodeURIComponent(paymentCode.reference_code)}/virtual-account`,
        {},
        { headers }
      );

      const route = res.data?.virtual_route;
      if (!route?.account_number) {
        alert(res.data?.message || 'Unable to generate a tracked transfer account.');
        return;
      }

      setGeneratedVirtualRoutes((current) => ({
        ...current,
        [paymentCode.reference_code]: route,
      }));
      setPaymentCodes((current) => {
        if (!current?.payment_codes) {
          return current;
        }
        return {
          ...current,
          payment_codes: current.payment_codes.map((code) => (
            (code.reference_code || code.code) === paymentCode.reference_code
              ? (res.data?.payment_code || code)
              : code
          )),
        };
      });
    } catch (err) {
      alert(err.response?.data?.message || 'Unable to generate a tracked transfer account right now.');
    } finally {
      setTransferRouteLoadingCode('');
    }
  };

  const printPaymentInstructions = () => {
    if (!paymentCodes) return;

    const schoolName = branding.school_name || branding.name || 'School';
    const schoolEmail = branding.school_email || branding.email || '';
    const schoolPhone = branding.school_phone || branding.phone || '';
    const schoolAddress = branding.school_address || branding.address || '';
    const themeColor = branding.theme_color || '#3b82f6';
    const schoolPaymentAccount = paymentCodes.school_payment_account || {};
    const bankName = schoolPaymentAccount.bank_name || '';
    const bankAccount = schoolPaymentAccount.bank_account || '';
    const bankAccountName = schoolPaymentAccount.bank_account_name || '';
    const bankBranch = schoolPaymentAccount.bank_branch || '';
    const hasBankDetails = Boolean(bankName || bankAccount || bankAccountName || bankBranch);

    const totalCashAmount = paymentCodes.payment_codes.reduce((sum, code) => sum + Number(code.base_amount || code.cash_amount || 0), 0);

    const printWindow = window.open('', '', 'width=900,height=1200');
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Payment Instructions & Reference Guide - ${paymentCodes.student_name}</title>
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
          <div class="document-title">📋 Payment Instructions For Parent</div>

          <!-- Student Information -->
          <div class="student-info">
            <p><span class="info-label">Student Name:</span> ${paymentCodes.student_name}</p>
            <p><span class="info-label">Stable Payment Identity:</span> <strong>${paymentCodes.student_code}</strong></p>
            <p><span class="info-label">Class:</span> ${paymentCodes.class || 'Not assigned'}</p>
            ${paymentCodes.parent_phone ? `<p><span class="info-label">Parent/Guardian:</span> ${paymentCodes.parent_name || ''} (${paymentCodes.parent_phone})</p>` : ''}
          </div>

          ${hasBankDetails ? `
          <div class="section">
            <div class="section-title">🏦 School Bank Account</div>
            <div class="payment-method">
              <div class="payment-method-content">
                <p><strong>Bank Name:</strong> ${bankName}</p>
                <p><strong>Account Number:</strong> ${bankAccount}</p>
                ${bankAccountName ? `<p><strong>Account Name:</strong> ${bankAccountName}</p>` : ''}
                ${bankBranch ? `<p><strong>Branch:</strong> ${bankBranch}</p>` : ''}
                <p style="margin-top: 8px;"><strong>Use this only when the school has asked for a direct bank transfer or office-confirmed payment.</strong></p>
              </div>
            </div>
          </div>` : ''}

          <!-- Payment Routes Section -->
          <div class="section">
            <div class="section-title">💳 Fee References And Tracked Payment Options</div>
            <table class="payment-codes-table">
              <thead>
                <tr>
                  <th>Fee Type</th>
                  <th>Preferred Reference</th>
                  <th>Payment Channel</th>
                  <th class="amount-column">Amount</th>
                </tr>
              </thead>
              <tbody>
                ${paymentCodes.payment_codes.map(code => `
                  <tr>
                    <td><strong>${code.fee_type}</strong></td>
                    <td><span class="code-column">${code.reference_code || code.code}</span></td>
                    <td><span style="color:#475569;">Use the tracked transfer account or tracked payment link for this exact fee whenever the school provides one</span></td>
                    <td class="amount-column">GH₵ ${Number(code.base_amount || 0).toFixed(2)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>

          <!-- Important Notice -->
          <div class="important">
            <strong>⚠️ Important:</strong> Best option: use the tracked transfer account or tracked payment link created for the exact fee. That keeps the learner and fee purpose attached automatically.
          </div>

          <!-- Payment Methods Section -->
          <div class="section">
            <div class="section-title">💰 How to Pay</div>
            ${paymentCodes.payment_codes.map(code => `
              <div class="payment-method">
                <div class="payment-method-title">${code.fee_type}</div>
                <div class="payment-method-content">
                  <p><strong>Preferred Reference:</strong> ${code.reference_code || code.code}</p>
                  <p><strong>Best Option:</strong> Ask the school for the tracked transfer account or tracked payment link for this fee.</p>
                  ${hasBankDetails ? `<p><strong>School Bank Account:</strong> ${[bankName, bankAccount, bankAccountName].filter(Boolean).join(' • ')}${bankBranch ? ` • ${bankBranch}` : ''}</p>` : ''}
                  <p style="color:#475569;"><strong>Share the reference exactly as shown.</strong> Use it when the school asks for bank narration or office confirmation.</p>
                  <p><strong>Amount To Pay:</strong> GH₵ ${Number(code.base_amount || 0).toFixed(2)}</p>
                  <p><strong>Reference To Present At School Office:</strong> ${code.reference_code || code.code}</p>
                  <p style="margin-top: 8px;"><strong>Payment Flow:</strong></p>
                  <p style="margin-left: 12px;">1) Use the tracked transfer account or tracked payment link from the school for this fee whenever available.</p>
                  <p style="margin-left: 12px;">2) If the school instead gives a normal bank account, enter the amount shown for this fee.</p>
                  <p style="margin-left: 12px;">3) Keep reference <strong>${code.reference_code || code.code}</strong> in the narration or present it at the school office.</p>
                  <p style="margin-left: 12px;">4) The school records the payment under this learner and fee purpose.</p>
                </div>
              </div>
            `).join('')}

          </div>

          <!-- Summary Section -->
          <div class="section">
            <div class="section-title">📊 Amount Summary</div>
            <div class="instructions">
              <div class="instructions-title">Per-Fee Instructions:</div>
              <div class="instruction-text">
                ${paymentCodes.payment_codes.map(code => 
                  `• <strong>${code.fee_type}:</strong> Pay GH₵ ${Number(code.base_amount || 0).toFixed(2)} using the tracked transfer account or tracked payment link for reference <strong>${code.reference_code || code.code}</strong>. If the school asks for direct transfer, keep the same reference in the narration.`
                ).join('<br>')}
              </div>
              <div class="instruction-text" style="margin-top: 15px; font-weight: bold; border-top: 1px solid #ddd; padding-top: 10px;">
                Total amount due across these references: GH₵ ${totalCashAmount.toFixed(2)}
              </div>
            </div>
          </div>

          <!-- Contact Instructions -->
          <div class="section">
            <div class="section-title">❓ Questions?</div>
            <div class="instructions">
              <div class="instruction-text">
                If you have any questions about the payment reference to use or the school\'s approved payment channel:
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
            <div class="summary-row"><span>Amount Paid</span><strong>GH₵ ${baseAmount.toFixed(2)}</strong></div>
            <div class="summary-row total"><span>Total Recorded</span><strong>GH₵ ${paidAmount.toFixed(2)}</strong></div>
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

  const classOptions = Array.from(
    new Set(
      students
        .map((student) => (student.current_class || '').trim())
        .filter(Boolean)
    )
  ).sort((left, right) => left.localeCompare(right, undefined, { numeric: true, sensitivity: 'base' }));

  const filteredStudents = students.filter(student => {
    const matchesSearch = student.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (student.student_code && student.student_code.toLowerCase().includes(searchTerm.toLowerCase()));
    const studentClass = (student.current_class || '').trim();
    const matchesClass = selectedClass === 'all' || studentClass === selectedClass;

    if (!matchesSearch || !matchesClass) {
      return false;
    }
    
    if (filterStatus === 'all') return true;
    
    const feeTypes = ['Tuition', 'Feeding', 'Uniform', 'Transport'];
    const paymentStatus = feeTypes.map(type => calculatePaymentSummary(student, type));

    if (filterStatus === 'paid') {
      return paymentStatus.some(p => p.isPaid);
    } else if (filterStatus === 'pending') {
      return paymentStatus.some(p => p.isPending);
    }
    
    return true;
  });

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
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-bold text-slate-800">💳 Student Payment Tracker</h2>
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
            value={selectedClass}
            onChange={(e) => setSelectedClass(e.target.value)}
            className="w-full p-3 border rounded-lg bg-slate-50"
          >
            <option value="all">All Classes</option>
            {classOptions.map((className) => (
              <option key={className} value={className}>{className}</option>
            ))}
          </select>
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
            <p className="mt-1 text-xs text-slate-500">
              {filteredStudents.length} student{filteredStudents.length === 1 ? '' : 's'} found
              {selectedClass !== 'all' ? ` in ${selectedClass}` : ''}
            </p>
          </div>
          <div>
            {filteredStudents.length === 0 ? (
              <div className="p-4 text-sm text-slate-500">
                No students match this search or class filter.
              </div>
            ) : filteredStudents.slice(0, 100).map((student) => (
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
                <p className="text-xs text-slate-600">{student.student_code || 'No ID'} • {student.current_class || 'No class'}</p>
              </button>
            ))}
            {filteredStudents.length > 100 && (
              <div className="p-4 text-xs text-slate-500 border-t">
                Showing first 100 students. Narrow by class or type part of the student name or ID.
              </div>
            )}
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

              {paymentCodes?.school_payment_account && (
                (paymentCodes.school_payment_account.bank_name || paymentCodes.school_payment_account.bank_account || paymentCodes.school_payment_account.bank_account_name || paymentCodes.school_payment_account.bank_branch) ? (
                  <div className="rounded-2xl border border-cyan-200 bg-cyan-50 p-4 text-slate-900 shadow-sm">
                    <p className="text-xs font-black uppercase tracking-[0.22em] text-cyan-700">School Bank Account</p>
                    <div className="mt-2 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
                      {paymentCodes.school_payment_account.bank_name ? <p><strong>Bank:</strong> {paymentCodes.school_payment_account.bank_name}</p> : null}
                      {paymentCodes.school_payment_account.bank_account ? <p><strong>Account Number:</strong> {paymentCodes.school_payment_account.bank_account}</p> : null}
                      {paymentCodes.school_payment_account.bank_account_name ? <p><strong>Account Name:</strong> {paymentCodes.school_payment_account.bank_account_name}</p> : null}
                      {paymentCodes.school_payment_account.bank_branch ? <p><strong>Branch:</strong> {paymentCodes.school_payment_account.bank_branch}</p> : null}
                    </div>
                    <p className="mt-2 text-xs text-cyan-800">Use this only for direct bank transfer or office-confirmed payment. For automatic tracking, generate the tracked transfer account or tracked payment link below.</p>
                  </div>
                ) : null
              )}

              {/* Payment Routes Section */}
              {paymentCodesError ? (
                <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-amber-950 shadow-sm">
                  <p className="text-xs font-black uppercase tracking-[0.22em] text-amber-700">Collection Paused</p>
                  <h4 className="mt-2 text-lg font-black text-slate-950">Parent payment references are currently blocked.</h4>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{paymentCodesError.message}</p>
                  {paymentCodesError.error === 'payment_collection_blocked' ? (
                    <div className="mt-3 grid gap-3 sm:grid-cols-3">
                      <div className="rounded-xl border border-amber-200 bg-white px-3 py-2">
                        <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-amber-700">Plan</p>
                        <p className="mt-1 text-sm font-black text-slate-950">{paymentCodesError.effective_plan || 'Free Tier'}</p>
                      </div>
                      <div className="rounded-xl border border-amber-200 bg-white px-3 py-2">
                        <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-amber-700">Active Students</p>
                        <p className="mt-1 text-sm font-black text-slate-950">{paymentCodesError.active_students ?? 'Unknown'}</p>
                      </div>
                      <div className="rounded-xl border border-amber-200 bg-white px-3 py-2">
                        <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-amber-700">Plan Limit</p>
                        <p className="mt-1 text-sm font-black text-slate-950">{paymentCodesError.plan_limit ?? 50}</p>
                      </div>
                    </div>
                  ) : null}
                  {paymentCodesError.error === 'school_verification_required' ? (
                    <div className="mt-3 rounded-xl border border-amber-200 bg-white px-3 py-3 text-sm text-slate-700">
                      Submit and complete School Verification before sharing payment instructions or viewing parent-payment records.
                    </div>
                  ) : null}
                  <p className="mt-3 text-xs font-semibold text-amber-800">
                    {paymentCodesError.error === 'school_verification_required'
                      ? 'Verification sits above subscription access for payment operations.'
                      : 'Upgrade the school subscription or reduce active enrollment before sharing any new payment instruction with parents.'}
                  </p>
                </div>
              ) : null}

              {paymentCodes && paymentCodes.payment_codes && paymentCodes.payment_codes.length > 0 && (
                <div className="bg-amber-50 border-l-4 border-l-amber-600 p-4 rounded-lg">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-bold text-amber-900 flex items-center gap-2">
                      📋 Payment Instructions to Share with Parent
                    </h4>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          const codesText = paymentCodes.payment_codes
                            .map(c => {
                              return `${c.fee_type}: Ref ${c.reference_code || c.code} | Amount GH₵ ${Number(c.base_amount || 0).toFixed(2)} | Best option: tracked transfer account or tracked payment link`;
                            })
                            .join('\n');
                          const schoolPaymentAccount = paymentCodes.school_payment_account || {};
                          const bankLines = (schoolPaymentAccount.bank_name || schoolPaymentAccount.bank_account || schoolPaymentAccount.bank_account_name || schoolPaymentAccount.bank_branch)
                            ? `School Bank Account:\n${schoolPaymentAccount.bank_name ? `- Bank: ${schoolPaymentAccount.bank_name}\n` : ''}${schoolPaymentAccount.bank_account ? `- Account Number: ${schoolPaymentAccount.bank_account}\n` : ''}${schoolPaymentAccount.bank_account_name ? `- Account Name: ${schoolPaymentAccount.bank_account_name}\n` : ''}${schoolPaymentAccount.bank_branch ? `- Branch: ${schoolPaymentAccount.bank_branch}\n` : ''}\n`
                            : '';
                          const instructions = `Payment Instructions for ${paymentCodes.student_name}\n\nStable Payment Identity: ${paymentCodes.student_code}\n\n${bankLines}${codesText}\n\nBest option: use the tracked transfer account or tracked payment link generated from EduPulse for the exact fee. Only use the normal school bank account when the school is manually confirming the payment.`;
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
                    {(paymentCodes.school_payment_account?.bank_name || paymentCodes.school_payment_account?.bank_account || paymentCodes.school_payment_account?.bank_account_name || paymentCodes.school_payment_account?.bank_branch) && (
                      <div className="rounded-lg border border-amber-200 bg-white p-3 text-sm text-slate-700">
                        <p className="font-semibold text-slate-800">School Bank Account</p>
                        {paymentCodes.school_payment_account.bank_name && <p className="mt-1 text-xs text-slate-600">Bank: {paymentCodes.school_payment_account.bank_name}</p>}
                        {paymentCodes.school_payment_account.bank_account && <p className="text-xs text-slate-600">Account Number: {paymentCodes.school_payment_account.bank_account}</p>}
                        {paymentCodes.school_payment_account.bank_account_name && (
                          <p className="text-xs text-slate-600">Account Name: {paymentCodes.school_payment_account.bank_account_name}</p>
                        )}
                        {paymentCodes.school_payment_account.bank_branch && (
                          <p className="text-xs text-slate-600">Branch: {paymentCodes.school_payment_account.bank_branch}</p>
                        )}
                        <p className="mt-2 text-xs text-amber-800">Use this only when the school wants a direct bank transfer or office-confirmed payment. For automatic tracking, use the tracked transfer account or tracked payment link for the exact fee below.</p>
                      </div>
                    )}
                    {paymentCodes.payment_identity?.tracked_transfer_readiness_note ? (
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
                        <p className="font-semibold text-slate-800">Tracked transfer account setup</p>
                        <p className="mt-1">{paymentCodes.payment_identity.tracked_transfer_readiness_note}</p>
                      </div>
                    ) : null}
                    {paymentCodes.payment_codes.map((code, idx) => (
                      (() => {
                        const referenceKey = code.reference_code || code.code;
                        const virtualRoute = generatedVirtualRoutes[referenceKey] || code.virtual_route;
                        return (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-3 bg-white rounded border border-amber-200 text-sm"
                      >
                        <div className="flex-1">
                          <p className="font-semibold text-slate-800">{code.fee_type}</p>
                          <p className="text-xs text-slate-600">Amount: GH₵ {Number(code.base_amount || 0).toFixed(2)}</p>
                          <p className="text-xs font-semibold text-slate-700">Preferred Ref: {code.reference_code || code.code}</p>
                          <p className="text-xs text-slate-700">Best option: generate the tracked transfer account or tracked payment link for this exact fee so EduPulse records the learner and purpose automatically.</p>

                          <p className="text-xs text-slate-600">Reference: {code.reference_code || code.code}</p>
                          {generatedLinks[referenceKey] ? (
                            <p className="mt-2 break-all text-xs text-emerald-700">Tracked link ready: {generatedLinks[referenceKey]}</p>
                          ) : null}
                          {virtualRoute ? (
                            <div className="mt-2 rounded-lg border border-cyan-200 bg-cyan-50 p-2 text-xs text-cyan-900">
                              <p className="font-semibold">Tracked transfer account ready</p>
                              <p className="mt-1">Bank: {virtualRoute.bank_name || 'Paystack transfer account'}</p>
                              <p>Account number: {virtualRoute.account_number}</p>
                              {virtualRoute.account_name ? <p>Account name: {virtualRoute.account_name}</p> : null}
                              <p className="mt-1">Base fee: GH₵ {Number(virtualRoute.base_amount || 0).toFixed(2)}</p>
                              {Number(virtualRoute.convenience_fee_amount || 0) > 0 ? (
                                <p>Convenience fee: GH₵ {Number(virtualRoute.convenience_fee_amount || 0).toFixed(2)}</p>
                              ) : null}
                              <p className="font-semibold">Transfer total: GH₵ {Number(virtualRoute.total_amount || 0).toFixed(2)}</p>
                            </div>
                          ) : null}
                        </div>
                        <div className="flex items-center gap-2">
                          <code className="block bg-amber-100 text-amber-900 px-3 py-2 rounded font-mono font-bold text-sm">
                            {code.reference_code || code.code}
                          </code>
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(code.reference_code || code.code);
                              alert('Reference copied!');
                            }}
                            className="px-2 py-2 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors text-xs font-bold"
                          >
                            📋 Copy
                          </button>
                          {paymentCodes.payment_identity?.supports_fee_route_dvas ? (
                            <button
                              onClick={() => generateTrackedTransferRoute(code)}
                              disabled={transferRouteLoadingCode === referenceKey}
                              className="px-2 py-2 bg-cyan-600 text-white rounded hover:bg-cyan-700 transition-colors text-xs font-bold disabled:bg-cyan-300"
                            >
                              {transferRouteLoadingCode === referenceKey ? 'Creating...' : 'Tracked Transfer'}
                            </button>
                          ) : null}
                          <button
                            onClick={() => generateTrackedPaymentLink(code)}
                            disabled={linkLoadingCode === referenceKey}
                            className="px-2 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700 transition-colors text-xs font-bold disabled:bg-emerald-300"
                          >
                            {linkLoadingCode === referenceKey ? 'Generating...' : 'Tracked Link'}
                          </button>
                          {generatedLinks[referenceKey] ? (
                            <button
                              onClick={() => {
                                navigator.clipboard.writeText(generatedLinks[referenceKey]);
                                alert('Tracked payment link copied!');
                              }}
                              className="px-2 py-2 bg-slate-100 text-slate-700 rounded hover:bg-slate-200 transition-colors text-xs font-bold"
                            >
                              Copy Link
                            </button>
                          ) : null}
                        </div>
                      </div>
                        );
                      })()
                    ))}
                  </div>
                  <p className="text-xs text-amber-800 mt-3 italic">
                    💬 Preferred instruction: "Use the tracked transfer account or tracked payment link generated from EduPulse for reference <strong>{paymentCodes.payment_codes[0]?.reference_code || paymentCodes.payment_codes[0]?.code || 'S001-T1'}</strong>. Only use the normal school bank account if the school asks for direct transfer confirmation." 
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
