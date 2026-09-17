import React, { useState, useEffect } from 'react';
import axios from 'axios';
import TimetableManager from './TimetableManager';
import TermManagementPanel from './TermManagementPanel';
import reportTemplates from '../report_templates';
import { buildTemplateHtml, GRADE_SCALE_ROWS, formatGradingSchemeSummary, getGradeFromTotal, getRemarkFromGrade } from '../utils/reportTemplate';

const TEMPLATE_ALIAS_TO_CANONICAL = {
  sample1: 'gradman_v1',
  sample2: 'parent_focus',
  sample3: 'progress_insights',
  sample4: 'compact_clear',
  sample5: 'guardian_narrative',
  sample6: 'classic_traditional'
};

const TEMPLATE_CANONICAL_TO_ALIAS = Object.fromEntries(
  Object.entries(TEMPLATE_ALIAS_TO_CANONICAL).map(([alias, canonical]) => [canonical, alias])
);

const PREVIEW_TEMPLATE_THEMES = {
  default: {
    modalCanvas: 'bg-white p-8 shadow-lg',
    sectionGap: 'space-y-5',
    headerWrap: 'mb-2 rounded-3xl bg-linear-to-r from-emerald-600 via-teal-600 to-sky-600 px-6 pb-5 pt-4 text-white shadow-lg',
    logoShell: 'bg-white/20 text-white',
    titleClass: 'text-3xl font-black uppercase tracking-tight text-white',
    mottoClass: 'mt-1 text-sm italic text-emerald-100',
    contactClass: 'mt-2 text-xs text-emerald-100',
    studentCard: 'grid grid-cols-2 gap-4 rounded-3xl border border-emerald-100 bg-white p-5 text-xs text-slate-800 shadow-sm',
    academicTitleClass: 'text-xl font-black uppercase text-slate-900',
    academicMetaClass: 'text-sm text-slate-600',
    summaryCard: 'rounded-3xl border border-slate-200 bg-white p-4 text-slate-800 shadow-sm',
    summaryTitle: 'mb-3 border-b border-slate-200 pb-1 font-bold uppercase tracking-wide text-emerald-700',
    summaryLabel: 'font-bold text-slate-700',
    summaryValue: 'font-bold text-slate-900',
    tableTitle: 'mb-2 border-b border-slate-200 pb-1 font-bold uppercase tracking-wide text-sky-700',
    tableHead: 'bg-slate-100 text-slate-700',
    tableRow: 'border-b border-slate-200 text-slate-700',
    tableGrade: 'font-bold text-emerald-700',
    tableTotal: 'font-bold text-slate-900',
    scaleHead: 'bg-slate-100 text-slate-700',
    scaleText: 'text-slate-700',
    insightWrap: 'rounded-3xl border border-slate-200 bg-white p-4 shadow-sm',
    insightTitle: 'mb-3 border-b border-slate-200 pb-1 font-bold uppercase tracking-wide text-violet-700',
    insightCard: 'rounded-2xl bg-slate-50 p-3',
    insightLabel: 'mb-1 text-xs font-bold uppercase tracking-wide text-violet-700',
    insightText: 'text-sm text-slate-700',
    signatureWrap: 'mt-8 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm',
    signatureLine: 'mt-8 border-t border-slate-400 pt-1',
    signatureText: 'text-xs font-bold text-slate-700',
    genericCard: 'rounded-3xl border border-slate-200 bg-white p-4 shadow-sm',
    genericTitle: 'mb-2 text-sm font-bold uppercase tracking-wide text-slate-700',
    genericText: 'grid grid-cols-1 gap-2 text-xs text-slate-600 md:grid-cols-2',
    genericLabel: 'font-semibold text-slate-700',
    remarkTones: {
      teacher_remarks: 'rounded-3xl border border-emerald-200 bg-white p-4',
      headmaster_remarks: 'rounded-3xl border border-lime-200 bg-lime-50 p-4',
      proprietor_remarks: 'rounded-3xl border border-teal-200 bg-teal-50 p-4',
      ai_analysis: 'rounded-3xl border border-sky-200 bg-sky-50 p-4',
      default: 'rounded-3xl border border-emerald-200 bg-white p-4'
    }
  },
  progress_insights: {
    modalCanvas: 'bg-slate-900 p-8 shadow-lg',
    sectionGap: 'space-y-5',
    headerWrap: 'mb-2 rounded-3xl bg-linear-to-r from-violet-600 via-indigo-600 to-sky-600 px-6 pb-5 pt-4 text-white shadow-lg',
    logoShell: 'bg-white/20 text-white',
    titleClass: 'text-3xl font-black uppercase tracking-tight text-white',
    mottoClass: 'mt-1 text-sm italic text-blue-100',
    contactClass: 'mt-2 text-xs text-blue-100',
    studentCard: 'grid grid-cols-2 gap-4 rounded-3xl bg-slate-800 p-5 text-xs text-slate-100 shadow-lg',
    academicTitleClass: 'text-xl font-black uppercase text-white',
    academicMetaClass: 'text-sm text-blue-100',
    summaryCard: 'rounded-3xl border border-white/10 bg-slate-800 p-4 text-slate-100',
    summaryTitle: 'mb-3 border-b border-white/10 pb-1 font-bold uppercase tracking-wide text-sky-300',
    summaryLabel: 'font-bold text-sky-200',
    summaryValue: 'font-bold text-white',
    tableTitle: 'mb-2 border-b border-white/10 pb-1 font-bold uppercase tracking-wide text-violet-200',
    tableHead: 'bg-slate-800 text-sky-100',
    tableRow: 'border-b border-white/10 text-slate-100',
    tableGrade: 'font-bold text-lime-300',
    tableTotal: 'font-bold text-white',
    scaleHead: 'bg-slate-800 text-sky-100',
    scaleText: 'text-slate-100',
    insightWrap: 'rounded-3xl border border-white/10 bg-slate-800 p-4',
    insightTitle: 'mb-3 border-b border-white/10 pb-1 font-bold uppercase tracking-wide text-violet-200',
    insightCard: 'rounded-2xl bg-slate-700 p-3',
    insightLabel: 'mb-1 text-xs font-bold uppercase tracking-wide text-fuchsia-200',
    insightText: 'text-sm text-slate-100',
    signatureWrap: 'mt-8 rounded-3xl border border-white/10 bg-slate-800 p-4',
    signatureLine: 'mt-8 border-t border-slate-500 pt-1',
    signatureText: 'text-xs font-bold text-sky-100',
    genericCard: 'rounded-3xl border border-white/10 bg-slate-800 p-4',
    genericTitle: 'mb-2 text-sm font-bold uppercase tracking-wide text-sky-300',
    genericText: 'grid grid-cols-1 gap-2 text-xs text-slate-200 md:grid-cols-2',
    genericLabel: 'font-semibold text-sky-100',
    remarkTones: {
      teacher_remarks: 'rounded-3xl border border-yellow-400/30 bg-yellow-400/10 p-4',
      headmaster_remarks: 'rounded-3xl border border-orange-400/30 bg-orange-400/10 p-4',
      proprietor_remarks: 'rounded-3xl border border-cyan-400/30 bg-cyan-400/10 p-4',
      ai_analysis: 'rounded-3xl border border-violet-400/30 bg-violet-400/10 p-4',
      default: 'rounded-3xl border border-white/10 bg-slate-800 p-4'
    }
  },
  compact_clear: {
    modalCanvas: 'bg-white p-6 shadow-lg',
    sectionGap: 'space-y-3',
    headerWrap: 'mb-1 border-b border-slate-300 pb-3 text-left',
    logoShell: 'bg-slate-200 text-slate-700',
    titleClass: 'text-2xl font-bold uppercase tracking-tight text-slate-900',
    mottoClass: 'mt-1 text-xs italic text-slate-500',
    contactClass: 'mt-2 text-[11px] text-slate-500',
    studentCard: 'grid grid-cols-2 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px]',
    academicTitleClass: 'text-lg font-bold uppercase text-slate-900',
    academicMetaClass: 'text-xs text-slate-500',
    summaryCard: 'rounded-lg border border-slate-200 bg-white p-3',
    summaryTitle: 'mb-2 border-b border-slate-200 pb-1 text-sm font-bold uppercase tracking-wide text-slate-700',
    summaryLabel: 'font-semibold text-slate-700',
    summaryValue: 'font-bold text-slate-900',
    tableTitle: 'mb-1 text-sm font-bold uppercase tracking-wide text-slate-700',
    tableHead: 'bg-slate-100',
    tableRow: 'border-b border-slate-200',
    tableGrade: 'font-bold text-slate-800',
    tableTotal: 'font-bold text-slate-900',
    scaleHead: 'bg-slate-100',
    scaleText: 'text-slate-700',
    insightWrap: 'rounded-lg border border-slate-200 bg-white p-3',
    insightTitle: 'mb-2 border-b border-slate-200 pb-1 text-sm font-bold uppercase tracking-wide text-slate-700',
    insightCard: 'rounded border border-slate-200 bg-slate-50 p-3',
    insightLabel: 'mb-1 text-[11px] font-bold uppercase tracking-wide text-slate-500',
    insightText: 'text-sm text-slate-700',
    signatureWrap: 'mt-6 border-t border-slate-200 pt-3',
    signatureLine: 'mt-6 border-t border-slate-400 pt-1',
    signatureText: 'text-[11px] font-bold text-slate-700',
    genericCard: 'rounded-lg border border-slate-200 p-3',
    genericTitle: 'mb-2 text-sm font-bold uppercase tracking-wide text-slate-700',
    genericText: 'grid grid-cols-1 gap-2 text-xs text-slate-600 md:grid-cols-2',
    genericLabel: 'font-semibold text-slate-700',
    remarkTones: {
      teacher_remarks: 'rounded-lg border-l-2 border-slate-400 bg-slate-50 p-3',
      headmaster_remarks: 'rounded-lg border-l-2 border-slate-500 bg-slate-50 p-3',
      proprietor_remarks: 'rounded-lg border-l-2 border-slate-600 bg-slate-50 p-3',
      ai_analysis: 'rounded-lg border-l-2 border-slate-700 bg-slate-50 p-3',
      default: 'rounded-lg border-l-2 border-slate-400 bg-slate-50 p-3'
    }
  },
  guardian_narrative: {
    modalCanvas: 'bg-rose-50 p-8 shadow-lg',
    sectionGap: 'space-y-5',
    headerWrap: 'mb-2 rounded-[28px] border border-rose-200 bg-white px-6 pb-5 pt-4 text-center shadow-sm',
    logoShell: 'bg-rose-100 text-rose-700',
    titleClass: 'text-3xl font-black uppercase tracking-tight text-rose-900',
    mottoClass: 'mt-1 text-sm italic text-rose-700',
    contactClass: 'mt-2 text-xs text-rose-700',
    studentCard: 'grid grid-cols-2 gap-4 rounded-[28px] border border-rose-200 bg-white p-5 text-xs shadow-sm',
    academicTitleClass: 'text-xl font-black uppercase text-rose-900',
    academicMetaClass: 'text-sm text-rose-700',
    summaryCard: 'rounded-[28px] border border-rose-200 bg-white p-4 shadow-sm',
    summaryTitle: 'mb-3 border-b border-rose-100 pb-1 font-bold text-rose-900',
    summaryLabel: 'font-bold text-rose-900',
    summaryValue: 'font-bold text-slate-900',
    tableTitle: 'mb-2 border-b border-rose-100 pb-1 font-bold text-rose-900',
    tableHead: 'bg-rose-100',
    tableRow: 'border-b border-rose-100',
    tableGrade: 'font-bold text-rose-700',
    tableTotal: 'font-bold text-slate-900',
    scaleHead: 'bg-white',
    scaleText: 'text-rose-900',
    insightWrap: 'rounded-[28px] border border-rose-200 bg-white p-4 shadow-sm',
    insightTitle: 'mb-3 border-b border-rose-100 pb-1 font-bold text-rose-900',
    insightCard: 'rounded-2xl bg-rose-50 p-3',
    insightLabel: 'mb-1 text-xs font-bold uppercase tracking-wide text-rose-700',
    insightText: 'text-sm text-slate-700',
    signatureWrap: 'mt-8 rounded-[28px] border border-rose-200 bg-white p-4 shadow-sm',
    signatureLine: 'mt-8 border-t border-rose-300 pt-1',
    signatureText: 'text-xs font-bold text-rose-900',
    genericCard: 'rounded-[28px] border border-rose-200 bg-white p-4 shadow-sm',
    genericTitle: 'mb-2 text-sm font-bold text-rose-900',
    genericText: 'grid grid-cols-1 gap-2 text-xs text-slate-600 md:grid-cols-2',
    genericLabel: 'font-semibold text-rose-900',
    remarkTones: {
      teacher_remarks: 'rounded-[28px] border border-yellow-200 bg-yellow-50 p-4',
      headmaster_remarks: 'rounded-[28px] border border-orange-200 bg-orange-50 p-4',
      proprietor_remarks: 'rounded-[28px] border border-cyan-200 bg-cyan-50 p-4',
      ai_analysis: 'rounded-[28px] border border-rose-200 bg-rose-100 p-4',
      default: 'rounded-[28px] border border-rose-200 bg-white p-4'
    }
  }
};

const TEMPLATE_HISTORY_ACTION_LABELS = {
  activate: 'Activated',
  upload: 'Uploaded',
  restore: 'Restored',
};

function buildTemplateHistoryPreview(activeTemplateId, activeTemplateConfig, snapshot) {
  if (!snapshot) {
    return [];
  }

  const rows = [];
  const currentConfig = activeTemplateConfig || {};
  const currentTemplateId = TEMPLATE_ALIAS_TO_CANONICAL[activeTemplateId] || activeTemplateId || '';

  if ((snapshot.report_template_id || '') !== currentTemplateId) {
    rows.push(`Template: ${snapshot.report_template_id || 'None'} instead of ${currentTemplateId || 'None'}.`);
  }

  const booleanComparisons = [
    ['Custom HTML', snapshot.has_custom_html, Boolean(currentConfig.html)],
    ['Custom CSS', snapshot.has_custom_css, Boolean(currentConfig.css)],
    ['Background image', snapshot.has_background_image, Boolean(currentConfig.background_image_url)],
  ];

  booleanComparisons.forEach(([label, snapshotValue, currentValue]) => {
    if (Boolean(snapshotValue) !== Boolean(currentValue)) {
      rows.push(`${label}: ${snapshotValue ? 'Enabled' : 'Disabled'} instead of ${currentValue ? 'Enabled' : 'Disabled'}.`);
    }
  });

  const snapshotConfigCount = Number(snapshot.config_key_count || 0);
  const currentConfigCount = Object.keys(currentConfig || {}).length;
  if (snapshotConfigCount !== currentConfigCount) {
    rows.push(`Config keys: ${snapshotConfigCount} instead of ${currentConfigCount}.`);
  }

  return rows;
}

