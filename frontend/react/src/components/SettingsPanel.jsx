import React, { useState, useEffect } from 'react';
import axios from 'axios';
import TimetableManager from './TimetableManager';
import TermManagementPanel from './TermManagementPanel';

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
    country_code: 'GH',
    anniversary_date: ''
  });
  const [fees, setFees] = useState({
    tuition_fee: 0,
    feeding_fee: 0,
    transport_fee: 0,
    terminal_report_fee: 0,
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
  const [customTemplateUpload, setCustomTemplateUpload] = useState({
    templateName: '',
    htmlFile: null,
    cssFile: null,
    backgroundImage: null
  });
  const [uploadingTemplate, setUploadingTemplate] = useState(false);
  const [subscriptionPlan, setSubscriptionPlan] = useState('');
  const [paystackProviders, setPaystackProviders] = useState([]);
  const [paystackRoutes, setPaystackRoutes] = useState([]);
  const [loadingPaystackProviders, setLoadingPaystackProviders] = useState(false);
  const [loadingPaystackRoutes, setLoadingPaystackRoutes] = useState(false);
  const [creatingPaystackRoute, setCreatingPaystackRoute] = useState(false);
  const [resolvingPaystackCustomer, setResolvingPaystackCustomer] = useState(false);
  const [paystackProviderError, setPaystackProviderError] = useState('');
  const [paystackRouteMessage, setPaystackRouteMessage] = useState('');
  const [paystackRouteForm, setPaystackRouteForm] = useState({
    payment_type: 'Tuition',
    customer_code: '',
    preferred_bank: ''
  });

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
      anniversary_date: branding.anniversary_date || prev.anniversary_date || ''
    }));

    // Get subscription plan from backend to ensure it's always up-to-date
    const fetchSubscriptionPlan = async () => {
      try {
        const headers = {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'X-School-ID': localStorage.getItem('school_id')
        };
        const res = await axios.get('/api/school/profile', { headers });
        const planFromServer = res.data.subscription_plan || localStorage.getItem('subscription_plan') || 'Free Tier';
        setSubscriptionPlan(planFromServer);
        // Update localStorage with latest plan
        localStorage.setItem('subscription_plan', planFromServer);
      } catch (err) {
        console.error('Failed to load subscription plan:', err);
        // Fallback to localStorage
        const plan = localStorage.getItem('subscription_plan') || 'Free Tier';
        setSubscriptionPlan(plan);
      }
    };
    
    fetchSubscriptionPlan();

    const fetchSchoolSettings = async () => {
      try {
        const headers = {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'X-School-ID': localStorage.getItem('school_id')
        };
        const res = await axios.get('/api/school/settings', { headers });
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
          country_code: data.country_code || prev.country_code,
          anniversary_date: data.anniversary_date || prev.anniversary_date,
        }));
      } catch (err) {
        console.error('Failed to load school settings:', err);
      }
    };


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
          tuition_fee: res.data.tuition_fee || 0,
          feeding_fee: res.data.feeding_fee || 0,
          transport_fee: res.data.transport_fee || 0,
          terminal_report_fee: res.data.terminal_report_fee || 0,
          other_fees: res.data.other_fees || {}
        });
      } catch (err) {
        console.error('Failed to load fees');
      }
    };

    
    fetchSchoolSettings();
    fetchGradingScheme();
    fetchFees();
    fetchActiveTemplate();
    fetchPaystackProviders();
    fetchPaystackRoutes();
  }, []);

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id')
  });

  const fetchPaystackProviders = async () => {
    setLoadingPaystackProviders(true);
    setPaystackProviderError('');
    try {
      const headers = getAuthHeaders();
      const res = await axios.get('/api/proprietor/paystack/providers?country=ghana', { headers });
      const providers = Array.isArray(res.data)
        ? res.data
        : Array.isArray(res.data?.providers)
          ? res.data.providers
          : [];
      setPaystackProviders(providers);
      if (res.data?.warning) {
        setPaystackProviderError(`⚠️ ${res.data.warning}`);
      }
      if (!paystackRouteForm.preferred_bank && providers.length > 0) {
        const defaultProvider = providers[0]?.slug || providers[0]?.name || '';
        setPaystackRouteForm((prev) => ({ ...prev, preferred_bank: defaultProvider }));
      }
    } catch (err) {
      const error = err.response?.data?.error || err.response?.data?.message || 'Failed to load supported providers';
      setPaystackProviderError(error);
    } finally {
      setLoadingPaystackProviders(false);
    }
  };

  const fetchPaystackRoutes = async () => {
    setLoadingPaystackRoutes(true);
    try {
      const headers = getAuthHeaders();
      const res = await axios.get('/api/proprietor/paystack/subaccounts', { headers });
      setPaystackRoutes(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to load Paystack routes:', err);
      setPaystackRoutes([]);
    } finally {
      setLoadingPaystackRoutes(false);
    }
  };

  const handleAutofillPaystackCustomerCode = async () => {
    setResolvingPaystackCustomer(true);
    setPaystackRouteMessage('');
    try {
      const headers = getAuthHeaders();
      const res = await axios.post('/api/proprietor/paystack/customers/resolve', {}, { headers });
      const customerCode = res.data?.customer_code || '';
      if (!customerCode) {
        setPaystackRouteMessage('❌ Could not resolve a Paystack customer code.');
        return;
      }

      setPaystackRouteForm((prev) => ({ ...prev, customer_code: customerCode }));
      setPaystackRouteMessage(`✅ Customer code auto-filled: ${customerCode}`);
    } catch (err) {
      const error = err.response?.data?.error || err.response?.data?.message || 'Failed to auto-fill customer code';
      setPaystackRouteMessage(`❌ ${error}`);
    } finally {
      setResolvingPaystackCustomer(false);
    }
  };

  const handleCreatePaystackRoute = async () => {
    const fallbackProvider = paystackRouteForm.preferred_bank?.trim() || 'titan-paystack';

    setCreatingPaystackRoute(true);
    setPaystackRouteMessage('');
    try {
      const headers = getAuthHeaders();
      const payload = {
        payment_type: paystackRouteForm.payment_type,
        customer_code: paystackRouteForm.customer_code?.trim() || undefined,
        preferred_bank: fallbackProvider
      };

      const res = await axios.post('/api/proprietor/paystack/subaccounts/create', payload, { headers });
      if (res.data?.mode === 'manual_fallback') {
        setPaystackRouteMessage(`⚠️ ${res.data?.message || 'Route created in fallback mode. Virtual account is not yet available.'}`);
      } else {
        setPaystackRouteMessage(`✅ ${res.data?.message || 'Virtual account created successfully.'}`);
      }
      await fetchPaystackRoutes();
    } catch (err) {
      const error = err.response?.data?.error || err.response?.data?.message || 'Failed to create virtual account route';
      setPaystackRouteMessage(`❌ ${error}`);
    } finally {
      setCreatingPaystackRoute(false);
    }
  };

  const fetchActiveTemplate = async () => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get('/api/school/template', { headers });
      setActiveTemplate(res.data.template_id || 'sample1');
      setActiveTemplateConfig(res.data.template_config || {});
    } catch (err) {
      console.error('Failed to load active template');
    }
  };

  const handleTemplateSelect = async (templateId) => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const response = await axios.post('/api/school/template', { template_id: templateId }, { headers });
      setActiveTemplate(templateId);
      setActiveTemplateConfig(response.data.template_config || activeTemplateConfig);
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
      alert('Custom HTML Templates are only available in Premium tier');
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

  const handleViewBankDetails = async () => {
    const pwd = prompt('Enter your password to view full bank details');
    if (!pwd) return;
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.post('/api/school/branding/bank/view', { password: pwd }, { headers });
      const data = res.data || {};
      setSettings((prev) => ({ ...prev, bank_name: data.bank_name, bank_account: data.bank_account, bank_account_name: data.bank_account_name, bank_branch: data.bank_branch }));
      setTemplateMessage('✅ Bank details revealed');
      setTimeout(() => setTemplateMessage(''), 3000);
    } catch (err) {
      setTemplateMessage(`❌ ${err.response?.data?.message || 'Unable to reveal bank details'}`);
      setTimeout(() => setTemplateMessage(''), 4000);
    }
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
      await axios.post('/api/school/settings', {
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
        bank_name: settings.bank_name,
        bank_account: settings.bank_account,
        bank_account_name: settings.bank_account_name,
        bank_branch: settings.bank_branch
      }, { headers });
      
      // Save fees separately
      await axios.post('/api/school/fees', {
        tuition_fee: fees.tuition_fee,
        feeding_fee: fees.feeding_fee,
        transport_fee: fees.transport_fee,
        terminal_report_fee: fees.terminal_report_fee,
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
        anniversary_date: settings.anniversary_date,
        bank_name: settings.bank_name,
        bank_account: settings.bank_account,
        bank_account_name: settings.bank_account_name,
        bank_branch: settings.bank_branch
      };
      localStorage.setItem('branding', JSON.stringify(newBranding));
      
      alert("Settings and fees updated! The page will reload to apply changes.");
      window.location.reload();
    } catch (err) {
      alert("Failed to update settings or fees.");
      console.error(err);
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

  const providerErrorLower = (paystackProviderError || '').toLowerCase();
  const hasProviderAuthIssue =
    providerErrorLower.includes('unauthorized') ||
    providerErrorLower.includes('paystack_secret_key') ||
    providerErrorLower.includes('invalid key') ||
    providerErrorLower.includes('forbidden') ||
    providerErrorLower.includes('permission');

  const paymentNetworkStatus = loadingPaystackProviders
    ? 'Checking'
    : paystackProviderError
      ? 'Temporary Fallback'
      : 'Active';

  const paymentNetworkBadgeClass = loadingPaystackProviders
    ? 'bg-slate-100 text-slate-700'
    : paystackProviderError
      ? 'bg-amber-100 text-amber-800'
      : 'bg-green-100 text-green-800';

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
          <p className="text-sm text-slate-600 mb-6">Parents pay via Paystack payment gateway. Bank account details below are optional for manual transfers. Leave empty if not needed.</p>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Bank Transfer Section */}
            <div className="border rounded-lg p-4 bg-green-50">
              <h4 className="font-bold text-slate-800 mb-3">🏦 Bank Account</h4>
              <div className="space-y-3">
                <div>
                  <label className="text-sm font-bold text-slate-700">Bank Name</label>
                  <div className="flex gap-2 items-center">
                    <input
                      type="text"
                      name="bank_name"
                      value={settings.bank_name || ''}
                      onChange={handleChange}
                      className="w-full p-2 border rounded mt-1 bg-white"
                      placeholder="e.g., Fidelity Bank Ghana"
                      disabled={typeof settings.bank_name === 'string' && settings.bank_name.includes('***')}
                    />
                    <button type="button" onClick={handleViewBankDetails} className="px-3 py-1 bg-indigo-600 text-white rounded text-sm">View</button>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700">Account Number</label>
                  <div className="flex gap-2 items-center">
                    <input
                      type="text"
                      name="bank_account"
                      value={settings.bank_account || ''}
                      onChange={handleChange}
                      className="w-full p-2 border rounded mt-1 bg-white"
                      placeholder="School bank account number"
                      disabled={typeof settings.bank_account === 'string' && settings.bank_account.startsWith('****')}
                    />
                    <button type="button" onClick={handleViewBankDetails} className="px-3 py-1 bg-indigo-600 text-white rounded text-sm">View</button>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700">Account Holder Name</label>
                  <div className="flex gap-2 items-center">
                    <input
                      type="text"
                      name="bank_account_name"
                      value={settings.bank_account_name || ''}
                      onChange={handleChange}
                      className="w-full p-2 border rounded mt-1 bg-white"
                      placeholder="Name on bank account"
                      disabled={typeof settings.bank_account_name === 'string' && settings.bank_account_name.includes('***')}
                    />
                    <button type="button" onClick={handleViewBankDetails} className="px-3 py-1 bg-indigo-600 text-white rounded text-sm">View</button>
                  </div>
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
                  />
                </div>
              </div>
            </div>

            {/* Paystack Dedicated Virtual Accounts */}
            <div className="border rounded-lg p-4 bg-blue-50">
              <h4 className="font-bold text-slate-800 mb-2">🧾 Paystack Virtual Accounts</h4>
              <p className="text-xs text-slate-600 mb-3">
                Create one dedicated virtual account per fee type. Parents can transfer to these account numbers directly.
              </p>

              <div className="space-y-3">
                <div>
                  <label className="text-sm font-bold text-slate-700">Payment Type</label>
                  <select
                    value={paystackRouteForm.payment_type}
                    onChange={(e) => setPaystackRouteForm((prev) => ({ ...prev, payment_type: e.target.value }))}
                    className="w-full p-2 border rounded mt-1 bg-white"
                  >
                    <option value="Tuition">Tuition</option>
                    <option value="Feeding">Feeding</option>
                    <option value="Uniform">Uniform</option>
                    <option value="Transport">Transport</option>
                    <option value="Other">Other</option>
                  </select>
                </div>

                <div className="bg-slate-50 border border-slate-200 rounded p-2">
                  <p className="text-xs text-slate-600">
                    Customer profile is handled automatically by the system. No extra configuration is required.
                  </p>
                </div>

                <div>
                  <label className="text-sm font-bold text-slate-700">Supported Provider / Bank</label>
                  <select
                    value={paystackRouteForm.preferred_bank}
                    onChange={(e) => setPaystackRouteForm((prev) => ({ ...prev, preferred_bank: e.target.value }))}
                    className="w-full p-2 border rounded mt-1 bg-white"
                    disabled={loadingPaystackProviders}
                  >
                    {!loadingPaystackProviders && paystackProviders.length === 0 && (
                      <option value="">No providers loaded</option>
                    )}
                    {paystackProviders.map((provider, idx) => (
                      <option
                        key={`${provider.slug || provider.name || 'provider'}-${idx}`}
                        value={provider.slug || provider.name || ''}
                      >
                        {provider.name || provider.slug || 'Unknown Provider'}
                        {provider.slug ? ` (${provider.slug})` : ''}
                      </option>
                    ))}
                  </select>
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      onClick={fetchPaystackProviders}
                      className="px-3 py-1 text-xs font-bold rounded bg-slate-700 text-white hover:bg-slate-600"
                    >
                      {loadingPaystackProviders ? 'Refreshing...' : 'Refresh Providers'}
                    </button>
                    <button
                      type="button"
                      onClick={handleCreatePaystackRoute}
                      disabled={creatingPaystackRoute}
                      className="px-3 py-1 text-xs font-bold rounded bg-blue-700 text-white hover:bg-blue-600 disabled:opacity-50"
                    >
                      {creatingPaystackRoute ? 'Creating...' : 'Create Virtual Account'}
                    </button>
                  </div>
                  {paystackProviderError && (
                    <div className={`mt-2 rounded border p-2 text-xs ${paystackProviderError.startsWith('⚠️') ? 'border-amber-300 bg-amber-50 text-amber-800' : 'border-red-300 bg-red-50 text-red-700'}`}>
                      <p className="font-semibold">{paystackProviderError.startsWith('⚠️') ? paystackProviderError : `❌ ${paystackProviderError}`}</p>
                      {hasProviderAuthIssue && (
                        <ul className="mt-2 list-disc pl-4 space-y-1">
                          <li>Payment network is temporarily unavailable.</li>
                          <li>You can still create routes and continue operations.</li>
                          <li>Parents can pay using the school bank account while setup completes.</li>
                          <li>If this continues, contact platform support.</li>
                        </ul>
                      )}
                    </div>
                  )}
                  {paystackRouteMessage && (
                    <p className={`text-xs mt-2 ${paystackRouteMessage.startsWith('✅') ? 'text-green-700' : 'text-red-600'}`}>
                      {paystackRouteMessage}
                    </p>
                  )}
                </div>

                <div className="pt-2 border-t">
                  <p className="text-sm font-bold text-slate-700 mb-2">Configured Virtual Routes</p>
                  <p className="text-xs text-slate-500 mb-2">
                    Status: <span className="font-semibold text-green-700">Virtual Account Ready</span> (real account number available) or <span className="font-semibold text-amber-700">Fallback Mode</span> (manual route while gateway setup completes).
                  </p>
                  {loadingPaystackRoutes ? (
                    <p className="text-xs text-slate-500">Loading routes...</p>
                  ) : paystackRoutes.length === 0 ? (
                    <p className="text-xs text-slate-500">No virtual routes created yet.</p>
                  ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                      {paystackRoutes
                        .filter((route) => route.is_active)
                        .map((route) => {
                          const isFallbackMode = !route.virtual_bank_account || (route.subaccount_code || '').startsWith('MANUAL_');

                          return (
                            <div key={route.id} className="bg-white border rounded p-2 text-xs">
                              <div className="flex items-center justify-between gap-2 mb-1">
                                <p className="font-bold text-slate-700">{route.payment_type}</p>
                                <span
                                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                    isFallbackMode
                                      ? 'bg-amber-100 text-amber-800 border border-amber-300'
                                      : 'bg-green-100 text-green-800 border border-green-300'
                                  }`}
                                >
                                  {isFallbackMode ? 'Fallback Mode' : 'Virtual Account Ready'}
                                </span>
                              </div>
                              <p className="text-slate-600">Acct: {route.virtual_bank_account || 'Not set'}</p>
                              <p className="text-slate-600">Bank: {route.virtual_bank_name || route.momo_provider || 'Not set'}</p>
                            </div>
                          );
                        })}
                    </div>
                  )}
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
              <label className="block text-sm font-bold text-slate-700 mb-2">Feeding Fee (Daily/Monthly)</label>
              <div className="flex items-center gap-2">
                <span className="text-slate-600 font-semibold">GH₵</span>
                <input
                  type="number"
                  value={fees.feeding_fee}
                  onChange={(e) => setFees((prev) => ({ ...prev, feeding_fee: parseFloat(e.target.value) || 0 }))}
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
          </div>

          {/* Other Fees Section */}
          <div className="mt-6 p-4 bg-slate-50 rounded-lg border border-slate-200">
            <p className="text-sm font-bold text-slate-700 mb-3">📌 Additional Fees (e.g., Sports, Library, Activities)</p>
            <div className="space-y-3">
              {Object.entries(fees.other_fees).map(([feeName, amount]) => (
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
                <p className="text-lg font-bold text-slate-800">GH₵ {fees.tuition_fee.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-slate-600">Feeding</p>
                <p className="text-lg font-bold text-slate-800">GH₵ {fees.feeding_fee.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-slate-600">Transport</p>
                <p className="text-lg font-bold text-slate-800">GH₵ {fees.transport_fee.toFixed(2)}</p>
              </div>
              {Object.entries(fees.other_fees).map(([name, amount]) => (
                <div key={name}>
                  <p className="text-slate-600">{name}</p>
                  <p className="text-lg font-bold text-slate-800">GH₵ {amount.toFixed(2)}</p>
                </div>
              ))}
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
            This will save school branding, contact details, and fee configuration. The page will reload to apply changes.
          </p>
        </div>
      </form>

      <div className="mt-10 border-t pt-8">
        <h3 className="text-xl font-bold text-slate-800 mb-4">📋 Terminal Report Templates</h3>
        <p className="text-sm text-slate-600 mb-4">
          Choose which template layout to use for terminal reports. Click a template to preview it, then click "Set as Active" to activate.
        </p>
        
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className={`border-2 rounded-2xl p-4 transition-all ${
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
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-bold text-blue-900">📄 Sample 1</p>
                    {activeTemplate === 'sample1' && <span className="text-xs bg-blue-600 text-white px-2 py-1 rounded-full">ACTIVE</span>}
                  </div>
                  <p className="text-xs text-blue-700 mb-3">Professional layout with centered header and detailed sections</p>
                </div>
                <button
                  onClick={() => handleTemplateSelect('sample1')}
                  disabled={activeTemplate === 'sample1'}
                  className={`w-full mt-2 px-3 py-2 rounded-lg text-sm font-bold transition-all ${
                    activeTemplate === 'sample1' 
                      ? 'bg-blue-200 text-blue-800 cursor-not-allowed' 
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}
                >
                  {activeTemplate === 'sample1' ? '✓ Currently Active' : 'Set as Active'}
                </button>
              </div>
              <div className={`border-2 rounded-2xl p-4 transition-all ${
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
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-bold text-green-900">📄 Sample 2</p>
                    {activeTemplate === 'sample2' && <span className="text-xs bg-green-600 text-white px-2 py-1 rounded-full">ACTIVE</span>}
                  </div>
                  <p className="text-xs text-green-700 mb-3">Compact single-page format with emphasis on grades</p>
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
              <div className={`border-2 rounded-2xl p-4 transition-all ${
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
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-bold text-purple-900">📄 Sample 3</p>
                    {activeTemplate === 'sample3' && <span className="text-xs bg-purple-600 text-white px-2 py-1 rounded-full">ACTIVE</span>}
                  </div>
                  <p className="text-xs text-purple-700 mb-3">Modern design with visual progress indicators</p>
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
              <div className={`border-2 rounded-2xl p-4 transition-all ${
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
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-bold text-amber-900">📄 Sample 4</p>
                    {activeTemplate === 'sample4' && <span className="text-xs bg-amber-600 text-white px-2 py-1 rounded-full">ACTIVE</span>}
                  </div>
                  <p className="text-xs text-amber-700 mb-3">Detailed narrative report with extensive remarks section</p>
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
              <div className={`border-2 rounded-2xl p-4 transition-all ${
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
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-bold text-pink-900">📄 Sample 5</p>
                    {activeTemplate === 'sample5' && <span className="text-xs bg-pink-600 text-white px-2 py-1 rounded-full">ACTIVE</span>}
                  </div>
                  <p className="text-xs text-pink-700 mb-3">Traditional style with signature blocks and official formatting</p>
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

      {/* Custom HTML Template Upload - Premium Only */}
      {subscriptionPlan === 'Premium' && (
        <div className="mt-10 border-t pt-8">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-xl font-bold text-slate-800">🎨 Custom HTML Report Templates</h3>
            <span className="text-xs bg-linear-to-r from-yellow-400 to-amber-500 text-white px-3 py-1 rounded-full font-bold">PREMIUM</span>
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

      {/* Premium Upsell for Free/Basic Tiers */}
      {subscriptionPlan !== 'Premium' && (
        <div className="mt-10 border-t pt-8">
          <div className="bg-linear-to-r from-purple-50 to-pink-50 border-2 border-purple-200 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="text-4xl">🎨</div>
              <div>
                <h3 className="text-lg font-bold text-slate-800 mb-2">Custom HTML Templates - Premium Feature</h3>
                <p className="text-sm text-slate-700 mb-3">
                  Unlock the ability to upload and use your own custom HTML-based report templates with the Premium tier. Perfect for schools that want complete control over their report card design.
                </p>
                <button
                  onClick={() => alert('Upgrade to Premium to access Custom HTML Templates!')}
                  className="px-6 py-2 bg-linear-to-r from-purple-600 to-pink-600 text-white font-bold rounded-lg hover:from-purple-700 hover:to-pink-700 transition-all"
                >
                  🚀 Upgrade to Premium
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
                    {['School name', 'Student name', 'Student code', 'Class', 'Academic term', 'Academic year', 'Subject scores', 'Grades', 'Term average', 'Class position', 'Attendance %', 'Total attendance'].map((item) => (
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