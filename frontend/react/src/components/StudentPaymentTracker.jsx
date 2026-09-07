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
  const [bulkPrintLoading, setBulkPrintLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedClass, setSelectedClass] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all'); // all, paid, pending, overdue
  const [recoveryReference, setRecoveryReference] = useState('');
  const [recoveryLoading, setRecoveryLoading] = useState(false);
  const [recoveryResult, setRecoveryResult] = useState(null);
  const { branding } = useBranding();

  const getTuitionConvenienceDetails = (code, codesRecord = paymentCodes) => {
    const configuredPercentage = Number(codesRecord?.fees_configuration?.tuition_convenience_fee_percentage || schoolFees?.tuition_convenience_fee_percentage || 0);
    const amount = Number(code?.virtual_route?.convenience_fee_amount || 0);
    const baseAmount = Number(code?.virtual_route?.base_amount || code?.base_amount || 0);
    const percentage = configuredPercentage > 0
      ? configuredPercentage
      : (amount > 0 && baseAmount > 0 ? Number(((amount / baseAmount) * 100).toFixed(2)) : 0);
    return {
      percentage,
      amount,
    };
  };

  const getTrackerPaymentCodes = (codesRecord) => (codesRecord?.payment_codes || []).filter(
    (code) => (code?.payment_category?.fee_type || code?.fee_type) === 'Tuition'
  );

  const getAuthHeaders = () => ({
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  useEffect(() => {
    fetchStudents();
    fetchSchoolFees();
  }, []);

  const fetchStudents = async () => {
    try {
      const res = await axios.get('/api/students', getAuthHeaders());
      const studentList = Array.isArray(res.data) ? res.data : res.data?.students || [];
      setStudents(studentList);
    } catch (err) {
      console.error('Failed to load students');
    }
  };

  const fetchSchoolFees = async () => {
    try {
      const res = await axios.get('/api/school/fees', getAuthHeaders());
      setSchoolFees(res.data);
    } catch (err) {
      console.error('Failed to load school fees');
    }
  };

  const fetchStudentPayments = async (studentId) => {
    try {
      setLoading(true);
      const res = await axios.get(`/api/students/${studentId}/payments`, getAuthHeaders());
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

  const fetchPaymentCodesData = async (studentId) => {
    const res = await axios.get(`/api/students/${studentId}/payment-codes`, getAuthHeaders());
    return res.data;
  };

  const fetchPaymentCodes = async (studentId) => {
    try {
      const result = await fetchPaymentCodesData(studentId);
      const preparedResult = await ensureTrackedTransferRoutes(studentId, result);
      setPaymentCodes(preparedResult);
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

  const ensureTrackedTransferRoutes = async (studentId, codesRecord) => {
    if (!codesRecord?.payment_identity?.supports_fee_route_dvas || !Array.isArray(codesRecord.payment_codes) || codesRecord.payment_codes.length === 0) {
      return codesRecord;
    }

    const updatedPaymentCodes = await Promise.all(
      codesRecord.payment_codes.map(async (code) => {
        if ((code?.payment_category?.fee_type || code?.fee_type) !== 'Tuition') {
          return code;
        }
        if (code.virtual_route?.account_number || code.has_virtual_route) {
          return code;
        }

        try {
          const res = await axios.post(
            `/api/students/${studentId}/payment-codes/${encodeURIComponent(code.reference_code || code.code)}/virtual-account`,
            {},
            getAuthHeaders()
          );
          return res.data?.payment_code || {
            ...code,
            virtual_route: res.data?.virtual_route || null,
            has_virtual_route: Boolean(res.data?.virtual_route),
          };
        } catch (err) {
          return {
            ...code,
            tracked_transfer_error: err.response?.data?.message || 'Tracked transfer account is not available right now.',
          };
        }
      })
    );

    return {
      ...codesRecord,
      payment_codes: updatedPaymentCodes,
    };
  };

  const handleRecoverReference = async () => {
    const normalizedReference = recoveryReference.trim();
    if (!normalizedReference) {
      setRecoveryResult({
        tone: 'warning',
        message: 'Enter the exact Paystack transaction reference before running recovery.',
      });
      return;
    }

    try {
      setRecoveryLoading(true);
      setRecoveryResult(null);
      const res = await axios.post(
        '/api/finance/paystack/recover-reference',
        { reference: normalizedReference },
        getAuthHeaders()
      );
      const status = res.data?.status || 'recorded';
      const tone = status === 'recorded' || status === 'duplicate' ? 'success' : status === 'unmapped' ? 'warning' : 'info';
      const messageMap = {
        recorded: 'Paystack transaction recovered and recorded successfully.',
        duplicate: 'This Paystack transaction was already recorded earlier.',
        blocked: 'Payment was recovered but is currently blocked pending subscription or verification rules.',
        unmapped: 'Paystack confirmed the transaction, but EduPulse could not map it to a student payment route yet.',
        ignored: 'The transaction did not match this school or did not require finance recovery.',
      };
      setRecoveryResult({
        tone,
        message: messageMap[status] || 'Recovery request completed.',
        reference: res.data?.reference || normalizedReference,
      });
      if (['recorded', 'duplicate', 'blocked'].includes(status)) {
        fetchStudents();
        if (selectedStudent?.id) {
          fetchStudentPayments(selectedStudent.id);
          fetchPaymentCodes(selectedStudent.id);
        }
      }
    } catch (err) {
      const responseData = err.response?.data || {};
      setRecoveryResult({
        tone: 'error',
        message: responseData.message || 'Unable to recover the Paystack transaction right now.',
        reference: responseData.reference || normalizedReference,
      });
    } finally {
      setRecoveryLoading(false);
    }
  };

  const printPaymentInstructions = async () => {
    if (!paymentCodes) return;
    const html = buildPaymentInstructionsHtml(paymentCodes);
    openInstructionPrintWindow(`Payment Instructions & Reference Guide - ${paymentCodes.student_name}`, html);
  };

  const openInstructionPrintWindow = (title, content) => {
    const printWindow = window.open('', '', 'width=900,height=1200');
    if (!printWindow) {
      alert('Unable to open the print window right now. Please allow pop-ups and try again.');
      return;
    }

    const schoolName = branding.school_name || branding.name || 'School';
    const schoolEmail = branding.school_email || branding.email || '';
    const schoolPhone = branding.school_phone || branding.phone || '';
    const schoolAddress = branding.school_address || branding.address || '';
    const themeColor = branding.theme_color || '#3b82f6';

    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>${title}</title>
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
          .page-break {
            break-before: page;
            page-break-before: always;
            height: 0;
          }
          @media print {
            body { background: white; }
            .container { box-shadow: none; }
          }
        </style>
      </head>
      <body>
        ${content}
      </body>
      </html>
    `;

    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => printWindow.print(), 500);
  };

  const buildPaymentInstructionsHtml = (codesRecord) => {
    const trackerPaymentCodes = getTrackerPaymentCodes(codesRecord);
    const schoolName = branding.school_name || branding.name || 'School';
    const schoolMotto = branding.school_motto || branding.motto || '';
    const schoolLogo = branding.logo_url || branding.logo || '';
    const schoolEmail = branding.school_email || branding.email || '';
    const schoolPhone = branding.school_phone || branding.phone || '';
    const schoolAddress = branding.school_address || branding.address || '';
    const themeColor = branding.theme_color || '#3b82f6';
    const totalTrackedAmount = trackerPaymentCodes.reduce((sum, code) => sum + Number(code.virtual_route?.total_amount || code.total_amount || 0), 0);

    return `
      <div class="container">
        <div class="header">
          ${schoolLogo ? `<div style="margin-bottom:12px;"><img src="${schoolLogo}" alt="${schoolName} logo" style="max-height:72px; max-width:96px; object-fit:contain;" /></div>` : ''}
          <div class="school-name">${schoolName}</div>
          ${schoolMotto ? `<div style="font-size:13px; color:${themeColor}; font-style:italic; margin-bottom:6px;">${schoolMotto}</div>` : ''}
          <div class="school-contact">
            ${schoolAddress ? `<div>${schoolAddress}</div>` : ''}
            ${schoolPhone ? `<div>📞 ${schoolPhone}</div>` : ''}
            ${schoolEmail ? `<div>✉️ ${schoolEmail}</div>` : ''}
          </div>
        </div>

        <div class="document-title">📋 Payment Instructions For Parent</div>

        <div class="student-info">
          <p><span class="info-label">Student Name:</span> ${codesRecord.student_name}</p>
          <p><span class="info-label">Stable Payment Identity:</span> <strong>${codesRecord.student_code}</strong></p>
          <p><span class="info-label">Class:</span> ${codesRecord.class || 'Not assigned'}</p>
          ${codesRecord.parent_phone ? `<p><span class="info-label">Parent/Guardian:</span> ${codesRecord.parent_name || ''} (${codesRecord.parent_phone})</p>` : ''}
        </div>

        <div class="section">
          <div class="section-title">💳 Tuition Reference And Tracked Transfer Account</div>
          <table class="payment-codes-table">
            <thead>
              <tr>
                <th>Charge</th>
                <th>Preferred Reference</th>
                <th>Payment Channel</th>
                <th class="amount-column">Amount</th>
              </tr>
            </thead>
            <tbody>
              ${trackerPaymentCodes.map(code => {
                const convenience = getTuitionConvenienceDetails(code, codesRecord);
                return `
                <tr>
                  <td><strong>${code.fee_type}</strong></td>
                  <td><span class="code-column">${code.reference_code || code.code}</span></td>
                  <td><span style="color:#475569;">Use the automatically prepared EduPulse tracked transfer account only</span></td>
                  <td class="amount-column">GH₵ ${Number(code.virtual_route?.total_amount || code.total_amount || 0).toFixed(2)}</td>
                </tr>
                ${convenience.amount > 0 ? `<tr><td colspan="4" style="font-size:12px; color:#475569; padding-top:0;">Convenience fee: ${convenience.percentage.toFixed(2)}% = GH₵ ${convenience.amount.toFixed(2)} added to tuition.</td></tr>` : ''}
              `;
              }).join('')}
            </tbody>
          </table>
        </div>

        <div class="important">
          <strong>⚠️ Important:</strong> Parents should use only the EduPulse tracked transfer account shown for tuition. The school's direct bank account is intentionally excluded from this instruction sheet.
        </div>

        <div class="section">
          <div class="section-title">💰 How to Pay</div>
          ${trackerPaymentCodes.map(code => {
            const convenience = getTuitionConvenienceDetails(code, codesRecord);
            return `
            <div class="payment-method">
              <div class="payment-method-title">${code.fee_type}</div>
              <div class="payment-method-content">
                <p><strong>Preferred Reference:</strong> ${code.reference_code || code.code}</p>
                ${code.virtual_route?.account_number ? `<p><strong>Tracked Transfer Bank:</strong> ${code.virtual_route.bank_name || 'Paystack transfer account'}</p>` : ''}
                ${code.virtual_route?.account_number ? `<p><strong>Tracked Transfer Account Number:</strong> ${code.virtual_route.account_number}</p>` : ''}
                ${code.virtual_route?.account_name ? `<p><strong>Tracked Transfer Account Name:</strong> ${code.virtual_route.account_name}</p>` : ''}
                ${code.virtual_route?.account_number ? `<p><strong>Payment Route:</strong> Pay into this tracked transfer account for tuition.</p>` : `<p><strong>Payment Route:</strong> The school must reconnect Paystack tracked transfer before parents can pay.</p>`}
                <p><strong>School Tuition:</strong> GH₵ ${Number(code.base_amount || 0).toFixed(2)}</p>
                ${convenience.amount > 0 ? `<p><strong>Convenience Fee:</strong> ${convenience.percentage.toFixed(2)}% = GH₵ ${convenience.amount.toFixed(2)}</p>` : ''}
                ${code.virtual_route?.total_amount ? `<p><strong>Transfer Total:</strong> GH₵ ${Number(code.virtual_route.total_amount || 0).toFixed(2)}</p>` : ''}
                <p style="color:#475569;"><strong>Share the reference exactly as shown.</strong> Use it when the school asks for bank narration or office confirmation.</p>
                <p><strong>Amount To Pay:</strong> GH₵ ${Number(code.virtual_route?.total_amount || code.total_amount || 0).toFixed(2)}</p>
                <p><strong>Reference To Present At School Office:</strong> ${code.reference_code || code.code}</p>
                <p style="margin-top: 8px;"><strong>Payment Flow:</strong></p>
                <p style="margin-left: 12px;">1) ${code.virtual_route?.account_number ? 'Use the tracked transfer bank name and account number shown above for tuition.' : 'Ask the school to reconnect the tracked transfer account for tuition.'}</p>
                <p style="margin-left: 12px;">2) ${code.virtual_route?.total_amount ? `Transfer GH₵ ${Number(code.virtual_route.total_amount || 0).toFixed(2)} exactly so EduPulse can match it immediately.` : `Wait for the tracked transfer account to become available before collecting this tuition payment.`}</p>
                <p style="margin-left: 12px;">3) Keep reference <strong>${code.reference_code || code.code}</strong> in the narration or present it at the school office.</p>
                <p style="margin-left: 12px;">4) EduPulse records the tuition payment under this learner and updates the student balance as soon as Paystack confirms it.</p>
                ${code.tracked_transfer_error ? `<p style="margin-top: 8px; color:#b45309;"><strong>Tracked transfer note:</strong> ${code.tracked_transfer_error}</p>` : ''}
              </div>
            </div>
          `;
          }).join('')}
        </div>

        <div class="section">
          <div class="section-title">📊 Amount Summary</div>
          <div class="instructions">
            <div class="instructions-title">Per-Fee Instructions:</div>
            <div class="instruction-text">
              ${trackerPaymentCodes.map(code => {
                const convenience = getTuitionConvenienceDetails(code, codesRecord);
                return `• <strong>${code.fee_type}:</strong> ${code.virtual_route?.account_number ? `Use tracked transfer account ${code.virtual_route.account_number} at ${code.virtual_route.bank_name || 'the listed bank'} and pay GH₵ ${Number(code.virtual_route.total_amount || code.total_amount || 0).toFixed(2)}${convenience.amount > 0 ? ` (includes ${convenience.percentage.toFixed(2)}% convenience fee of GH₵ ${convenience.amount.toFixed(2)})` : ''}` : `Wait for the tracked transfer account before collecting tuition`} for reference <strong>${code.reference_code || code.code}</strong>.`;
              }).join('<br>')}
            </div>
            <div class="instruction-text" style="margin-top: 15px; font-weight: bold; border-top: 1px solid #ddd; padding-top: 10px;">
              Total amount due across these references: GH₵ ${totalTrackedAmount.toFixed(2)}
            </div>
          </div>
        </div>

        <div class="section">
          <div class="section-title">❓ Questions?</div>
          <div class="instructions">
            <div class="instruction-text">
              If you have any questions about the payment reference to use or the school's approved payment channel:
            </div>
            ${schoolPhone ? `<div class="instruction-text">📞 Call: ${schoolPhone}</div>` : ''}
            ${schoolEmail ? `<div class="instruction-text">✉️ Email: ${schoolEmail}</div>` : ''}
            <div class="instruction-text" style="margin-top: 10px;">
              Or visit the school office during office hours.
            </div>
          </div>
        </div>

        <div class="footer">
          <p>Generated on ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</p>
          <p>Please keep this document for your records</p>
        </div>
      </div>
    `;
  };

  const printFilteredPaymentInstructions = async () => {
    const studentsToPrint = filteredStudents.slice(0, 100);
    if (studentsToPrint.length === 0) {
      alert('No students match the current search or class filter.');
      return;
    }

    try {
      setBulkPrintLoading(true);
      const results = await Promise.all(
        studentsToPrint.map(async (student) => {
          try {
            const result = await fetchPaymentCodesData(student.id);
            const printableResult = await ensureTrackedTransferRoutes(student.id, result);
            return { student, result: printableResult };
          } catch (err) {
            return {
              student,
              error: err.response?.data?.message || 'Unable to load payment instructions right now.',
            };
          }
        })
      );

      const printableResults = results.filter(({ result }) => getTrackerPaymentCodes(result).length > 0);
      if (printableResults.length === 0) {
        alert(results.find(({ error }) => error)?.error || 'No tuition payment instructions are available for the current filtered students right now.');
        return;
      }

      const combinedHtml = printableResults
        .map(({ result }, index) => `${index > 0 ? '<div class="page-break"></div>' : ''}${buildPaymentInstructionsHtml(result)}`)
        .join('');

      openInstructionPrintWindow('Bulk Payment Instructions', combinedHtml);

      const failedCount = results.length - printableResults.length;
      if (failedCount > 0) {
        alert(`Printed ${printableResults.length} instruction sheet${printableResults.length === 1 ? '' : 's'}. ${failedCount} student${failedCount === 1 ? '' : 's'} could not be prepared right now.`);
      }
    } finally {
      setBulkPrintLoading(false);
    }
  };

  const printPaymentReceipt = (student, payment, feeTypeSummary) => {
    if (!student || !payment) return;

    const schoolName = branding.school_name || branding.name || 'School';
    const schoolMotto = branding.school_motto || branding.motto || '';
    const schoolLogo = branding.logo_url || branding.logo || '';
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
            ${schoolLogo ? `<div style="margin-bottom:12px;"><img src="${schoolLogo}" alt="${schoolName} logo" style="max-height:72px; max-width:96px; object-fit:contain;" /></div>` : ''}
            <div class="school-name">${schoolName}</div>
            ${schoolMotto ? `<div style="font-size:13px; color:${themeColor}; font-style:italic; margin-bottom:6px;">${schoolMotto}</div>` : ''}
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
      requiredAmount = schoolFees.tuition_fee;
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
    
    const feeTypes = ['Tuition'];
    const paymentStatus = feeTypes.map(type => calculatePaymentSummary(student, type));

    if (filterStatus === 'paid') {
      return paymentStatus.some(p => p.isPaid);
    } else if (filterStatus === 'pending') {
      return paymentStatus.some(p => p.isPending);
    }
    
    return true;
  });

  const feeTypes = ['Tuition'];
  const trackerPaymentCodes = getTrackerPaymentCodes(paymentCodes);

  const getFeeTypeLabel = (feeType) => {
    return feeType;
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
        <button
          onClick={printFilteredPaymentInstructions}
          disabled={bulkPrintLoading || filteredStudents.length === 0}
          className="px-4 py-2 bg-slate-800 text-white rounded-lg text-sm font-bold hover:bg-slate-900 transition-colors disabled:bg-slate-300"
        >
          {bulkPrintLoading ? 'Preparing Batch Print...' : `🖨️ Print ${Math.min(filteredStudents.length, 100)} Filtered Instruction${Math.min(filteredStudents.length, 100) === 1 ? '' : 's'}`}
        </button>
      </div>

      <div className="mb-6 rounded-2xl border border-cyan-200 bg-cyan-50 p-4 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs font-black uppercase tracking-[0.22em] text-cyan-700">Paystack Reconciliation</p>
            <h3 className="mt-2 text-lg font-black text-slate-900">Recover a successful tracked transfer by exact reference</h3>
            <p className="mt-2 text-sm leading-6 text-slate-700">
              Use this when Paystack shows a successful transfer but the student payment has not appeared yet in EduPulse. This runs the backend recovery flow without bringing back the old reconciliation dashboard card.
            </p>
          </div>
          <div className="w-full max-w-xl">
            <label htmlFor="paystack-recovery-reference" className="mb-2 block text-xs font-bold uppercase tracking-[0.18em] text-cyan-800">
              Transaction Reference
            </label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                id="paystack-recovery-reference"
                type="text"
                value={recoveryReference}
                onChange={(event) => setRecoveryReference(event.target.value)}
                placeholder="e.g. 6a9d6f5523744a1df06a6143"
                className="flex-1 rounded-xl border border-cyan-200 bg-white px-4 py-3 text-sm text-slate-800 shadow-sm outline-none transition focus:border-cyan-400"
              />
              <button
                onClick={handleRecoverReference}
                disabled={recoveryLoading}
                className="rounded-xl bg-cyan-700 px-4 py-3 text-sm font-bold text-white transition hover:bg-cyan-800 disabled:cursor-not-allowed disabled:bg-cyan-300"
              >
                {recoveryLoading ? 'Recovering...' : 'Recover Paystack Payment'}
              </button>
            </div>
            {recoveryResult ? (
              <div className={`mt-3 rounded-xl border px-3 py-3 text-sm ${
                recoveryResult.tone === 'success'
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                  : recoveryResult.tone === 'warning'
                    ? 'border-amber-200 bg-amber-50 text-amber-900'
                    : recoveryResult.tone === 'error'
                      ? 'border-rose-200 bg-rose-50 text-rose-900'
                      : 'border-slate-200 bg-white text-slate-800'
              }`}>
                <p className="font-semibold">{recoveryResult.message}</p>
                {recoveryResult.reference ? <p className="mt-1 text-xs opacity-80">Reference: {recoveryResult.reference}</p> : null}
              </div>
            ) : null}
          </div>
        </div>
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
      <p className="mb-6 text-xs text-slate-500">
        Batch print uses the current search and class filter and prepares up to the first 100 matching students at once.
      </p>

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

              {paymentCodes && trackerPaymentCodes.length > 0 && (
                <div className="bg-amber-50 border-l-4 border-l-amber-600 p-4 rounded-lg">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-bold text-amber-900 flex items-center gap-2">
                      📋 Payment Instructions to Share with Parent
                    </h4>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          const codesText = trackerPaymentCodes
                            .map(c => {
                              const virtualRoute = c.virtual_route;
                              const convenience = getTuitionConvenienceDetails(c, paymentCodes);
                              if (virtualRoute?.account_number) {
                                return `${c.fee_type}: Ref ${c.reference_code || c.code} | Tracked transfer bank: ${virtualRoute.bank_name || 'Paystack transfer account'} | Account: ${virtualRoute.account_number} | School tuition GH₵ ${Number(c.base_amount || 0).toFixed(2)}${convenience.amount > 0 ? ` | Convenience fee ${convenience.percentage.toFixed(2)}% = GH₵ ${convenience.amount.toFixed(2)}` : ''} | Transfer total GH₵ ${Number(virtualRoute.total_amount || c.base_amount || 0).toFixed(2)}`;
                              }
                              return `${c.fee_type}: Ref ${c.reference_code || c.code} | Tracked transfer account is temporarily unavailable. Reconnect Paystack settlement in system settings before sharing this instruction.`;
                            })
                            .join('\n');
                          const instructions = `Payment Instructions for ${paymentCodes.student_name}\n\nStable Payment Identity: ${paymentCodes.student_code}\n\n${codesText}\n\nHow to pay:\n1. Use the EduPulse tracked transfer account shown for tuition.\n2. Pay the exact tracked total with the exact tuition reference.\n3. Keep the same reference when sharing proof at the school office.`;
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
                    {paymentCodes.fees_configuration?.terminal_report_fee > 0 ? (
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
                        <p className="font-semibold text-slate-800">Separate report-card fee</p>
                        <p className="mt-1">Report-card printing remains configured separately at GH₵ {Number(paymentCodes.fees_configuration.terminal_report_fee || 0).toFixed(2)} and is no longer merged into tuition tracking.</p>
                      </div>
                    ) : null}
                    {paymentCodes.payment_identity?.tracked_transfer_readiness_note ? (
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
                        <p className="font-semibold text-slate-800">Tracked transfer account setup</p>
                        <p className="mt-1">{paymentCodes.payment_identity.tracked_transfer_readiness_note}</p>
                      </div>
                    ) : null}
                    {trackerPaymentCodes.map((code, idx) => (
                      (() => {
                        const referenceKey = code.reference_code || code.code;
                        const virtualRoute = code.virtual_route;
                        const convenience = getTuitionConvenienceDetails(code, paymentCodes);
                        return (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-3 bg-white rounded border border-amber-200 text-sm"
                      >
                        <div className="flex-1">
                          <p className="font-semibold text-slate-800">{code.fee_type}</p>
                          <p className="text-xs text-slate-600">School tuition: GH₵ {Number(code.base_amount || 0).toFixed(2)}</p>
                          {convenience.amount > 0 ? (
                            <p className="text-xs text-slate-600">Convenience fee: {convenience.percentage.toFixed(2)}% = GH₵ {convenience.amount.toFixed(2)}</p>
                          ) : null}
                          <p className="text-xs font-semibold text-slate-700">Preferred Ref: {code.reference_code || code.code}</p>
                          <p className="text-xs text-slate-700">Parents should use the automatically prepared tracked transfer account so EduPulse records the learner and purpose immediately.</p>

                          <p className="text-xs text-slate-600">Reference: {code.reference_code || code.code}</p>
                          {virtualRoute ? (
                            <div className="mt-2 rounded-lg border border-cyan-200 bg-cyan-50 p-2 text-xs text-cyan-900">
                              <p className="font-semibold">Tracked transfer account ready</p>
                              <p className="mt-1">Bank: {virtualRoute.bank_name || 'Paystack transfer account'}</p>
                              <p>Account number: {virtualRoute.account_number}</p>
                              {virtualRoute.account_name ? <p>Account name: {virtualRoute.account_name}</p> : null}
                              <p className="mt-1">School tuition: GH₵ {Number(virtualRoute.base_amount || 0).toFixed(2)}</p>
                              {convenience.amount > 0 ? (
                                <p>Convenience fee: {convenience.percentage.toFixed(2)}% = GH₵ {convenience.amount.toFixed(2)}</p>
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
                          {virtualRoute?.account_number ? null : (
                            <span className="rounded bg-amber-100 px-2 py-2 text-xs font-semibold text-amber-900">
                              Paystack setup needed
                            </span>
                          )}
                        </div>
                      </div>
                        );
                      })()
                    ))}
                  </div>
                  <p className="text-xs text-amber-800 mt-3 italic">
                    💬 Preferred instruction: "Use the EduPulse tracked transfer account for reference <strong>{trackerPaymentCodes[0]?.reference_code || trackerPaymentCodes[0]?.code || 'S001-T1'}</strong> and pay the exact tracked total shown there." 
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