export default function SettingsPanel() {
  const [settings, setSettings] = useState({
    school_name: '',
    school_motto: '',
    logo_url: '',
    primary_color: '#1e3a8a',
    school_email: '',
    school_phone: '',
    school_address: '',
    school_website: '',
    bank_name: '',
    bank_account: '',
    bank_account_name: '',
    bank_branch: '',
    paystack_subaccount_code: '',
    paystack_bank_code: '',
    paystack_resolved_account_name: '',
    country_code: 'GH',
    anniversary_date: '',
    next_term_reopen_date: '',
    ai_registrar_enabled: false,
    admissions_visit_location_default: '',
    admissions_visit_contact_person_default: '',
    admissions_visit_contact_phone_default: '',
    approval_pdf_enabled: false,
    approval_pdf_delivery_mode: 'email_link',
    approval_pdf_include_payment_summary: true,
    approval_pdf_include_required_items: true,
    approval_pdf_required_items: '',
  });
  const [fees, setFees] = useState({
    tuition_fee: 0,
    tuition_convenience_fee_percentage: 1.95,
    feeding_fee: 0,
    feeding_daily_fee: 0,
    feeding_weekly_fee: 0,
    feeding_monthly_fee: 0,
    transport_fee: 0,
    terminal_report_fee: 0,
    admission_fee_enabled: false,
    admission_fee_amount: 0,
    other_fees: {}
  });
  const [otherFeeInput, setOtherFeeInput] = useState('');
  const [otherFeeAmount, setOtherFeeAmount] = useState('');
  const [classScoreMax, setClassScoreMax] = useState(30);
  const [examScoreMax, setExamScoreMax] = useState(70);
  const [gradingSchemeStatus, setGradingSchemeStatus] = useState('');
  const [logoUploadError, setLogoUploadError] = useState('');
  const [previewTemplate, setPreviewTemplate] = useState(null);
  const [showTemplatePreview, setShowTemplatePreview] = useState(false);
  const [activeTemplate, setActiveTemplate] = useState('sample1');
  const [activeTemplateConfig, setActiveTemplateConfig] = useState({});
  const [templateMessage, setTemplateMessage] = useState('');
  const [templateHistory, setTemplateHistory] = useState([]);
  const [templateHistoryBusyId, setTemplateHistoryBusyId] = useState('');
  const [selectedTemplateHistorySnapshotId, setSelectedTemplateHistorySnapshotId] = useState('');
  const [customTemplateUpload, setCustomTemplateUpload] = useState({
    templateName: '',
    htmlFile: null,
    cssFile: null,
    backgroundImage: null
  });
  const [uploadingTemplate, setUploadingTemplate] = useState(false);
  const [subscriptionPlan, setSubscriptionPlan] = useState('');
  const [subscriptionTrial, setSubscriptionTrial] = useState({ active: false, plan: '', end_date: null });
  const [bankDetailsVisible, setBankDetailsVisible] = useState(false);
  const [isReconnectingPaystackSettlement, setIsReconnectingPaystackSettlement] = useState(false);

  const [maskedBankSnapshot, setMaskedBankSnapshot] = useState({
    bank_name: '',
    bank_account: '',
    bank_account_name: '',
    bank_branch: ''
  });
  const [savedBankSnapshot, setSavedBankSnapshot] = useState({
    bank_name: '',
    bank_account: '',
    bank_account_name: '',
    bank_branch: ''
  });

  const normalizeBankField = (value = '') => (typeof value === 'string' ? value.trim() : '');
  const isMaskedBankValue = (value = '') => typeof value === 'string' && value.includes('***');
  const getComparableBankValue = (fieldName) => {
    const currentValue = settings[fieldName] || '';
    if (!bankDetailsVisible && isMaskedBankValue(currentValue)) {
      return normalizeBankField(savedBankSnapshot[fieldName] || '');
    }
    return normalizeBankField(currentValue);
  };
  const bankDetailsChangedSinceLastSave = ['bank_name', 'bank_account', 'bank_account_name', 'bank_branch'].some(
    (fieldName) => getComparableBankValue(fieldName) !== normalizeBankField(savedBankSnapshot[fieldName] || '')
  );

  const bankDetailsReadyForProvisioning = Boolean(
    getComparableBankValue('bank_name')
      && getComparableBankValue('bank_account')
      && getComparableBankValue('bank_account_name')
  );

  const paystackProvisioningState = settings.paystack_subaccount_code
    ? {
        tone: 'border-emerald-200 bg-emerald-50 text-emerald-900',
        label: 'Connected',
        message: 'EduPulse has already connected the Paystack settlement account needed for tracked transfer payments.',
      }
    : bankDetailsChangedSinceLastSave && bankDetailsReadyForProvisioning
      ? {
          tone: 'border-amber-200 bg-amber-50 text-amber-900',
          label: 'Save Needed',
          message: 'These bank details are not saved yet. Use Save and Connect Settlement Account so EduPulse can store them first and complete tracked transfer setup.',
        }
    : bankDetailsReadyForProvisioning
      ? {
          tone: 'border-amber-200 bg-amber-50 text-amber-900',
          label: 'Connection Needed',
          message: 'Bank details are saved, but EduPulse has not connected the Paystack settlement account yet. Save settings to complete tracked transfer setup.',
        }
      : {
          tone: 'border-slate-200 bg-slate-50 text-slate-700',
          label: 'Bank Details Needed',
          message: 'Enter the bank name, account number, and account holder name so EduPulse can connect tracked transfer settlement for this school.',
        };

  // Color palette options for easy tenant selection
  const colorPalette = [
    { name: 'Navy Blue', hex: '#1e3a8a' },
    { name: 'Royal Blue', hex: '#2563eb' },
    { name: 'Sky Blue', hex: '#0ea5e9' },
    { name: 'Teal', hex: '#0d9488' },
    { name: 'Green', hex: '#16a34a' },
    { name: 'Emerald', hex: '#059669' },
    { name: 'Purple', hex: '#7c3aed' },
    { name: 'Violet', hex: '#a855f7' },
    { name: 'Pink', hex: '#ec4899' },
    { name: 'Rose', hex: '#e11d48' },
    { name: 'Red', hex: '#dc2626' },
    { name: 'Orange', hex: '#ea580c' },
    { name: 'Amber', hex: '#d97706' },
    { name: 'Slate Grey', hex: '#475569' },
    { name: 'Dark Grey', hex: '#374151' },
    { name: 'Charcoal', hex: '#1f2937' }
  ];

  const safeJsonParse = (rawValue, fallback) => {
    try {
      if (rawValue === null || rawValue === undefined || rawValue === '' || rawValue === 'undefined') {
        return fallback;
      }
      return JSON.parse(rawValue);
    } catch (err) {
      return fallback;
    }
  };

  const normalizeOtherFees = (rawFees) => {
    if (!rawFees || typeof rawFees !== 'object' || Array.isArray(rawFees)) {
      return {};
    }

    return Object.entries(rawFees).reduce((result, [feeName, amount]) => {
      const numericAmount = Number(amount);
      if (!Number.isFinite(numericAmount)) {
        return result;
      }
      result[feeName] = numericAmount;
      return result;
    }, {});
  };

  const normalizeFeeNumber = (value, fallback = 0) => {
    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? numericValue : fallback;
  };

  const tuitionFee = normalizeFeeNumber(fees.tuition_fee);
  const tuitionConvenienceFeePercentage = normalizeFeeNumber(fees.tuition_convenience_fee_percentage, 1.95);
  const feedingDailyFee = normalizeFeeNumber(fees.feeding_daily_fee);
  const feedingWeeklyFee = normalizeFeeNumber(fees.feeding_weekly_fee);
  const feedingMonthlyFee = normalizeFeeNumber(fees.feeding_monthly_fee);
  const transportFee = normalizeFeeNumber(fees.transport_fee);
  const admissionFeeAmount = normalizeFeeNumber(fees.admission_fee_amount);
  const tuitionConvenienceAmount = Number(((tuitionFee * tuitionConvenienceFeePercentage) / 100).toFixed(2));
  const tuitionTransferTotal = Number((tuitionFee + tuitionConvenienceAmount).toFixed(2));

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id')
  });

  const loadSchoolSettings = async () => {
    try {
      const res = await axios.get('/api/school/settings', { headers: getAuthHeaders() });
      const data = res.data || {};

      setSettings((prev) => ({
        ...prev,
        school_name: data.name || prev.school_name,
        school_motto: data.motto || prev.school_motto,
        logo_url: data.logo_url || prev.logo_url,
        primary_color: data.primary_color || prev.primary_color,
        school_email: data.school_email || prev.school_email,
        school_phone: data.school_phone || prev.school_phone,
        school_address: data.school_address || prev.school_address,
        school_website: data.school_website || prev.school_website,
        bank_name: data.bank_name || '',
        bank_account: data.bank_account || '',
        bank_account_name: data.bank_account_name || '',
        bank_branch: data.bank_branch || '',
        paystack_subaccount_code: data.paystack_subaccount_code || '',
        paystack_bank_code: data.paystack_bank_code || '',
        paystack_resolved_account_name: data.paystack_resolved_account_name || '',
        country_code: data.country_code || prev.country_code,
        anniversary_date: data.anniversary_date || prev.anniversary_date,
        next_term_reopen_date: data.next_term_reopen_date || '',
        ai_registrar_enabled: Boolean(data.ai_registrar_enabled ?? data.ai_registrar_addon_enabled),
        admissions_visit_location_default: data.admissions_visit_location_default || '',
        admissions_visit_contact_person_default: data.admissions_visit_contact_person_default || '',
        admissions_visit_contact_phone_default: data.admissions_visit_contact_phone_default || '',
        approval_pdf_enabled: Boolean(data.approval_pdf_enabled),
        approval_pdf_delivery_mode: data.approval_pdf_delivery_mode || 'email_link',
        approval_pdf_include_payment_summary: data.approval_pdf_include_payment_summary !== false,
        approval_pdf_include_required_items: data.approval_pdf_include_required_items !== false,
        approval_pdf_required_items: data.approval_pdf_required_items || '',
      }));

      const nextMaskedBankSnapshot = {
        bank_name: data.bank_name || '',
        bank_account: data.bank_account || '',
        bank_account_name: data.bank_account_name || '',
        bank_branch: data.bank_branch || ''
      };
      setMaskedBankSnapshot(nextMaskedBankSnapshot);
      setSavedBankSnapshot({
        bank_name: isMaskedBankValue(nextMaskedBankSnapshot.bank_name) ? '' : nextMaskedBankSnapshot.bank_name,
        bank_account: isMaskedBankValue(nextMaskedBankSnapshot.bank_account) ? '' : nextMaskedBankSnapshot.bank_account,
        bank_account_name: isMaskedBankValue(nextMaskedBankSnapshot.bank_account_name) ? '' : nextMaskedBankSnapshot.bank_account_name,
        bank_branch: isMaskedBankValue(nextMaskedBankSnapshot.bank_branch) ? '' : nextMaskedBankSnapshot.bank_branch,
      });
      setBankDetailsVisible(false);
    } catch (err) {
      console.error('Failed to load school settings:', err);
    }
  };

  useEffect(() => {
    const branding = safeJsonParse(localStorage.getItem('branding'), {});
    setSettings((prev) => ({
      ...prev,
      school_name: branding.name || prev.school_name || '',
      school_motto: branding.motto || prev.school_motto || '',
      logo_url: branding.logo || prev.logo_url || '',
      primary_color: branding.theme_color || prev.primary_color || '#1e3a8a',
      school_email: branding.email || prev.school_email || '',
      school_phone: branding.phone || prev.school_phone || '',
      school_address: branding.address || prev.school_address || '',
      school_website: branding.website || prev.school_website || '',
      country_code: branding.country_code || prev.country_code || 'GH',
      anniversary_date: branding.anniversary_date || prev.anniversary_date || '',
      next_term_reopen_date: prev.next_term_reopen_date || ''
    }));

    // Get subscription plan from backend to ensure it's always up-to-date
    const fetchSubscriptionPlan = async () => {
      try {
        const res = await axios.get('/api/school/subscription/effective-plan', { headers: getAuthHeaders() });
        const planFromServer = res.data.effective_plan || res.data.plan || localStorage.getItem('subscription_plan') || 'Free Tier';
        setSubscriptionPlan(planFromServer);
        setSubscriptionTrial(res.data.trial || { active: false, plan: '', end_date: null });
        // Update localStorage with latest plan
        localStorage.setItem('subscription_plan', planFromServer);
      } catch (err) {
        console.error('Failed to load subscription plan:', err);
        // Fallback to localStorage
        const plan = localStorage.getItem('subscription_plan') || 'Free Tier';
        setSubscriptionPlan(plan);
        setSubscriptionTrial({ active: false, plan: '', end_date: null });
      }
    };
    
    fetchSubscriptionPlan();


    const fetchGradingScheme = async () => {
      try {
        const headers = {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'X-School-ID': localStorage.getItem('school_id')
        };
        const res = await axios.get('/api/school/grading-scheme', { headers });
        setClassScoreMax(res.data.class_score_max);
        setExamScoreMax(res.data.exam_score_max);
      } catch (err) {
        console.error('Failed to load grading scheme');
      }
    };


    const fetchFees = async () => {
      try {
        const headers = {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'X-School-ID': localStorage.getItem('school_id')
        };
        const res = await axios.get('/api/school/fees', { headers });
        setFees({
          tuition_fee: normalizeFeeNumber(res.data.tuition_fee),
          tuition_convenience_fee_percentage: normalizeFeeNumber(res.data.tuition_convenience_fee_percentage, 1.95),
          feeding_fee: normalizeFeeNumber(res.data.feeding_fee),
          feeding_daily_fee: normalizeFeeNumber(res.data.feeding_daily_fee),
          feeding_weekly_fee: normalizeFeeNumber(res.data.feeding_weekly_fee),
          feeding_monthly_fee: normalizeFeeNumber(res.data.feeding_monthly_fee),
          transport_fee: normalizeFeeNumber(res.data.transport_fee),
          terminal_report_fee: normalizeFeeNumber(res.data.terminal_report_fee),
          admission_fee_enabled: Boolean(res.data.admission_fee_enabled),
          admission_fee_amount: normalizeFeeNumber(res.data.admission_fee_amount),
          other_fees: normalizeOtherFees(res.data.other_fees)
        });
      } catch (err) {
        console.error('Failed to load fees');
      }
    };

    
    loadSchoolSettings();
    fetchGradingScheme();
    fetchFees();
    fetchActiveTemplate();
  }, []);

  const fetchActiveTemplate = async () => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get('/api/school/report-template', { headers });
      const canonicalId = res.data.report_template_id || 'gradman_v1';
      setActiveTemplate(TEMPLATE_CANONICAL_TO_ALIAS[canonicalId] || canonicalId);
      setActiveTemplateConfig(res.data.report_template_config || {});

      const historyRes = await axios.get('/api/school/report-template/history', { headers });
      const nextHistory = Array.isArray(historyRes.data?.history) ? historyRes.data.history : [];
      setTemplateHistory(nextHistory);
      setSelectedTemplateHistorySnapshotId((currentValue) => {
        if (nextHistory.some((item) => item.snapshot_id === currentValue)) {
          return currentValue;
        }
        const preferredItem = nextHistory.find((item) => !item.is_current) || nextHistory[0];
        return preferredItem?.snapshot_id || '';
      });
    } catch (err) {
      console.error('Failed to load active template');
    }
  };

  const handleTemplateHistoryRestore = async (snapshotId) => {
    try {
      setTemplateHistoryBusyId(snapshotId);
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const response = await axios.post(`/api/school/report-template/history/${snapshotId}/restore`, {}, { headers });
      const canonicalId = response.data.report_template_id || 'gradman_v1';
      setActiveTemplate(TEMPLATE_CANONICAL_TO_ALIAS[canonicalId] || canonicalId);
      setActiveTemplateConfig(response.data.report_template_config || {});
      setTemplateMessage('✅ Report template restored successfully');
      fetchActiveTemplate();
      setTimeout(() => setTemplateMessage(''), 4000);
    } catch (err) {
      const errorMsg = err.response?.data?.message || 'Failed to restore report template history.';
      setTemplateMessage(`❌ ${errorMsg}`);
      setTimeout(() => setTemplateMessage(''), 5000);
    } finally {
      setTemplateHistoryBusyId('');
    }
  };

  const selectedTemplateHistoryItem = templateHistory.find((item) => item.snapshot_id === selectedTemplateHistorySnapshotId) || null;
  const templateHistoryPreview = buildTemplateHistoryPreview(activeTemplate, activeTemplateConfig, selectedTemplateHistoryItem);

  const handleTemplateHistoryDownload = async (snapshotId, fallbackName) => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const response = await axios.get(`/api/school/report-template/history/${snapshotId}/download`, {
        headers,
        responseType: 'blob'
      });
      const blobUrl = window.URL.createObjectURL(new Blob([response.data], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = fallbackName || `${snapshotId}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      const errorMsg = err.response?.data?.message || 'Failed to download report template snapshot.';
      setTemplateMessage(`❌ ${errorMsg}`);
      setTimeout(() => setTemplateMessage(''), 5000);
    }
  };

  const handleTemplateSelect = async (templateId) => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const canonicalId = TEMPLATE_ALIAS_TO_CANONICAL[templateId] || templateId;
      const response = await axios.post(
        '/api/school/report-template',
        { report_template_id: canonicalId },
        { headers }
      );
      setActiveTemplate(templateId);
      setActiveTemplateConfig(response.data.report_template_config || activeTemplateConfig);
      setTemplateMessage(`✅ Template ${templateId} is now active`);
      setTimeout(() => setTemplateMessage(''), 3000);
    } catch (err) {
      console.error('❌ Template selection error:', err.response?.data || err);
      const errorMsg = err.response?.data?.message || 'Failed to activate template. Please try again.';
      setTemplateMessage(`❌ ${errorMsg}`);
      setTimeout(() => setTemplateMessage(''), 5000);
    }
  };

  const handleCustomTemplateUpload = async (e) => {
    e.preventDefault();
    
    if (!customTemplateUpload.htmlFile) {
      alert('Please select an HTML file to upload');
      return;
    }

    if (subscriptionPlan !== 'Premium') {
      alert('Custom HTML Templates are only available in School OS Plus');
      return;
    }

    setUploadingTemplate(true);
    try {
      const formData = new FormData();
      formData.append('html_file', customTemplateUpload.htmlFile);
      
      if (customTemplateUpload.cssFile) {
        formData.append('css_file', customTemplateUpload.cssFile);
      }
      
      if (customTemplateUpload.backgroundImage) {
        formData.append('background_image', customTemplateUpload.backgroundImage);
      }
      
      if (customTemplateUpload.templateName) {
        formData.append('report_template_id', customTemplateUpload.templateName);
      }

      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };

      const response = await axios.post('/api/school/report-template/upload', formData, { headers });
      setTemplateMessage(`✅ Custom template uploaded successfully!`);
      
      // Reset the form
      setCustomTemplateUpload({
        templateName: '',
        htmlFile: null,
        cssFile: null,
        backgroundImage: null
      });
      
      // Fetch active template again to update list
      fetchActiveTemplate();
      
      setTimeout(() => setTemplateMessage(''), 5000);
    } catch (err) {
      console.error('❌ Template upload error:', err);
      const errorMsg = err.response?.data?.message || 'Failed to upload template. Please check the file format and try again.';
      setTemplateMessage(`❌ ${errorMsg}`);
      setTimeout(() => setTemplateMessage(''), 5000);
    } finally {
      setUploadingTemplate(false);
    }
  };





  const getCustomTemplateSrcDoc = () => {
    if (!activeTemplateConfig || activeTemplateConfig.type !== 'html') {
      return '<!doctype html><html><body><p>No custom template available</p></body></html>';
    }

    const cssStyles = activeTemplateConfig.css ? `<style>${activeTemplateConfig.css}</style>` : '';
    const background = activeTemplateConfig.background_image
      ? `style="background-image: url(${activeTemplateConfig.background_image}); background-size: cover; background-repeat: no-repeat;"
`      : '';

    return `<!doctype html><html><head><meta charset="utf-8">${cssStyles}</head><body ${background}>${activeTemplateConfig.html || '<p>No HTML content</p>'}</body></html>`;
  };

  const formatDisplayDate = (value) => {
    if (!value) return '';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
  };

  const previewTemplateCanonicalId = TEMPLATE_ALIAS_TO_CANONICAL[previewTemplate] || previewTemplate;
  const previewTemplateDefinition = reportTemplates.find((template) => template.id === previewTemplateCanonicalId);
  const previewReopeningDate = formatDisplayDate(settings.next_term_reopen_date) || '4 May 2026';
  const previewScoreTotals = [
    { subject: 'English Language', total: 67, position: '4th' },
    { subject: 'Mathematics', total: 70, position: '3rd' },
    { subject: 'Science', total: 64, position: '6th' },
    { subject: 'Creative Arts', total: 71, position: '2nd' }
  ].map((row) => {
    const total = Number(row.total) || 0;
    const classScore = Math.round((total * classScoreMax) / 100);
    const examScore = total - classScore;
    const grade = getGradeFromTotal(total);
    return {
      ...row,
      class_score: String(classScore),
      exam_score: String(examScore),
      total: String(total),
      grade,
      remarks: getRemarkFromGrade(grade)
    };
  });
  const previewTermAverage = previewScoreTotals.length
    ? (previewScoreTotals.reduce((sum, row) => sum + (Number(row.total) || 0), 0) / previewScoreTotals.length).toFixed(1)
    : '0.0';
  const previewGradingSchemeSummary = formatGradingSchemeSummary(classScoreMax, examScoreMax);
  const previewTemplateData = {
    school_name: settings.school_name || 'M. A. Bediako Adventist Preparatory School',
    school_logo: settings.logo_url || '',
    school_motto: settings.school_motto || 'Excellence in Education',
    school_email: settings.school_email || 'mabaps1974@yahoo.com',
    school_phone: settings.school_phone || '03220 80310',
    school_contact: `${settings.school_email || 'mabaps1974@yahoo.com'} | ${settings.school_phone || '03220 80310'}`,
    student_name: 'John Doe (Sample)',
    student_code: 'STU-2024-001',
    class_name: 'Basic 6C',
    academic_term: 'Term One',
    academic_year: '2024/2025',
    term_average: previewTermAverage,
    overall_position: '2nd',
    out_of_students: '45',
    attendance_percentage: '96%',
    total_attendance: '68/70',
    class_score_max: String(classScoreMax),
    exam_score_max: String(examScoreMax),
    grading_scheme_summary: previewGradingSchemeSummary,
    reopening_date: previewReopeningDate,
    homeroom_teacher_remarks: 'John has shown excellent performance this term. Keep up the good work!',
    headmaster_remarks: 'Outstanding academic achievement. Continue to strive for excellence.',
    proprietor_remarks: 'A model student. Well done!',
    ai_performance_analysis: 'John demonstrates strong consistency across core subjects with very good attendance and positive classroom habits.',
    strengths: 'Excellent literacy skills, strong class participation, and dependable homework completion.',
    weaknesses: 'Needs to speak up more during oral drills and improve speed in Mathematics problem solving.',
    subject_grades: previewScoreTotals
  };
  const previewTemplateHtml = previewTemplateDefinition?.config?.type === 'html'
    ? buildTemplateHtml({ templateConfig: previewTemplateDefinition.config, data: previewTemplateData })
    : '';
  const previewTemplateSectionConfig = previewTemplateDefinition?.config?.type === 'html'
    ? null
    : previewTemplateDefinition?.config?.sections
      ? previewTemplateDefinition.config
      : null;
  const previewTheme = PREVIEW_TEMPLATE_THEMES[previewTemplateCanonicalId] || PREVIEW_TEMPLATE_THEMES.default;
  const previewHideEmptyFields = Boolean(previewTemplateSectionConfig?.visibility?.hide_empty_fields);
  const previewHideEmptySections = Boolean(previewTemplateSectionConfig?.visibility?.hide_empty_sections);

  const isPreviewEmptyValue = (value) => {
    if (value === null || value === undefined) return true;
    if (Array.isArray(value)) return value.length === 0;
    if (typeof value === 'string') return value.trim() === '';
    return false;
  };

  const getPreviewFieldValue = (fieldKey) => {
    const value = previewTemplateData[fieldKey];
    if (isPreviewEmptyValue(value)) return '';
    return String(value);
  };

  const filterPreviewFields = (fields = []) => (
    previewHideEmptyFields
      ? fields.filter((field) => !isPreviewEmptyValue(previewTemplateData[field.key]))
      : fields
  );

  const renderTemplateCardThumbnail = (templateAlias) => {
    const canonicalId = TEMPLATE_ALIAS_TO_CANONICAL[templateAlias] || templateAlias;
    const templateDefinition = reportTemplates.find((template) => template.id === canonicalId);
    const templateTheme = PREVIEW_TEMPLATE_THEMES[canonicalId] || PREVIEW_TEMPLATE_THEMES.default;
    const templateSections = templateDefinition?.config?.sections || [];
    const tableSection = templateSections.find((section) => section.type === 'table');
    const summarySection = templateSections.find((section) => section.type === 'summary');
    const insightsSection = templateSections.find((section) => section.type === 'insights');
    const remarksCount = templateSections.filter((section) => section.type === 'remarks' || section.type === 'analysis').length;
    const signatureCount = templateSections.find((section) => section.type === 'signatures')?.fields?.length || 0;
    const thumbnailRows = Math.min(3, previewTemplateData.subject_grades.length || 3);
    const tableColumns = Math.min(4, tableSection?.columns?.length || 3);
    const summaryFields = Math.min(4, summarySection?.fields?.length || 2);

    return (
      <div className="mb-3 overflow-hidden rounded-xl border border-white/60 bg-white/80 shadow-sm">
        <div className={`${templateTheme.modalCanvas} origin-top-left scale-[0.22]`} style={{ width: '455%', height: 172, transformOrigin: 'top left' }}>
          <div className={templateTheme.sectionGap}>
            <div className={templateTheme.headerWrap}>
              <div className="mb-2 flex justify-center">
                <div className={`flex h-12 w-12 items-center justify-center rounded-full text-lg ${templateTheme.logoShell}`}>🏫</div>
              </div>
              <h4 className={templateTheme.titleClass}>{previewTemplateData.school_name}</h4>
              <p className={templateTheme.mottoClass}>{previewTemplateData.school_motto}</p>
            </div>

            <div className="text-center">
              <p className={templateTheme.academicTitleClass}>Terminal Report Card</p>
              <p className={templateTheme.academicMetaClass}>{previewTemplateData.academic_year} - {previewTemplateData.academic_term}</p>
            </div>

            <div className={templateTheme.studentCard}>
              <div>
                <p className="mb-1 text-slate-500">Student</p>
                <p className={templateTheme.summaryValue}>{previewTemplateData.student_name}</p>
              </div>
              <div>
                <p className="mb-1 text-slate-500">Class</p>
                <p className={templateTheme.summaryValue}>{previewTemplateData.class_name}</p>
              </div>
            </div>

            {summarySection && (
              <div className={templateTheme.summaryCard}>
                <p className={templateTheme.summaryTitle}>{summarySection.label}</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {Array.from({ length: summaryFields }).map((_, index) => (
                    <div key={`${templateAlias}-summary-${index}`} className="flex items-center gap-2">
                      <span className={templateTheme.summaryLabel}>•</span>
                      <span className={templateTheme.summaryValue}>Metric</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {insightsSection && (
              <div className={templateTheme.insightWrap}>
                <p className={templateTheme.insightTitle}>{insightsSection.label}</p>
                <div className="grid grid-cols-2 gap-2">
                  <div className={templateTheme.insightCard}>
                    <p className={templateTheme.insightLabel}>Strengths</p>
                    <p className={templateTheme.insightText}>Strong literacy and class focus.</p>
                  </div>
                  <div className={templateTheme.insightCard}>
                    <p className={templateTheme.insightLabel}>Needs</p>
                    <p className={templateTheme.insightText}>Faster maths problem solving.</p>
                  </div>
                </div>
              </div>
            )}

            {tableSection && (
              <div>
                <p className={templateTheme.tableTitle}>{tableSection.label}</p>
                <div className={`grid gap-px overflow-hidden rounded-lg ${templateTheme.tableHead}`} style={{ gridTemplateColumns: `repeat(${tableColumns}, minmax(0, 1fr))` }}>
                  {tableSection.columns.slice(0, tableColumns).map((column) => (
                    <div key={`${templateAlias}-${column.key}-head`} className="bg-inherit px-2 py-1 text-[10px] font-bold uppercase tracking-wide">
                      {column.label}
                    </div>
                  ))}
                  {Array.from({ length: thumbnailRows }).flatMap((_, rowIndex) => (
                    tableSection.columns.slice(0, tableColumns).map((column, columnIndex) => (
                      <div
                        key={`${templateAlias}-${rowIndex}-${column.key}`}
                        className={`px-2 py-1 text-[10px] ${templateTheme.tableRow} ${columnIndex === tableColumns - 1 ? templateTheme.tableGrade : column.key === 'total' ? templateTheme.tableTotal : ''}`}
                      >
                        {column.key === 'subject' ? previewTemplateData.subject_grades[rowIndex]?.subject || 'Subject' : '...'}
                      </div>
                    ))
                  ))}
                </div>
              </div>
            )}

            {remarksCount > 0 && (
              <div className="grid gap-2">
                {Array.from({ length: Math.min(2, remarksCount) }).map((_, index) => (
                  <div
                    key={`${templateAlias}-remark-${index}`}
                    className={index === 0 ? templateTheme.remarkTones.teacher_remarks : templateTheme.remarkTones.ai_analysis || templateTheme.remarkTones.default}
                  >
                    <p className="text-[10px] font-bold uppercase tracking-wide text-slate-700">Narrative</p>
                    <p className="text-[10px] text-slate-600">Short comment preview block.</p>
                  </div>
                ))}
              </div>
            )}

            {signatureCount > 0 && (
              <div className={templateTheme.signatureWrap}>
                <div className={`grid gap-3`} style={{ gridTemplateColumns: `repeat(${Math.min(3, signatureCount)}, minmax(0, 1fr))` }}>
                  {Array.from({ length: Math.min(3, signatureCount) }).map((_, index) => (
                    <div key={`${templateAlias}-signature-${index}`} className="text-center">
                      <div className={templateTheme.signatureLine}>
                        <p className={templateTheme.signatureText}>Sign</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderPreviewSection = (section) => {
    if (!section) return null;

    if (section.type === 'header') {
      return (
        <div key={section.id} className={previewTheme.headerWrap}>
          {previewTemplateData.school_logo ? (
            <div className="mb-2">
              <img
                src={previewTemplateData.school_logo}
                alt="School Logo"
                className="mx-auto h-16 w-16 object-contain"
              />
            </div>
          ) : (
            <div className="mb-2 flex justify-center">
              <div className={`flex h-16 w-16 items-center justify-center rounded-full text-3xl ${previewTheme.logoShell}`}>
                🏫
              </div>
            </div>
          )}
          <h1 className={previewTheme.titleClass}>{previewTemplateData.school_name}</h1>
          {previewTemplateData.school_motto && (
            <p className={previewTheme.mottoClass}>{previewTemplateData.school_motto}</p>
          )}
          {(previewTemplateData.school_email || previewTemplateData.school_phone) && (
            <p className={previewTheme.contactClass}>
              {previewTemplateData.school_email || ''}
              {previewTemplateData.school_email && previewTemplateData.school_phone ? ' | ' : ''}
              {previewTemplateData.school_phone || ''}
            </p>
          )}
        </div>
      );
    }

    if (section.type === 'student_info') {
      const fields = filterPreviewFields(section.fields || []);
      if (fields.length === 0 && previewHideEmptySections) return null;

      const academicFields = fields.filter((field) => field.key === 'academic_term' || field.key === 'academic_year');
      const identityFields = fields.filter((field) => field.key !== 'academic_term' && field.key !== 'academic_year');

      return (
        <div key={section.id} className="space-y-4">
          {academicFields.length > 0 && (
            <div className="text-center">
              <h2 className={previewTheme.academicTitleClass}>Terminal Report Card</h2>
              <p className={previewTheme.academicMetaClass}>
                Academic Year: {previewTemplateData.academic_year} - {previewTemplateData.academic_term}
              </p>
            </div>
          )}
          {identityFields.length > 0 && (
            <div className={previewTheme.studentCard}>
              {identityFields.map((field) => (
                <div key={field.key}>
                  <p className="mb-1 text-slate-600">{field.label}:</p>
                  <p className={previewTheme.summaryValue}>{getPreviewFieldValue(field.key)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    if (section.type === 'summary') {
      const fields = filterPreviewFields(section.fields || []);
      if (fields.length === 0 && previewHideEmptySections) return null;

      return (
        <div key={section.id} className={previewTheme.summaryCard}>
          <h3 className={previewTheme.summaryTitle}>{section.label}</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            {fields.map((field) => (
              <div key={field.key}>
                <span className={previewTheme.summaryLabel}>{field.label}:</span>{' '}
                <span className={previewTheme.summaryValue}>{getPreviewFieldValue(field.key)}</span>
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (section.type === 'table') {
      const rows = previewTemplateData.subject_grades || [];
      if (rows.length === 0 && previewHideEmptySections) return null;

      return (
        <div key={section.id} className="mb-6">
          <h3 className={previewTheme.tableTitle}>{section.label}</h3>
          <table className="w-full text-sm">
            <thead className={previewTheme.tableHead}>
              <tr>
                {section.columns.map((column) => (
                  <th key={column.key} className="p-2 text-left">{column.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${section.id}-${index}`} className={previewTheme.tableRow}>
                  {section.columns.map((column) => (
                    <td key={column.key} className="p-2">
                      {column.key === 'grade' ? (
                        <span className={previewTheme.tableGrade}>{row[column.key] ?? ''}</span>
                      ) : column.key === 'total' ? (
                        <span className={previewTheme.tableTotal}>{row[column.key] ?? ''}</span>
                      ) : (
                        row[column.key] ?? ''
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
          <h3 className={previewTheme.tableTitle}>{section.label}</h3>
          <p className={`mb-2 text-xs ${previewTheme.scaleText}`}>{previewGradingSchemeSummary}</p>
          <table className="w-full text-xs">
            <thead className={previewTheme.scaleHead}>
              <tr className="uppercase text-slate-500">
                <th className="p-2 text-left">Grade</th>
                <th className="p-2 text-left">Range</th>
                <th className="p-2 text-left">Remarks</th>
              </tr>
            </thead>
            <tbody>
              {GRADE_SCALE_ROWS.map((row) => (
                <tr key={row.grade} className="border-t">
                  <td className={`p-2 font-bold ${previewTheme.scaleText}`}>{row.grade}</td>
                  <td className={`p-2 ${previewTheme.scaleText}`}>{row.range}</td>
                  <td className={`p-2 ${previewTheme.scaleText}`}>{row.remark}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    if (section.type === 'remarks' || section.type === 'analysis') {
      const fields = filterPreviewFields(section.fields || []);
      if (fields.length === 0 && previewHideEmptySections) return null;

      const toneBySection = {
        teacher_remarks: previewTheme.remarkTones.teacher_remarks,
        headmaster_remarks: previewTheme.remarkTones.headmaster_remarks,
        proprietor_remarks: previewTheme.remarkTones.proprietor_remarks,
        ai_analysis: previewTheme.remarkTones.ai_analysis
      };
      const tone = toneBySection[section.id] || previewTheme.remarkTones.default;

      return (
        <div key={section.id} className={tone}>
          <p className="mb-1 text-xs font-bold text-slate-700">{section.label}:</p>
          {fields.map((field) => (
            <p key={field.key} className="text-sm italic text-slate-600">{getPreviewFieldValue(field.key)}</p>
          ))}
        </div>
      );
    }

    if (section.type === 'insights') {
      const fields = filterPreviewFields(section.fields || []);
      if (fields.length === 0 && previewHideEmptySections) return null;

      return (
        <div key={section.id} className={previewTheme.insightWrap}>
          <h3 className={previewTheme.insightTitle}>{section.label}</h3>
          <div className="grid gap-3 md:grid-cols-2">
            {fields.map((field) => (
              <div key={field.key} className={previewTheme.insightCard}>
                <p className={previewTheme.insightLabel}>{field.label}</p>
                <p className={previewTheme.insightText}>{getPreviewFieldValue(field.key)}</p>
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (section.type === 'signatures') {
      const fields = section.fields || [];
      if (fields.length === 0 && previewHideEmptySections) return null;

      return (
        <div key={section.id} className={previewTheme.signatureWrap}>
          <div className="grid grid-cols-3 gap-4">
            {fields.map((field) => (
              <div key={field.key} className="text-center">
                <div className={previewTheme.signatureLine}>
                  <p className={previewTheme.signatureText}>{field.label}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }

    const fields = filterPreviewFields(section.fields || []);
    if (fields.length === 0 && previewHideEmptySections) return null;

    return (
      <div key={section.id} className={previewTheme.genericCard}>
        <p className={previewTheme.genericTitle}>{section.label}</p>
        <div className={previewTheme.genericText}>
          {fields.map((field) => (
            <div key={field.key} className="flex items-start gap-2">
              <span className={previewTheme.genericLabel}>{field.label}:</span>
              <span>{getPreviewFieldValue(field.key)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const handleViewBankDetails = async () => {
    const pwd = prompt('Enter your password to view full bank details');
    if (!pwd) return;
    try {
      const res = await axios.post('/api/school/branding/bank/view', { password: pwd }, { headers: getAuthHeaders() });
      const data = res.data || {};
      setSettings((prev) => ({ ...prev, bank_name: data.bank_name, bank_account: data.bank_account, bank_account_name: data.bank_account_name, bank_branch: data.bank_branch }));
      setSavedBankSnapshot({
        bank_name: data.bank_name || '',
        bank_account: data.bank_account || '',
        bank_account_name: data.bank_account_name || '',
        bank_branch: data.bank_branch || '',
      });
      setBankDetailsVisible(true);
      setTemplateMessage('✅ Bank details revealed');
      setTimeout(() => setTemplateMessage(''), 3000);
    } catch (err) {
      setTemplateMessage(`❌ ${err.response?.data?.message || 'Unable to reveal bank details'}`);
      setTimeout(() => setTemplateMessage(''), 4000);
    }
  };

  const handleHideBankDetails = () => {
    setSettings((prev) => ({
      ...prev,
      bank_name: maskedBankSnapshot.bank_name || prev.bank_name,
      bank_account: maskedBankSnapshot.bank_account || prev.bank_account,
      bank_account_name: maskedBankSnapshot.bank_account_name || prev.bank_account_name,
      bank_branch: maskedBankSnapshot.bank_branch || prev.bank_branch,
    }));
    setBankDetailsVisible(false);
  };

  const handleChange = (e) => {
    setSettings({ ...settings, [e.target.name]: e.target.value });
  };

  const handleLogoFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setLogoUploadError('');

    const isAllowed = ['image/png', 'image/jpeg'].includes(file.type);
    if (!isAllowed) {
      setLogoUploadError('Logo must be a PNG or JPG image.');
      return;
    }

    const maxBytes = 5 * 1024 * 1024;
    if (file.size > maxBytes) {
      setLogoUploadError('Logo must be 5MB or smaller.');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      // Compress image by resizing and reducing quality
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const maxDimension = 200; // Resize to max 200x200 for logo
        let width = img.width;
        let height = img.height;

        if (width > height) {
          if (width > maxDimension) {
            height = Math.round((height * maxDimension) / width);
            width = maxDimension;
          }
        } else {
          if (height > maxDimension) {
            width = Math.round((width * maxDimension) / height);
            height = maxDimension;
          }
        }

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);

        // Convert to base64 with reduced quality
        const compressedDataUrl = canvas.toDataURL('image/jpeg', 0.8);
        setSettings((prev) => ({ ...prev, logo_url: compressedDataUrl }));
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const settingsPayload = {
        name: settings.school_name,
        motto: settings.school_motto,
        logo_url: settings.logo_url,
        primary_color: settings.primary_color,
        school_email: settings.school_email,
        school_phone: settings.school_phone,
        school_address: settings.school_address,
        school_website: settings.school_website,
        country_code: settings.country_code,
        anniversary_date: settings.anniversary_date,
        next_term_reopen_date: settings.next_term_reopen_date,
        admissions_visit_location_default: settings.admissions_visit_location_default,
        admissions_visit_contact_person_default: settings.admissions_visit_contact_person_default,
        admissions_visit_contact_phone_default: settings.admissions_visit_contact_phone_default,
        approval_pdf_enabled: settings.ai_registrar_enabled ? settings.approval_pdf_enabled : false,
        approval_pdf_delivery_mode: settings.approval_pdf_delivery_mode,
        approval_pdf_include_payment_summary: settings.ai_registrar_enabled ? settings.approval_pdf_include_payment_summary : false,
        approval_pdf_include_required_items: settings.ai_registrar_enabled ? settings.approval_pdf_include_required_items : false,
        approval_pdf_required_items: settings.ai_registrar_enabled ? settings.approval_pdf_required_items : '',
      };

      if (bankDetailsVisible || settings.bank_name !== maskedBankSnapshot.bank_name) {
        settingsPayload.bank_name = settings.bank_name;
      }
      if (bankDetailsVisible || settings.bank_account !== maskedBankSnapshot.bank_account) {
        settingsPayload.bank_account = settings.bank_account;
      }
      if (bankDetailsVisible || settings.bank_account_name !== maskedBankSnapshot.bank_account_name) {
        settingsPayload.bank_account_name = settings.bank_account_name;
      }
      if (bankDetailsVisible || settings.bank_branch !== maskedBankSnapshot.bank_branch) {
        settingsPayload.bank_branch = settings.bank_branch;
      }

      const settingsResponse = await axios.post('/api/school/settings', settingsPayload, { headers });
      const settingsData = settingsResponse.data || {};
      setSettings((prev) => ({
        ...prev,
        paystack_subaccount_code: settingsData.paystack_subaccount_code || prev.paystack_subaccount_code,
        paystack_bank_code: settingsData.paystack_bank_code || prev.paystack_bank_code,
        paystack_resolved_account_name: settingsData.paystack_resolved_account_name || prev.paystack_resolved_account_name,
      }));
      
      // Save fees separately
      await axios.post('/api/school/fees', {
        tuition_fee: fees.tuition_fee,
        tuition_convenience_fee_percentage: fees.tuition_convenience_fee_percentage,
        feeding_fee: fees.feeding_fee,
        feeding_daily_fee: fees.feeding_daily_fee,
        feeding_weekly_fee: fees.feeding_weekly_fee,
        feeding_monthly_fee: fees.feeding_monthly_fee,
        transport_fee: fees.transport_fee,
        terminal_report_fee: fees.terminal_report_fee,
        admission_fee_enabled: fees.admission_fee_enabled,
        admission_fee_amount: fees.admission_fee_amount,
        other_fees: fees.other_fees
      }, { headers });
      
      // Update local storage for immediate UI refresh
      const currentBranding = JSON.parse(localStorage.getItem('branding')) || {};
      const newBranding = { 
        ...currentBranding,
        name: settings.school_name,
        motto: settings.school_motto,
        logo: settings.logo_url,
        theme_color: settings.primary_color,
        email: settings.school_email,
        phone: settings.school_phone,
        address: settings.school_address,
        website: settings.school_website,
        country_code: settings.country_code,
        anniversary_date: settings.anniversary_date
      };
      localStorage.setItem('branding', JSON.stringify(newBranding));
      
      alert(settingsData.message || "Settings and fees updated! The page will reload to apply changes.");
      window.location.reload();
    } catch (err) {
      alert(err.response?.data?.message || "Failed to update settings or fees.");
      console.error(err);
    }
  };

  const handleReconnectPaystackSettlement = async () => {
    setIsReconnectingPaystackSettlement(true);
    try {
      const headers = getAuthHeaders();

      if (bankDetailsChangedSinceLastSave) {
        const saveResponse = await axios.post('/api/school/settings', {
          bank_name: settings.bank_name,
          bank_account: settings.bank_account,
          bank_account_name: settings.bank_account_name,
          bank_branch: settings.bank_branch,
        }, { headers });
        const savePayload = saveResponse.data || {};
        setSavedBankSnapshot({
          bank_name: settings.bank_name || '',
          bank_account: settings.bank_account || '',
          bank_account_name: settings.bank_account_name || '',
          bank_branch: settings.bank_branch || '',
        });
        if (savePayload.paystack_subaccount_code) {
          await loadSchoolSettings();
          alert(savePayload.message || 'Bank details saved and Paystack settlement account connected successfully.');
          return;
        }
      }

      const response = await axios.post('/api/school/settings/paystack/reconnect', {}, { headers });
      const payload = response.data || {};
      setSettings((prev) => ({
        ...prev,
        paystack_subaccount_code: payload.paystack_subaccount_code || prev.paystack_subaccount_code,
        paystack_bank_code: payload.paystack_bank_code || prev.paystack_bank_code,
        paystack_resolved_account_name: payload.paystack_resolved_account_name || prev.paystack_resolved_account_name,
      }));
      await loadSchoolSettings();
      alert(payload.message || 'Paystack settlement account connected successfully.');
    } catch (err) {
      const message = err.response?.data?.message || 'Failed to reconnect the Paystack settlement account.';
      const providerDetail = err.response?.data?.provider_detail;
      alert(providerDetail ? `${message}\n\nDetails: ${providerDetail}` : message);
      console.error(err);
    } finally {
      setIsReconnectingPaystackSettlement(false);
    }
  };


  const handleGradingSchemePreset = (preset) => {
    if (preset === '30/70') {
      setClassScoreMax(30);
      setExamScoreMax(70);
    } else if (preset === '40/60') {
      setClassScoreMax(40);
      setExamScoreMax(60);
    } else if (preset === '50/50') {
      setClassScoreMax(50);
      setExamScoreMax(50);
    }
  };

  const handleGradingSchemeSave = async () => {
    if (classScoreMax + examScoreMax !== 100) {
      setGradingSchemeStatus('Error: Class score and exam score must add up to 100');
      return;
    }
    if (classScoreMax < 0 || examScoreMax < 0) {
      setGradingSchemeStatus('Error: Scores must be positive');
      return;
    }

    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      await axios.post('/api/school/grading-scheme', {
        class_score_max: classScoreMax,
        exam_score_max: examScoreMax
      }, { headers });
      setGradingSchemeStatus(`✅ Grading scheme updated to ${classScoreMax}/${examScoreMax}`);
      setTimeout(() => setGradingSchemeStatus(''), 3000);
    } catch (err) {
      const errorMsg = err.response?.data?.message || 'Error saving grading scheme';
      setGradingSchemeStatus(`❌ ${errorMsg}`);
      console.error('Grading scheme save error:', err);
    }
  };

  return (
    <>
      <style>{`
        input[type=number]::-webkit-inner-spin-button,
        input[type=number]::-webkit-outer-spin-button {
          -webkit-appearance: none;
          margin: 0;
        }
        input[type=number] {
          -moz-appearance: textfield;
        }
      `}</style>
      <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100 max-w-3xl">
      <h2 className="text-2xl font-bold text-slate-800 mb-6">System Branding & Settings</h2>
      <form onSubmit={handleSave} className="space-y-6">
        <div>
          <label className="block text-sm font-bold text-slate-700 mb-2">School Name</label>
          <input
            name="school_name"
            value={settings.school_name}
            onChange={handleChange}
            className="w-full p-3 border rounded-lg bg-slate-50"
            placeholder="e.g. Fountain of Youth International School"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-slate-700 mb-2">School Motto</label>
          <input
            name="school_motto"
            value={settings.school_motto}
            onChange={handleChange}
            className="w-full p-3 border rounded-lg bg-slate-50"
            placeholder="e.g. Modeling Excellence in Mind, Body and Soul"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-slate-700 mb-2">Country (Public Holidays)</label>
          <select
            name="country_code"
            value={settings.country_code}
            onChange={handleChange}
            className="w-full p-3 border rounded-lg bg-slate-50"
          >
            <option value="GH">Ghana</option>
            <option value="NG">Nigeria</option>
            <option value="CI">Cote d'Ivoire</option>
            <option value="SN">Senegal</option>
            <option value="GM">Gambia</option>
            <option value="SL">Sierra Leone</option>
            <option value="LR">Liberia</option>
            <option value="BJ">Benin</option>
            <option value="TG">Togo</option>
            <option value="BF">Burkina Faso</option>
            <option value="GN">Guinea</option>
            <option value="ML">Mali</option>
            <option value="NE">Niger</option>
            <option value="CV">Cape Verde</option>
          </select>
          <p className="mt-2 text-xs text-slate-500">
            National holidays come from this country setting. Schools should still add their own closure dates separately so feeding, attendance, and meal planning follow the real school calendar.
          </p>
        </div>

        <div>
          <label className="block text-sm font-bold text-slate-700 mb-2">School Anniversary Date</label>
          <input
            type="date"
            name="anniversary_date"
            value={settings.anniversary_date || ''}
            onChange={handleChange}
            className="w-full p-3 border rounded-lg bg-slate-50"
            placeholder="Founding date or anniversary"
          />
          <p className="text-xs text-slate-500 mt-1">This date will appear in the holiday calendar as a special event</p>
        </div>

        <div>
          <label className="block text-sm font-bold text-slate-700 mb-2">School Logo (PNG or JPG)</label>
          <input
            type="file"
            accept="image/png,image/jpeg"
            onChange={handleLogoFileChange}
            className="w-full p-3 border rounded-lg bg-slate-50"
          />
          {logoUploadError && (
            <p className="text-xs text-rose-600 mt-2">{logoUploadError}</p>
          )}
          {settings.logo_url && (
            <div className="mt-4 p-4 border rounded-xl bg-slate-50 inline-block">
              <p className="text-xs font-bold text-slate-400 uppercase mb-2">Preview</p>
              <img src={settings.logo_url} alt="Logo Preview" className="h-16 object-contain" />
            </div>
          )}
        </div>
        
        <div>
          <label className="block text-sm font-bold text-slate-700 mb-3">Primary Theme Color</label>
          <p className="text-xs text-slate-600 mb-3">Select your school's brand color. This will appear on all reports and documents.</p>
          <div className="grid grid-cols-4 md:grid-cols-8 gap-3">
            {colorPalette.map((color) => (
              <button
                key={color.hex}
                onClick={() => setSettings((prev) => ({ ...prev, primary_color: color.hex }))}
                className={`relative group transition-transform hover:scale-110`}
                title={color.name}
              >
                <div
                  className={`h-12 w-12 rounded-lg shadow-md border-2 ${
                    settings.primary_color === color.hex ? 'border-slate-800 ring-2 ring-offset-2 ring-slate-400' : 'border-slate-200'
                  }`}
                  style={{ backgroundColor: color.hex }}
                />
                <span className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-slate-800 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  {color.name}
                </span>
              </button>
            ))}
          </div>
          <div className="mt-4 p-3 bg-slate-100 rounded-lg flex items-center gap-3">
            <div
              className="h-8 w-8 rounded-lg shadow border border-slate-300"
              style={{ backgroundColor: settings.primary_color }}
            />
            <div>
              <p className="text-xs font-bold text-slate-600 uppercase">Selected Color</p>
              <p className="text-sm font-mono text-slate-800">{settings.primary_color.toUpperCase()}</p>
            </div>
          </div>
        </div>

        {/* Contact Details Section */}
        <div className="border-t pt-6 mt-8">
          <h3 className="text-lg font-bold text-slate-800 mb-4">📍 Contact Details</h3>
          <p className="text-sm text-slate-600 mb-4">These details will appear on all printed documents (reports, reminders, etc.)</p>
          
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">School Email</label>
            <input
              name="school_email"
              type="email"
              value={settings.school_email}
              onChange={handleChange}
              className="w-full p-3 border rounded-lg bg-slate-50"
              placeholder="e.g. admin@school.edu.gh"
            />
          </div>

          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">School Phone</label>
            <input
              name="school_phone"
              value={settings.school_phone}
              onChange={handleChange}
              className="w-full p-3 border rounded-lg bg-slate-50"
              placeholder="e.g. +233 XXX XXX XXX"
            />
          </div>

          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">School Address</label>
            <input
              name="school_address"
              value={settings.school_address}
              onChange={handleChange}
              className="w-full p-3 border rounded-lg bg-slate-50"
              placeholder="e.g. 123 Main Street, Accra, Ghana"
            />
          </div>

          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">School Website</label>
            <input
              name="school_website"
              value={settings.school_website}
              onChange={handleChange}
              className="w-full p-3 border rounded-lg bg-slate-50"
              placeholder="e.g. www.school.edu.gh"
            />
          </div>
        </div>

        {/* Payment Account Details Section */}
        <div className="border-t pt-6 mt-8">
          <h3 className="text-lg font-bold text-slate-800 mb-4">💳 Payment Account Details</h3>
          <p className="text-sm text-slate-600 mb-6">Tracked transfer payments depend on this settlement account. Bank details are hidden after save and require password re-entry to view again.</p>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Bank Transfer Section */}
            <div className="border rounded-lg p-4 bg-green-50">
              <h4 className="font-bold text-slate-800 mb-3">🏦 Bank Account</h4>
              <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <p className="max-w-sm text-xs text-slate-600">Saved bank details stay masked by default. Use the secure reveal action and confirm your password to view the full account information.</p>
                {!bankDetailsVisible ? (
                  <button
                    type="button"
                    onClick={handleViewBankDetails}
                    className="inline-flex min-w-40 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
                  >
                    Reveal Bank Details
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleHideBankDetails}
                    className="inline-flex min-w-40 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-slate-400 hover:bg-slate-100"
                  >
                    Close Bank Details
                  </button>
                )}
              </div>
              <div className="mb-3 rounded border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-900">
                EduPulse uses these bank details to connect the school's Paystack settlement account for tracked transfer payments. Keep them accurate because they also remain the school's official account for direct transfers and office confirmation.
              </div>
              <div className="space-y-3">
                <div>
                  <label className="text-sm font-bold text-slate-700">Bank Name</label>
                  <input
                    type="text"
                    name="bank_name"
                    value={settings.bank_name || ''}
                    onChange={handleChange}
                    className="w-full p-2 border rounded mt-1 bg-white"
                    placeholder="e.g., Fidelity Bank Ghana"
                    disabled={!bankDetailsVisible && isMaskedBankValue(settings.bank_name)}
                  />
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700">Account Number</label>
                  <input
                    type="text"
                    name="bank_account"
                    value={settings.bank_account || ''}
                    onChange={handleChange}
                    className="w-full p-2 border rounded mt-1 bg-white"
                    placeholder="School bank account number"
                    disabled={!bankDetailsVisible && isMaskedBankValue(settings.bank_account)}
                  />
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700">Account Holder Name</label>
                  <input
                    type="text"
                    name="bank_account_name"
                    value={settings.bank_account_name || ''}
                    onChange={handleChange}
                    className="w-full p-2 border rounded mt-1 bg-white"
                    placeholder="Name on bank account"
                    disabled={!bankDetailsVisible && isMaskedBankValue(settings.bank_account_name)}
                  />
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700">Branch (Optional)</label>
                  <input
                    type="text"
                    name="bank_branch"
                    value={settings.bank_branch || ''}
                    onChange={handleChange}
                    className="w-full p-2 border rounded mt-1 bg-white"
                    placeholder="Bank branch name"
                    disabled={!bankDetailsVisible && isMaskedBankValue(settings.bank_branch)}
                  />
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700">Tracked Transfer Settlement Status</label>
                  <div className={`mt-1 rounded border p-3 text-xs ${paystackProvisioningState.tone}`}>
                    <p className="font-bold uppercase tracking-wide">{paystackProvisioningState.label}</p>
                    <p className="mt-1">{paystackProvisioningState.message}</p>
                    {settings.paystack_subaccount_code ? <p className="mt-2">Generated subaccount code: {settings.paystack_subaccount_code}</p> : null}
                    {settings.paystack_bank_code ? <p className="mt-1">Verified Paystack bank code: {settings.paystack_bank_code}</p> : null}
                    {settings.paystack_resolved_account_name ? <p className="mt-1">Verified account name: {settings.paystack_resolved_account_name}</p> : null}
                    {bankDetailsReadyForProvisioning ? (
                      <button
                        type="button"
                        onClick={handleReconnectPaystackSettlement}
                        disabled={isReconnectingPaystackSettlement}
                        className="mt-3 inline-flex items-center rounded-lg bg-slate-900 px-3 py-2 text-xs font-bold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
                      >
                        {isReconnectingPaystackSettlement
                          ? 'Connecting...'
                          : bankDetailsChangedSinceLastSave
                            ? 'Save and Connect Settlement Account'
                          : settings.paystack_subaccount_code
                            ? 'Refresh Settlement Account'
                            : 'Reconnect Settlement Account'}
                      </button>
                    ) : null}
                  </div>
                  <p className="mt-2 text-xs text-slate-500">Schools only enter their bank details here. EduPulse creates and maintains the Paystack settlement subaccount in the background.</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Financial Fees Section */}
        <div className="border-t pt-6 mt-8">
          <h3 className="text-lg font-bold text-slate-800 mb-4">💰 Financial Fees Configuration</h3>
          <p className="text-sm text-slate-600 mb-4">Set the standard fees for your school. These can be updated anytime. Parents will see these amounts when making payments for their students.</p>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Tuition Fee</label>
              <div className="flex items-center gap-2">
                <span className="text-slate-600 font-semibold">GH₵</span>
                <input
                  type="number"
                  value={fees.tuition_fee}
                  onChange={(e) => setFees((prev) => ({ ...prev, tuition_fee: parseFloat(e.target.value) || 0 }))}
                  className="flex-1 p-3 border rounded-lg bg-slate-50"
                  placeholder="0.00"
                  step="0.01"
                  min="0"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Tuition Convenience Fee (%)</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={fees.tuition_convenience_fee_percentage}
                  onChange={(e) => setFees((prev) => ({ ...prev, tuition_convenience_fee_percentage: parseFloat(e.target.value) || 0 }))}
                  className="flex-1 p-3 border rounded-lg bg-slate-50"
                  placeholder="1.95"
                  step="0.01"
                  min="0"
                />
                <span className="text-slate-600 font-semibold">%</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">Parents pay this extra percentage only on tuition tracked through the EduPulse transfer account.</p>
              <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-900">
                <p className="font-semibold">Tracked tuition preview</p>
                <p className="mt-1">Convenience fee to add: {tuitionConvenienceFeePercentage.toFixed(2)}% of GH₵ {tuitionFee.toFixed(2)} = GH₵ {tuitionConvenienceAmount.toFixed(2)}</p>
                <p className="mt-1">Parent tracked-transfer total for tuition: GH₵ {tuitionTransferTotal.toFixed(2)}</p>
              </div>
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Feeding Fee (Daily Plan)</label>
              <div className="flex items-center gap-2">
                <span className="text-slate-600 font-semibold">GH₵</span>
                <input
                  type="number"
                  value={fees.feeding_daily_fee}
                  onChange={(e) => {
                    const nextValue = parseFloat(e.target.value) || 0;
                    setFees((prev) => ({
                      ...prev,
                      feeding_daily_fee: nextValue,
                      feeding_fee: prev.feeding_monthly_fee || prev.feeding_weekly_fee || nextValue,
                    }));
                  }}
                  className="flex-1 p-3 border rounded-lg bg-slate-50"
                  placeholder="0.00"
                  step="0.01"
                  min="0"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Feeding Fee (Weekly Plan)</label>
              <div className="flex items-center gap-2">
                <span className="text-slate-600 font-semibold">GH₵</span>
                <input
                  type="number"
                  value={fees.feeding_weekly_fee}
                  onChange={(e) => {
                    const nextValue = parseFloat(e.target.value) || 0;
                    setFees((prev) => ({
                      ...prev,
                      feeding_weekly_fee: nextValue,
                      feeding_fee: prev.feeding_monthly_fee || nextValue || prev.feeding_daily_fee,
                    }));
                  }}
                  className="flex-1 p-3 border rounded-lg bg-slate-50"
                  placeholder="0.00"
                  step="0.01"
                  min="0"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Feeding Fee (Monthly Plan)</label>
              <div className="flex items-center gap-2">
                <span className="text-slate-600 font-semibold">GH₵</span>
                <input
                  type="number"
                  value={fees.feeding_monthly_fee}
                  onChange={(e) => {
                    const nextValue = parseFloat(e.target.value) || 0;
                    setFees((prev) => ({
                      ...prev,
                      feeding_monthly_fee: nextValue,
                      feeding_fee: nextValue || prev.feeding_weekly_fee || prev.feeding_daily_fee,
                    }));
                  }}
                  className="flex-1 p-3 border rounded-lg bg-slate-50"
                  placeholder="0.00"
                  step="0.01"
                  min="0"
                />
              </div>
            </div>


            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Transport Fee (Optional)</label>
              <div className="flex items-center gap-2">
                <span className="text-slate-600 font-semibold">GH₵</span>
                <input
                  type="number"
                  value={fees.transport_fee}
                  onChange={(e) => setFees((prev) => ({ ...prev, transport_fee: parseFloat(e.target.value) || 0 }))}
                  className="flex-1 p-3 border rounded-lg bg-slate-50"
                  placeholder="0.00"
                  step="0.01"
                  min="0"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Terminal Report Printing Fee (Per Term)</label>
              <div className="flex items-center gap-2">
                <span className="text-slate-600 font-semibold">GH₵</span>
                <input
                  type="number"
                  value={fees.terminal_report_fee}
                  onChange={(e) => setFees((prev) => ({ ...prev, terminal_report_fee: parseFloat(e.target.value) || 0 }))}
                  className="flex-1 p-3 border rounded-lg bg-slate-50"
                  placeholder="0.00"
                  step="0.01"
                  min="0"
                />
              </div>
            </div>

            <div className="md:col-span-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-1">Admission Fee</label>
                  <p className="text-sm text-slate-600">Turn this on only if your school charges a separate admission fee for newly admitted learners.</p>
                </div>
                <label className="inline-flex items-center gap-3 text-sm font-bold text-slate-700">
                  <input
                    type="checkbox"
                    checked={fees.admission_fee_enabled}
                    onChange={(e) => setFees((prev) => ({ ...prev, admission_fee_enabled: e.target.checked }))}
                    className="h-4 w-4 rounded border-slate-300"
                  />
                  Enable admission fee
                </label>
              </div>

              <div className="mt-4 flex items-center gap-2 max-w-xs">
                <span className="text-slate-600 font-semibold">GH₵</span>
                <input
                  type="number"
                  value={fees.admission_fee_amount}
                  onChange={(e) => setFees((prev) => ({ ...prev, admission_fee_amount: parseFloat(e.target.value) || 0 }))}
                  className="flex-1 p-3 border rounded-lg bg-white"
                  placeholder="0.00"
                  step="0.01"
                  min="0"
                  disabled={!fees.admission_fee_enabled}
                />
              </div>
            </div>
          </div>

          {/* Other Fees Section */}
          <div className="mt-6 p-4 bg-slate-50 rounded-lg border border-slate-200">
            <p className="text-sm font-bold text-slate-700 mb-3">📌 Additional Fees (e.g., Sports, Library, Activities)</p>
            <div className="space-y-3">
              {Object.entries(fees.other_fees || {}).map(([feeName, amount]) => (
                <div key={feeName} className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-700 flex-1">{feeName}:</span>
                  <span className="text-slate-600 font-semibold">GH₵</span>
                  <input
                    type="number"
                    value={amount}
                    onChange={(e) => setFees((prev) => ({
                      ...prev,
                      other_fees: { ...prev.other_fees, [feeName]: parseFloat(e.target.value) || 0 }
                    }))}
                    className="w-24 p-2 border rounded-lg bg-white text-sm"
                    step="0.01"
                    min="0"
                  />
                  <button
                    type="button"
                    onClick={() => setFees((prev) => {
                      const updated = { ...prev.other_fees };
                      delete updated[feeName];
                      return { ...prev, other_fees: updated };
                    })}
                    className="px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg text-sm font-bold"
                  >
                    Remove
                  </button>
                </div>
              ))}
              
              <div className="flex items-center gap-2 pt-2 border-t">
                <input
                  type="text"
                  value={otherFeeInput}
                  onChange={(e) => setOtherFeeInput(e.target.value)}
                  placeholder="Fee name (e.g., Sports, Library)"
                  className="flex-1 p-2 border rounded-lg bg-white text-sm"
                />
                <span className="text-slate-600 font-semibold">GH₵</span>
                <input
                  type="number"
                  value={otherFeeAmount}
                  onChange={(e) => setOtherFeeAmount(e.target.value)}
                  placeholder="0.00"
                  className="w-24 p-2 border rounded-lg bg-white text-sm"
                  step="0.01"
                  min="0"
                />
                <button
                  type="button"
                  onClick={() => {
                    if (otherFeeInput.trim()) {
                      setFees((prev) => ({
                        ...prev,
                        other_fees: {
                          ...prev.other_fees,
                          [otherFeeInput.trim()]: parseFloat(otherFeeAmount) || 0
                        }
                      }));
                      setOtherFeeInput('');
                      setOtherFeeAmount('');
                    }
                  }}
                  className="px-4 py-2 bg-slate-700 text-white rounded-lg text-sm font-bold hover:bg-slate-600"
                >
                  Add Fee
                </button>
              </div>
            </div>
          </div>

          {/* Fee Summary */}
          <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm font-bold text-slate-700 mb-3">📊 Total Fees Summary</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div>
                <p className="text-slate-600">Tuition</p>
                <p className="text-lg font-bold text-slate-800">GH₵ {tuitionFee.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-slate-600">Tuition Convenience</p>
                <p className="text-lg font-bold text-slate-800">{tuitionConvenienceFeePercentage.toFixed(2)}%</p>
              </div>
              <div>
                <p className="text-slate-600">Convenience Amount</p>
                <p className="text-lg font-bold text-slate-800">GH₵ {tuitionConvenienceAmount.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-slate-600">Tracked Tuition Total</p>
                <p className="text-lg font-bold text-slate-800">GH₵ {tuitionTransferTotal.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-slate-600">Feeding Daily</p>
                <p className="text-lg font-bold text-slate-800">GH₵ {feedingDailyFee.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-slate-600">Feeding Weekly</p>
                <p className="text-lg font-bold text-slate-800">GH₵ {feedingWeeklyFee.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-slate-600">Feeding Monthly</p>
                <p className="text-lg font-bold text-slate-800">GH₵ {feedingMonthlyFee.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-slate-600">Transport</p>
                <p className="text-lg font-bold text-slate-800">GH₵ {transportFee.toFixed(2)}</p>
              </div>
              {fees.admission_fee_enabled ? (
                <div>
                  <p className="text-slate-600">Admission</p>
                  <p className="text-lg font-bold text-slate-800">GH₵ {admissionFeeAmount.toFixed(2)}</p>
                </div>
              ) : null}
              {Object.entries(fees.other_fees || {}).map(([name, amount]) => (
                <div key={name}>
                  <p className="text-slate-600">{name}</p>
                  <p className="text-lg font-bold text-slate-800">GH₵ {Number(amount || 0).toFixed(2)}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="border-t pt-6 mt-8">
          <h3 className="text-lg font-bold text-slate-800 mb-4">🎓 Admissions Configuration</h3>
          <p className="text-sm text-slate-600 mb-4">
            Configure the parent-facing admissions responses, school-visit defaults, and the approval letter for accepted applicants.
          </p>

          {!settings.ai_registrar_enabled && (
            <div className="mb-4 rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {subscriptionTrial.active
                ? `This school has an active ${subscriptionTrial.plan || subscriptionPlan} trial, but AI Registrar access is still not enabled. Refresh this page, and if the message remains, contact support because the trial entitlement should unlock the approval letter workflow.`
                : 'AI Registrar workflow automation is available on Basic, Premium, or an active eligible trial. Free Tier schools can still review applications, but the approval letter stays locked.'}
            </div>
          )}

          <div className="space-y-5">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
              <h4 className="text-sm font-bold uppercase tracking-wide text-slate-700">School Visit Defaults</h4>
              <p className="mt-1 text-sm text-slate-600">These defaults prefill the admissions review queue when staff selects School Visit Required and sends the review update from the application itself.</p>
              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-2">Visit Location</label>
                  <input name="admissions_visit_location_default" value={settings.admissions_visit_location_default} onChange={handleChange} className="w-full p-3 border rounded-lg bg-white" placeholder="Admissions office / campus gate" />
                </div>
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-2">Contact Person</label>
                  <input name="admissions_visit_contact_person_default" value={settings.admissions_visit_contact_person_default} onChange={handleChange} className="w-full p-3 border rounded-lg bg-white" placeholder="Admissions Officer" />
                </div>
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-2">Contact Phone</label>
                  <input name="admissions_visit_contact_phone_default" value={settings.admissions_visit_contact_phone_default} onChange={handleChange} className="w-full p-3 border rounded-lg bg-white" placeholder="+233..." />
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 space-y-5">
              <h4 className="text-sm font-bold uppercase tracking-wide text-slate-700">Approved Admission Letter</h4>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-1">Enable Admission Letter</label>
                  <p className="text-sm text-slate-600">
                    When enabled, approved applications can expose a downloadable admission letter through the secure parent status page.
                  </p>
                </div>
                <label className="inline-flex items-center gap-3 text-sm font-bold text-slate-700 whitespace-nowrap">
                  <input
                    type="checkbox"
                    checked={settings.approval_pdf_enabled}
                    onChange={(e) => setSettings((prev) => ({ ...prev, approval_pdf_enabled: e.target.checked }))}
                    className="h-4 w-4 rounded border-slate-300"
                    disabled={!settings.ai_registrar_enabled}
                  />
                  Enable Letter
                </label>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-2">Letter Delivery</label>
                  <select
                    name="approval_pdf_delivery_mode"
                    value={settings.approval_pdf_delivery_mode}
                    onChange={handleChange}
                    className="w-full p-3 border rounded-lg bg-white"
                    disabled={!settings.ai_registrar_enabled || !settings.approval_pdf_enabled}
                  >
                    <option value="status_page_only">Status Page Only</option>
                    <option value="email_link">Email Link + Status Page</option>
                    <option value="email_attachment">Email Attachment</option>
                  </select>
                  <p className="text-xs text-slate-500 mt-2">
                    Parents can always use the secure status page. Email-link mode also adds the letter link to approval emails.
                  </p>
                </div>

                <div className="space-y-3">
                  <label className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-3">
                    <input
                      type="checkbox"
                      checked={settings.approval_pdf_include_payment_summary}
                      onChange={(e) => setSettings((prev) => ({ ...prev, approval_pdf_include_payment_summary: e.target.checked }))}
                      className="mt-1 h-4 w-4 rounded border-slate-300"
                      disabled={!settings.ai_registrar_enabled || !settings.approval_pdf_enabled}
                    />
                    <span>
                      <span className="block text-sm font-bold text-slate-700">Include Payment Instructions</span>
                      <span className="block text-xs text-slate-500">Adds the payment link and school-configured admission fee summary when relevant.</span>
                    </span>
                  </label>

                  <label className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-3">
                    <input
                      type="checkbox"
                      checked={settings.approval_pdf_include_required_items}
                      onChange={(e) => setSettings((prev) => ({ ...prev, approval_pdf_include_required_items: e.target.checked }))}
                      className="mt-1 h-4 w-4 rounded border-slate-300"
                      disabled={!settings.ai_registrar_enabled || !settings.approval_pdf_enabled}
                    />
                    <span>
                      <span className="block text-sm font-bold text-slate-700">Include Required Items</span>
                      <span className="block text-xs text-slate-500">Adds the list of documents or items parents should bring after approval.</span>
                    </span>
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-700 mb-2">Required Items Text</label>
                <textarea
                  name="approval_pdf_required_items"
                  value={settings.approval_pdf_required_items}
                  onChange={handleChange}
                  rows={5}
                  className="w-full p-3 border rounded-lg bg-white"
                  disabled={!settings.ai_registrar_enabled || !settings.approval_pdf_enabled || !settings.approval_pdf_include_required_items}
                  placeholder={'Examples:\n- Bring two passport photographs\n- Bring prior report card\n- Report to the admissions office on reopening day'}
                />
                <p className="text-xs text-slate-500 mt-2">
                  This is school-controlled content for approved applicants only. Rejection and correction responses do not generate an approval letter.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Save Settings Button */}
        <div className="pt-6 border-t border-slate-200">
          <button
            type="submit"
            className="w-full md:w-auto px-8 py-4 bg-linear-to-r from-blue-600 to-blue-700 text-white font-bold rounded-xl shadow-lg hover:from-blue-700 hover:to-blue-800 transition-all hover:scale-105 text-lg"
          >
            💾 Save Settings
          </button>
          <p className="text-xs text-slate-500 mt-3">
            This will save school branding, admissions configuration, contact details, and fee configuration. The page will reload to apply changes.
          </p>
        </div>
      </form>

      <div className="mt-10 border-t pt-8">
        <h3 className="text-xl font-bold text-slate-800 mb-4">📋 Terminal Report Templates</h3>
        <p className="text-sm text-slate-600 mb-4">
          Choose which template layout to use for terminal reports. Click a template to preview it, then click "Set as Active" to activate.
        </p>

        <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <label className="block text-sm font-bold text-slate-700 mb-2">Next Term Reopen Date</label>
          <input
            type="date"
            name="next_term_reopen_date"
            value={settings.next_term_reopen_date}
            onChange={handleChange}
            className="w-full md:w-72 p-3 border rounded-lg bg-white"
          />
          <p className="text-xs text-slate-500 mt-2">
            Set this once and it will automatically appear on every terminal report template.
          </p>
        </div>
        
        {templateMessage && (
          <div className={`mb-4 p-3 rounded-lg ${
            templateMessage.includes('✅') ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'
          }`}>
            {templateMessage}
          </div>
        )}
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Available Templates</label>
            <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
              <div className={`border-2 rounded-2xl p-3 md:p-4 transition-all ${
                  activeTemplate === 'sample1' ? 'border-blue-600 bg-blue-100 ring-2 ring-blue-400' : 'border-blue-200 bg-blue-50'
                }`}
              >
                <div 
                  onClick={() => { 
                    setPreviewTemplate('sample1'); 
                    setShowTemplatePreview(true); 
                  }}
                  className="cursor-pointer hover:opacity-80 transition-opacity"
                >
                  {renderTemplateCardThumbnail('sample1')}
                  <div className="mb-1.5 flex items-start justify-between gap-2">
                    <p className="font-bold text-blue-900 text-sm md:text-base">📄 Sample 1</p>
                    {activeTemplate === 'sample1' && <span className="shrink-0 rounded-full bg-blue-600 px-2 py-1 text-[10px] font-bold text-white">ACTIVE</span>}
                  </div>
                  <p className="mb-2 text-[11px] leading-5 text-blue-700 md:text-xs">Professional layout with centered header and detailed sections</p>
                </div>
                <button
                  onClick={() => handleTemplateSelect('sample1')}
                  disabled={activeTemplate === 'sample1'}
                  className={`w-full mt-2 rounded-lg px-3 py-2 text-sm font-bold transition-all ${
                    activeTemplate === 'sample1' 
                      ? 'bg-blue-200 text-blue-800 cursor-not-allowed' 
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}
                >
                  {activeTemplate === 'sample1' ? '✓ Currently Active' : 'Set as Active'}
                </button>
              </div>
              <div className={`border-2 rounded-2xl p-3 md:p-4 transition-all ${
                  activeTemplate === 'sample2' ? 'border-green-600 bg-green-100 ring-2 ring-green-400' : 'border-green-200 bg-green-50'
                }`}
              >
                <div 
                  onClick={() => { 
                    setPreviewTemplate('sample2'); 
                    setShowTemplatePreview(true); 
                  }}
                  className="cursor-pointer hover:opacity-80 transition-opacity"
                >
                  {renderTemplateCardThumbnail('sample2')}
                  <div className="mb-1.5 flex items-start justify-between gap-2">
                    <p className="font-bold text-green-900 text-sm md:text-base">📄 Sample 2</p>
                    {activeTemplate === 'sample2' && <span className="shrink-0 rounded-full bg-green-600 px-2 py-1 text-[10px] font-bold text-white">ACTIVE</span>}
                  </div>
                  <p className="mb-2 text-[11px] leading-5 text-green-700 md:text-xs">Compact single-page format with emphasis on grades</p>
                </div>
                <button
                  onClick={() => handleTemplateSelect('sample2')}
                  disabled={activeTemplate === 'sample2'}
                  className={`w-full mt-2 px-3 py-2 rounded-lg text-sm font-bold transition-all ${
                    activeTemplate === 'sample2' 
                      ? 'bg-green-200 text-green-800 cursor-not-allowed' 
                      : 'bg-green-600 text-white hover:bg-green-700'
                  }`}
                >
                  {activeTemplate === 'sample2' ? '✓ Currently Active' : 'Set as Active'}
                </button>
              </div>
              <div className={`border-2 rounded-2xl p-3 md:p-4 transition-all ${
                  activeTemplate === 'sample3' ? 'border-purple-600 bg-purple-100 ring-2 ring-purple-400' : 'border-purple-200 bg-purple-50'
                }`}
              >
                <div 
                  onClick={() => { 
                    setPreviewTemplate('sample3'); 
                    setShowTemplatePreview(true); 
                  }}
                  className="cursor-pointer hover:opacity-80 transition-opacity"
                >
                  {renderTemplateCardThumbnail('sample3')}
                  <div className="mb-1.5 flex items-start justify-between gap-2">
                    <p className="font-bold text-purple-900 text-sm md:text-base">📄 Sample 3</p>
                    {activeTemplate === 'sample3' && <span className="shrink-0 rounded-full bg-purple-600 px-2 py-1 text-[10px] font-bold text-white">ACTIVE</span>}
                  </div>
                  <p className="mb-2 text-[11px] leading-5 text-purple-700 md:text-xs">Modern design with visual progress indicators</p>
                </div>
                <button
                  onClick={() => handleTemplateSelect('sample3')}
                  disabled={activeTemplate === 'sample3'}
                  className={`w-full mt-2 px-3 py-2 rounded-lg text-sm font-bold transition-all ${
                    activeTemplate === 'sample3' 
                      ? 'bg-purple-200 text-purple-800 cursor-not-allowed' 
                      : 'bg-purple-600 text-white hover:bg-purple-700'
                  }`}
                >
                  {activeTemplate === 'sample3' ? '✓ Currently Active' : 'Set as Active'}
                </button>
              </div>
              <div className={`border-2 rounded-2xl p-3 md:p-4 transition-all ${
                  activeTemplate === 'sample4' ? 'border-amber-600 bg-amber-100 ring-2 ring-amber-400' : 'border-amber-200 bg-amber-50'
                }`}
              >
                <div 
                  onClick={() => { 
                    setPreviewTemplate('sample4'); 
                    setShowTemplatePreview(true); 
                  }}
                  className="cursor-pointer hover:opacity-80 transition-opacity"
                >
                  {renderTemplateCardThumbnail('sample4')}
                  <div className="mb-1.5 flex items-start justify-between gap-2">
                    <p className="font-bold text-amber-900 text-sm md:text-base">📄 Sample 4</p>
                    {activeTemplate === 'sample4' && <span className="shrink-0 rounded-full bg-amber-600 px-2 py-1 text-[10px] font-bold text-white">ACTIVE</span>}
                  </div>
                  <p className="mb-2 text-[11px] leading-5 text-amber-700 md:text-xs">Detailed narrative report with extensive remarks section</p>
                </div>
                <button
                  onClick={() => handleTemplateSelect('sample4')}
                  disabled={activeTemplate === 'sample4'}
                  className={`w-full mt-2 px-3 py-2 rounded-lg text-sm font-bold transition-all ${
                    activeTemplate === 'sample4' 
                      ? 'bg-amber-200 text-amber-800 cursor-not-allowed' 
                      : 'bg-amber-600 text-white hover:bg-amber-700'
                  }`}
                >
                  {activeTemplate === 'sample4' ? '✓ Currently Active' : 'Set as Active'}
                </button>
              </div>
              <div className={`border-2 rounded-2xl p-3 md:p-4 transition-all ${
                  activeTemplate === 'sample5' ? 'border-pink-600 bg-pink-100 ring-2 ring-pink-400' : 'border-pink-200 bg-pink-50'
                }`}
              >
                <div 
                  onClick={() => { 
                    setPreviewTemplate('sample5'); 
                    setShowTemplatePreview(true); 
                  }}
                  className="cursor-pointer hover:opacity-80 transition-opacity"
                >
                  {renderTemplateCardThumbnail('sample5')}
                  <div className="mb-1.5 flex items-start justify-between gap-2">
                    <p className="font-bold text-pink-900 text-sm md:text-base">📄 Sample 5</p>
                    {activeTemplate === 'sample5' && <span className="shrink-0 rounded-full bg-pink-600 px-2 py-1 text-[10px] font-bold text-white">ACTIVE</span>}
                  </div>
                  <p className="mb-2 text-[11px] leading-5 text-pink-700 md:text-xs">Traditional style with signature blocks and official formatting</p>
                </div>
                <button
                  onClick={() => handleTemplateSelect('sample5')}
                  disabled={activeTemplate === 'sample5'}
                  className={`w-full mt-2 px-3 py-2 rounded-lg text-sm font-bold transition-all ${
                    activeTemplate === 'sample5' 
                      ? 'bg-pink-200 text-pink-800 cursor-not-allowed' 
                      : 'bg-pink-600 text-white hover:bg-pink-700'
                  }`}
                >
                  {activeTemplate === 'sample5' ? '✓ Currently Active' : 'Set as Active'}
                </button>
              </div>
              <div className={`border-2 rounded-2xl p-3 md:p-4 transition-all ${
                  activeTemplate === 'sample6' || activeTemplate === 'classic_traditional'
                    ? 'border-slate-700 bg-slate-100 ring-2 ring-slate-400'
                    : 'border-slate-300 bg-slate-50'
                }`}
              >
                <div
                  onClick={() => {
                    setPreviewTemplate('sample6');
                    setShowTemplatePreview(true);
                  }}
                  className="cursor-pointer hover:opacity-80 transition-opacity"
                >
                  {renderTemplateCardThumbnail('sample6')}
                  <div className="mb-1.5 flex items-start justify-between gap-2">
                    <p className="font-bold text-slate-900 text-sm md:text-base">📄 Sample 6</p>
                    {(activeTemplate === 'sample6' || activeTemplate === 'classic_traditional') && <span className="shrink-0 rounded-full bg-slate-700 px-2 py-1 text-[10px] font-bold text-white">ACTIVE</span>}
                  </div>
                  <p className="mb-2 text-[11px] leading-5 text-slate-700 md:text-xs">Classic terminal report layout with formal summary blocks and signature-ready structure</p>
                </div>
                <button
                  onClick={() => handleTemplateSelect('sample6')}
                  disabled={activeTemplate === 'sample6' || activeTemplate === 'classic_traditional'}
                  className={`w-full mt-2 px-3 py-2 rounded-lg text-sm font-bold transition-all ${
                    activeTemplate === 'sample6' || activeTemplate === 'classic_traditional'
                      ? 'bg-slate-200 text-slate-700 cursor-not-allowed'
                      : 'bg-slate-700 text-white hover:bg-slate-800'
                  }`}
                >
                  {activeTemplate === 'sample6' || activeTemplate === 'classic_traditional' ? '✓ Currently Active' : 'Set as Active'}
                </button>
              </div>
            </div>

            {/* Custom template indicator (for uploaded HTML) */}
            {activeTemplate && !['sample1','sample2','sample3','sample4','sample5','sample6','gradman_v1','parent_focus','progress_insights','compact_clear','guardian_narrative','classic_traditional'].includes(activeTemplate) && (
              <div className="mt-4 p-4 border rounded-lg bg-indigo-50 border-indigo-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-bold text-indigo-700">📦 Uploaded Custom Template</p>
                    <p className="text-xs text-indigo-600">Active template ID: {activeTemplate}</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => { setPreviewTemplate('custom'); setShowTemplatePreview(true); }}
                      className="px-3 py-1 text-xs font-bold rounded bg-indigo-600 text-white hover:bg-indigo-700"
                    >
                      Preview
                    </button>
                    <button
                      type="button"
                      disabled
                      className="px-3 py-1 text-xs font-bold rounded bg-gray-300 text-gray-500 cursor-not-allowed"
                    >
                      Active
                    </button>
                  </div>
                </div>
              </div>
            )}

            <p className="text-xs text-slate-500 mt-4">💡 Click template to preview • Click "Set as Active" button to activate</p>
          </div>
        </div>
      </div>

      {/* Custom HTML Template Upload - School OS Plus Only */}
      {subscriptionPlan === 'Premium' && (
        <div className="mt-10 border-t pt-8">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-xl font-bold text-slate-800">🎨 Custom HTML Report Templates</h3>
            <span className="text-xs bg-linear-to-r from-yellow-400 to-amber-500 text-white px-3 py-1 rounded-full font-bold">SCHOOL OS PLUS</span>
          </div>
          <p className="text-sm text-slate-600 mb-6">
            Upload your own custom HTML templates to completely customize how terminal reports look. You can provide HTML, CSS, and background images.
          </p>

          <form onSubmit={handleCustomTemplateUpload} className="space-y-4">
            {templateMessage && (
              <div className={`p-3 rounded-lg ${
                templateMessage.includes('✅') ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'
              }`}>
                {templateMessage}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-bold text-slate-700 mb-2">Template Name (Optional)</label>
                <input
                  type="text"
                  value={customTemplateUpload.templateName}
                  onChange={(e) => setCustomTemplateUpload({ ...customTemplateUpload, templateName: e.target.value })}
                  placeholder="e.g., My Custom Template v1"
                  className="w-full p-3 border rounded-lg bg-slate-50"
                />
                <p className="text-xs text-slate-500 mt-1">Leave blank for auto-generated name</p>
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-700 mb-2">HTML File *</label>
                <input
                  type="file"
                  accept=".html"
                  onChange={(e) => setCustomTemplateUpload({ ...customTemplateUpload, htmlFile: e.target.files?.[0] || null })}
                  className="w-full p-3 border rounded-lg bg-slate-50"
                  required
                />
                <p className="text-xs text-slate-500 mt-1">Required. Your custom report template HTML</p>
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-700 mb-2">CSS File (Optional)</label>
                <input
                  type="file"
                  accept=".css"
                  onChange={(e) => setCustomTemplateUpload({ ...customTemplateUpload, cssFile: e.target.files?.[0] || null })}
                  className="w-full p-3 border rounded-lg bg-slate-50"
                />
                <p className="text-xs text-slate-500 mt-1">Additional styling (optional)</p>
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-700 mb-2">Background Image (Optional)</label>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => setCustomTemplateUpload({ ...customTemplateUpload, backgroundImage: e.target.files?.[0] || null })}
                  className="w-full p-3 border rounded-lg bg-slate-50"
                />
                <p className="text-xs text-slate-500 mt-1">Image file (PNG, JPG, etc.)</p>
              </div>
            </div>

            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm font-bold text-slate-800 mb-2">📝 HTML Template Tips:</p>
              <ul className="text-xs text-slate-700 space-y-1 ml-4 list-disc">
                <li>
                  Use placeholder variables like{' '}
                  <code className="bg-slate-200 px-1 rounded">{'{{student_name}}'}</code>,{' '}
                  <code className="bg-slate-200 px-1 rounded">{'{{school_name}}'}</code>,{' '}
                  <code className="bg-slate-200 px-1 rounded">{'{{total_score}}'}</code>
                </li>
                <li>Include <code className="bg-slate-200 px-1 rounded">@media print</code> for print-friendly styling</li>
                <li>Use inline CSS or link to external resources</li>
                <li>Template should be a complete HTML5 document</li>
              </ul>
            </div>

            <button
              type="submit"
              disabled={uploadingTemplate}
              className="w-full px-6 py-3 bg-linear-to-r from-purple-600 to-purple-700 text-white font-bold rounded-lg hover:from-purple-700 hover:to-purple-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploadingTemplate ? '⏳ Uploading...' : '📤 Upload Custom Template'}
            </button>
          </form>
        </div>
      )}

      <div className="mt-10 border-t pt-8">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-xl font-bold text-slate-800">Template Version History</h3>
            <p className="text-sm text-slate-600">Every activation, upload, and restore is kept as a recoverable snapshot for your school.</p>
          </div>
          <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-bold text-white">
            {templateHistory.length} snapshot{templateHistory.length === 1 ? '' : 's'}
          </span>
        </div>

        <div className="space-y-3">
          {templateHistory.length === 0 ? (
            <p className="text-sm text-slate-500">No template history has been recorded yet.</p>
          ) : (
            <>
              <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-bold uppercase tracking-wide text-slate-600">Snapshot Preview</p>
                {selectedTemplateHistoryItem ? (
                  templateHistoryPreview.length === 0 ? (
                    <p className="mt-2 text-sm text-slate-500">This snapshot matches the active template.</p>
                  ) : (
                    <div className="mt-2 space-y-1">
                      {templateHistoryPreview.map((line) => (
                        <p key={line} className="text-sm text-slate-600">{line}</p>
                      ))}
                    </div>
                  )
                ) : (
                  <p className="mt-2 text-sm text-slate-500">Choose a template snapshot to preview the restore impact.</p>
                )}
              </div>

              {templateHistory.map((item) => (
              <div key={item.snapshot_id} className={`rounded-xl border bg-white p-4 ${selectedTemplateHistorySnapshotId === item.snapshot_id ? 'border-blue-300 bg-blue-50/40' : 'border-slate-200'}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-bold text-slate-800">{item.report_template_id}</p>
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-bold uppercase tracking-wide text-slate-700">{TEMPLATE_HISTORY_ACTION_LABELS[item.action] || item.action}</span>
                      {item.is_current && (
                        <span className="rounded-full bg-emerald-100 px-2 py-1 text-[11px] font-bold uppercase tracking-wide text-emerald-800">Active Template</span>
                      )}
                      {item.has_custom_html && (
                        <span className="rounded-full bg-indigo-100 px-2 py-1 text-[11px] font-bold uppercase tracking-wide text-indigo-800">Custom HTML</span>
                      )}
                      {item.has_custom_css && (
                        <span className="rounded-full bg-violet-100 px-2 py-1 text-[11px] font-bold uppercase tracking-wide text-violet-800">Custom CSS</span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {item.created_at ? new Date(item.created_at).toLocaleString() : 'Recently'}
                      {item.actor_name ? ` • by ${item.actor_name}` : ''}
                    </p>
                    {item.restored_from_snapshot_id && (
                      <p className="mt-1 text-[11px] uppercase tracking-wide text-slate-400">Restored from {item.restored_from_snapshot_id}</p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedTemplateHistorySnapshotId(item.snapshot_id)}
                      className="px-3 py-2 text-xs font-bold rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
                    >
                      {selectedTemplateHistorySnapshotId === item.snapshot_id ? 'Previewing' : 'Preview Diff'}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleTemplateHistoryDownload(item.snapshot_id, `${item.report_template_id || item.snapshot_id}.json`)}
                      className="px-3 py-2 text-xs font-bold rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
                    >
                      Download
                    </button>
                    <button
                      type="button"
                      onClick={() => handleTemplateHistoryRestore(item.snapshot_id)}
                      disabled={item.is_current || templateHistoryBusyId === item.snapshot_id}
                      className="px-3 py-2 text-xs font-bold rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {templateHistoryBusyId === item.snapshot_id ? 'Restoring...' : item.is_current ? 'Current' : 'Restore'}
                    </button>
                  </div>
                </div>
              </div>
            ))}
            </>
          )}
        </div>
      </div>

      {/* School OS Plus Upsell for Free/Basic Tiers */}
      {subscriptionPlan !== 'Premium' && (
        <div className="mt-10 border-t pt-8">
          <div className="bg-linear-to-r from-purple-50 to-pink-50 border-2 border-purple-200 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="text-4xl">🎨</div>
              <div>
                <h3 className="text-lg font-bold text-slate-800 mb-2">Custom HTML Templates - School OS Plus Feature</h3>
                <p className="text-sm text-slate-700 mb-3">
                  Unlock the ability to upload and use your own custom HTML-based report templates with School OS Plus. Perfect for schools that want complete control over their report card design.
                </p>
                <button
                  onClick={() => alert('Upgrade to School OS Plus to access Custom HTML Templates!')}
                  className="px-6 py-2 bg-linear-to-r from-purple-600 to-pink-600 text-white font-bold rounded-lg hover:from-purple-700 hover:to-pink-700 transition-all"
                >
                  🚀 Upgrade to School OS Plus
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="mt-10 border-t pt-8">
        <h3 className="text-xl font-bold text-slate-800 mb-4">Grading Scheme Configuration</h3>
        <p className="text-sm text-slate-600 mb-4">
          Configure how class work and exam scores are weighted. The two values must add up to 100.
        </p>
        
        <div className="space-y-4">
          {/* Quick Presets */}
          <div className="flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => handleGradingSchemePreset('30/70')}
              className={`px-4 py-2 rounded-lg font-semibold ${
                classScoreMax === 30 && examScoreMax === 70
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              30/70 (Traditional)
            </button>
            <button
              type="button"
              onClick={() => handleGradingSchemePreset('40/60')}
              className={`px-4 py-2 rounded-lg font-semibold ${
                classScoreMax === 40 && examScoreMax === 60
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              40/60 (Balanced)
            </button>
            <button
              type="button"
              onClick={() => handleGradingSchemePreset('50/50')}
              className={`px-4 py-2 rounded-lg font-semibold ${
                classScoreMax === 50 && examScoreMax === 50
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              50/50 (Equal)
            </button>
          </div>

          {/* Custom Configuration */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">
                Class Score Maximum
              </label>
              <input
                type="number"
                min="0"
                max="100"
                value={classScoreMax}
                onChange={(e) => {
                  const val = parseInt(e.target.value) || 0;
                  setClassScoreMax(val);
                  setExamScoreMax(100 - val);
                }}
                className="w-full p-3 border rounded-lg bg-slate-50 font-mono text-lg"
              />
            </div>
            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">
                Exam Score Maximum
              </label>
              <input
                type="number"
                min="0"
                max="100"
                value={examScoreMax}
                onChange={(e) => {
                  const val = parseInt(e.target.value) || 0;
                  setExamScoreMax(val);
                  setClassScoreMax(100 - val);
                }}
                className="w-full p-3 border rounded-lg bg-slate-50 font-mono text-lg"
              />
            </div>
          </div>

          {/* Preview */}
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm font-semibold text-slate-700">
              Current Scheme: <span className="text-blue-700 text-xl font-mono">{classScoreMax}/{examScoreMax}</span>
            </p>
            <p className="text-xs text-slate-600 mt-1">
              Class work: 0-{classScoreMax} points • Exam: 0-{examScoreMax} points • Total: 100 points
            </p>
          </div>

          <button
            type="button"
            onClick={handleGradingSchemeSave}
            className="bg-green-700 text-white px-6 py-2 rounded-lg font-bold hover:bg-green-600"
          >
            Save Grading Scheme
          </button>

          {gradingSchemeStatus && (
            <p className={`text-sm ${gradingSchemeStatus.includes('Error') ? 'text-red-600' : 'text-green-600'}`}>
              {gradingSchemeStatus}
            </p>
          )}
        </div>
      </div>

      <TermManagementPanel />

      <div className="mt-10">
        <TimetableManager title="Timetable Management" scope="school" canManage />
      </div>

      {/* Template Preview Modal */}
      {showTemplatePreview && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setShowTemplatePreview(false)}>
          <div className="bg-white rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-white border-b p-4 flex justify-between items-center z-10">
              <h3 className="text-xl font-bold text-slate-800">
                {previewTemplate === 'sample1' && '📄 Sample 1 - Professional Layout'}
                {previewTemplate === 'sample2' && '📄 Sample 2 - Compact Format'}
                {previewTemplate === 'sample3' && '📄 Sample 3 - Modern Design'}
                {previewTemplate === 'sample4' && '📄 Sample 4 - Detailed Narrative'}
                {previewTemplate === 'sample5' && '📄 Sample 5 - Traditional Style'}
                {previewTemplate === 'sample6' && '📄 Sample 6 - Classic Terminal Report'}
                {previewTemplate === 'custom' && '📄 Custom Uploaded Template'}
              </h3>
              <button 
                onClick={() => setShowTemplatePreview(false)}
                className="text-slate-500 hover:text-slate-700 text-2xl font-bold"
              >
                ×
              </button>
            </div>
            
            <div className="p-8 bg-gray-50">
              {previewTemplate === 'sample6' && (
                <div className="mb-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-bold text-slate-800 mb-2">Auto-filled by the system when grades are finalized</p>
                  <div className="flex flex-wrap gap-2 text-xs text-slate-700">
                    {['School name', 'Student name', 'Student code', 'Class', 'Academic term', 'Academic year', 'Subject scores', 'Grades', 'Term average', 'Class position', 'Attendance %', 'Total attendance', 'Next term reopen date'].map((item) => (
                      <span key={item} className="rounded-full bg-white px-3 py-1 border border-slate-200">{item}</span>
                    ))}
                  </div>
                  <p className="mt-3 text-xs text-slate-500">Usually still entered manually: conduct, attitude, interest, teacher remarks, academic remark, promotion decision, and signature blocks unless already stored in the report workflow.</p>
                </div>
              )}

              {/* Custom Review for Uploaded Template */}
              {previewTemplate === 'custom' ? (
                <div className="bg-white p-4 shadow-lg" style={{ minHeight: '600px' }}>
                  <iframe
                    title="Custom Template Preview"
                    style={{ width: '100%', minHeight: '650px', border: '1px solid #d1d5db' }}
                    srcDoc={getCustomTemplateSrcDoc()}
                  />
                </div>
              ) : previewTemplateHtml ? (
                <div className="bg-white p-4 shadow-lg" style={{ minHeight: '600px' }}>
                  <div
                    className="report-template-preview"
                    dangerouslySetInnerHTML={{ __html: previewTemplateHtml }}
                  />
                </div>
              ) : previewTemplateSectionConfig?.sections?.length ? (
                <div className={previewTheme.modalCanvas} style={{ minHeight: '600px' }}>
                  <div className={previewTheme.sectionGap}>
                    {previewTemplateSectionConfig.sections.map((section) => renderPreviewSection(section))}
                  </div>
                </div>
              ) : (
                <div className="bg-white p-8 shadow-lg" style={{ minHeight: '500px' }}>
                  {/* Header */}
                  <div className="text-center mb-6 border-b-4 border-blue-800 pb-4">
                    <div className="mb-2">
                      <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center text-3xl mx-auto">
                        🏫
                      </div>
                    </div>
                    <h1 className="text-3xl font-bold text-blue-900 uppercase">{settings.school_name || 'SAMPLE SCHOOL NAME'}</h1>
                    <p className="text-sm italic text-gray-600 mt-1">{settings.school_motto || 'Excellence in Education'}</p>
                    <p className="text-xs text-gray-500 mt-2">
                      {settings.school_email || 'info@school.edu'} | {settings.school_phone || '+233 XX XXX XXXX'}
                    </p>
                  </div>

                  {/* Report Title */}
                  <div className="text-center mb-4">
                    <h2 className="text-xl font-bold text-slate-800 uppercase">Terminal Report Card</h2>
                    <p className="text-sm text-slate-600">Academic Year: 2024/2025 - Term 1</p>
                  </div>

                  {/* Student Information */}
                  <div className="grid grid-cols-2 gap-4 mb-6 p-4 bg-blue-50 rounded-lg">
                    <div>
                      <p className="text-xs text-slate-600">Student Name:</p>
                      <p className="font-bold text-slate-800">John Doe (Sample)</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-600">Student ID:</p>
                      <p className="font-bold text-slate-800">STU-2024-001</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-600">Class:</p>
                      <p className="font-bold text-slate-800">Grade 10A</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-600">Position:</p>
                      <p className="font-bold text-slate-800">2nd / 45</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-600">Next Term Reopens:</p>
                      <p className="font-bold text-slate-800">{previewReopeningDate}</p>
                    </div>
                  </div>

                  {/* Performance Summary */}
                  <div className="mb-6">
                  <h3 className="font-bold text-slate-700 mb-2 border-b pb-1">Academic Performance</h3>
                  <table className="w-full text-sm">
                    <thead className="bg-slate-100">
                      <tr>
                        <th className="p-2 text-left">Subject</th>
                        <th className="p-2 text-center">Class Work</th>
                        <th className="p-2 text-center">Exam</th>
                        <th className="p-2 text-center">Total</th>
                        <th className="p-2 text-center">Grade</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b">
                        <td className="p-2">Mathematics</td>
                        <td className="p-2 text-center">28/30</td>
                        <td className="p-2 text-center">65/70</td>
                        <td className="p-2 text-center font-bold">93/100</td>
                        <td className="p-2 text-center font-bold text-green-700">A</td>
                      </tr>
                      <tr className="border-b">
                        <td className="p-2">English Language</td>
                        <td className="p-2 text-center">26/30</td>
                        <td className="p-2 text-center">60/70</td>
                        <td className="p-2 text-center font-bold">86/100</td>
                        <td className="p-2 text-center font-bold text-green-700">A</td>
                      </tr>
                      <tr className="border-b">
                        <td className="p-2">Science</td>
                        <td className="p-2 text-center">25/30</td>
                        <td className="p-2 text-center">58/70</td>
                        <td className="p-2 text-center font-bold">83/100</td>
                        <td className="p-2 text-center font-bold text-blue-700">B</td>
                      </tr>
                    </tbody>
                  </table>
                  <div className="mt-2 p-2 bg-blue-50 rounded">
                    <p className="text-sm"><span className="font-bold">Overall Average:</span> 87.3%</p>
                  </div>
                </div>

                {/* Remarks Section */}
                <div className="space-y-3 mb-6">
                  <div className="p-3 bg-yellow-50 border-l-4 border-yellow-400 rounded">
                    <p className="text-xs font-bold text-slate-700 mb-1">Class Teacher's Remarks:</p>
                    <p className="text-sm text-slate-600 italic">John has shown excellent performance this term. Keep up the good work!</p>
                  </div>
                  
                  <div className="p-3 bg-orange-50 border-l-4 border-orange-400 rounded">
                    <p className="text-xs font-bold text-slate-700 mb-1">Headmaster's Remarks:</p>
                    <p className="text-sm text-slate-600 italic">Outstanding academic achievement. Continue to strive for excellence.</p>
                  </div>
                  
                  <div className="p-3 bg-cyan-50 border-l-4 border-cyan-400 rounded">
                    <p className="text-xs font-bold text-slate-700 mb-1">Proprietor's Remarks:</p>
                    <p className="text-sm text-slate-600 italic">A model student. Well done!</p>
                  </div>
                </div>

                {/* Signatures */}
                <div className="grid grid-cols-3 gap-4 mt-8 pt-4 border-t">
                  <div className="text-center">
                    <div className="border-t border-slate-400 pt-1 mt-8">
                      <p className="text-xs font-bold">Class Teacher</p>
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="border-t border-slate-400 pt-1 mt-8">
                      <p className="text-xs font-bold">Headmaster</p>
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="border-t border-slate-400 pt-1 mt-8">
                      <p className="text-xs font-bold">Proprietor</p>
                    </div>
                  </div>
                </div>

                {/* Footer */}
                <div className="mt-6 text-center text-xs text-slate-500">
                  <p>Generated on {new Date().toLocaleDateString()}</p>
                </div>
              </div>
              )}
            </div>

            <div className="sticky bottom-0 bg-white border-t p-4">
                <button
                  onClick={() => setShowTemplatePreview(false)}
                  className="w-full bg-blue-600 text-white px-6 py-3 rounded-lg font-bold hover:bg-blue-700"
                >
                  Close Preview
                </button>
              </div>
            </div>
          </div>
        )}
    </div>
    </>
  );
 }