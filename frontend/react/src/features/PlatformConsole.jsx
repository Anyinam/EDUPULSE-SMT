import React, { useEffect, useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

const DEFAULT_PUBLIC_CONTENT = {
  faqs: [],
  tutorials: [],
  feature_guides: [],
  security_alerts: [],
  support: {
    email: 'support@edupulse.com',
    phone: '+233 552 141 384',
    website: '',
    response_time: 'within 24 hours on business days',
  },
  auth: {
    login_title: 'Welcome Back',
    login_subtitle: 'Enter your business credentials to access the dashboard.',
    register_title: 'Create Tenant',
    register_subtitle: 'Register your school organization.',
    register_support_note: 'Need help choosing a plan or completing registration?',
  },
  help_center: {
    title: 'Help Center',
    subtitle: 'Search FAQs, browse feature guides, and find tutorial updates.',
    security_title: 'Scam Alert',
    security_body: 'Protect your school accounts and payment setup. Verify suspicious contact before you share any sensitive information.',
  },
};

function SectionCard({ title, description, children }) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold text-gray-900">{title}</h2>
      {description ? <p className="text-sm text-gray-600 mt-1 mb-4">{description}</p> : null}
      {children}
    </div>
  );
}

export default function PlatformConsole() {
  const [token, setToken] = useState(localStorage.getItem('platform_token'));
  const [currentUser, setCurrentUser] = useState(null);
  const [activeTab, setActiveTab] = useState('public_content');
  const [needsBootstrap, setNeedsBootstrap] = useState(false);
  const [bootstrapChecked, setBootstrapChecked] = useState(false);

  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [bootstrapForm, setBootstrapForm] = useState({ ownerKey: '', username: '', email: '', password: '' });
  const [bootstrapError, setBootstrapError] = useState('');
  const [bootstrapSuccess, setBootstrapSuccess] = useState('');
  const [bootstrapLoading, setBootstrapLoading] = useState(false);

  const [publicContent, setPublicContent] = useState(DEFAULT_PUBLIC_CONTENT);
  const [publicContentLoading, setPublicContentLoading] = useState(false);
  const [publicContentError, setPublicContentError] = useState('');
  const [publicContentSuccess, setPublicContentSuccess] = useState('');

  const [chiefLibrary, setChiefLibrary] = useState({ subjects: [], meta: {} });
  const [chiefHistory, setChiefHistory] = useState([]);
  const [chiefText, setChiefText] = useState('');
  const [chiefFiles, setChiefFiles] = useState([]);
  const [chiefFileInputKey, setChiefFileInputKey] = useState(0);
  const [chiefReplaceExisting, setChiefReplaceExisting] = useState(true);
  const [chiefLoading, setChiefLoading] = useState(false);
  const [chiefError, setChiefError] = useState('');
  const [chiefSuccess, setChiefSuccess] = useState('');

  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState('');
  const [addUserForm, setAddUserForm] = useState({ username: '', email: '', password: '' });
  const [addUserError, setAddUserError] = useState('');
  const [emailTrace, setEmailTrace] = useState([]);
  const [emailTraceSummary, setEmailTraceSummary] = useState([]);
  const [emailTraceLoading, setEmailTraceLoading] = useState(false);
  const [emailTraceError, setEmailTraceError] = useState('');
  const [emailTraceSchoolFilter, setEmailTraceSchoolFilter] = useState('');

  const getPlatformHeaders = () => ({
    headers: { Authorization: `Bearer ${token}` },
  });

  useEffect(() => {
    if (!token) {
      fetchBootstrapStatus();
    }
  }, [token]);

  const fetchBootstrapStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/platform/bootstrap-status`);
      setNeedsBootstrap(Boolean(response.data?.needs_bootstrap));
    } catch (error) {
      setNeedsBootstrap(false);
    } finally {
      setBootstrapChecked(true);
    }
  };

  useEffect(() => {
    if (token) {
      fetchCurrentUser();
    }
  }, [token]);

  useEffect(() => {
    if (!token || !currentUser) {
      return;
    }

    if (activeTab === 'public_content') {
      fetchPublicContent();
      return;
    }

    if (activeTab === 'chief_examiner') {
      fetchChiefExaminerLibrary();
      return;
    }

    if (activeTab === 'users' && users.length === 0) {
      fetchUsers();
      return;
    }

    if (activeTab === 'email_trace' && emailTrace.length === 0) {
      fetchRegistrationEmailTrace();
    }
  }, [activeTab, token, currentUser]);

  const fetchCurrentUser = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/platform/auth/me`, getPlatformHeaders());
      setCurrentUser(response.data);
    } catch (error) {
      handleLogout();
    }
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    setLoginError('');
    setLoginLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/platform/auth/login`, {
        username: loginUsername,
        password: loginPassword,
      });

      const newToken = response.data.token;
      setToken(newToken);
      localStorage.setItem('platform_token', newToken);
      setCurrentUser(response.data.user);
      setLoginUsername('');
      setLoginPassword('');
    } catch (error) {
      setLoginError(error.response?.data?.message || 'Login failed');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    setToken(null);
    setCurrentUser(null);
    localStorage.removeItem('platform_token');
  };

  const handleBootstrap = async (event) => {
    event.preventDefault();
    setBootstrapError('');
    setBootstrapSuccess('');
    setBootstrapLoading(true);

    try {
      await axios.post(
        `${API_BASE_URL}/platform/users`,
        {
          username: bootstrapForm.username,
          email: bootstrapForm.email,
          password: bootstrapForm.password,
        },
        {
          headers: {
            'X-Platform-Owner-Key': bootstrapForm.ownerKey,
          },
        }
      );

      setBootstrapSuccess('Initial platform admin created. You can log in immediately below.');
      setLoginUsername(bootstrapForm.username);
      setBootstrapForm({ ownerKey: '', username: '', email: '', password: '' });
      setNeedsBootstrap(false);
    } catch (error) {
      setBootstrapError(error.response?.data?.message || 'Failed to bootstrap the first platform admin user.');
    } finally {
      setBootstrapLoading(false);
    }
  };

  const fetchPublicContent = async () => {
    setPublicContentLoading(true);
    setPublicContentError('');
    try {
      const response = await axios.get(`${API_BASE_URL}/platform/public-content`, getPlatformHeaders());
      setPublicContent({ ...DEFAULT_PUBLIC_CONTENT, ...response.data });
    } catch (error) {
      setPublicContentError(error.response?.data?.message || 'Failed to load public content');
    } finally {
      setPublicContentLoading(false);
    }
  };

  const savePublicContent = async () => {
    setPublicContentLoading(true);
    setPublicContentError('');
    setPublicContentSuccess('');
    try {
      await axios.put(`${API_BASE_URL}/platform/public-content`, publicContent, getPlatformHeaders());
      setPublicContentSuccess('Tenant-facing content updated successfully.');
      window.setTimeout(() => setPublicContentSuccess(''), 3000);
    } catch (error) {
      setPublicContentError(error.response?.data?.message || 'Failed to save public content');
    } finally {
      setPublicContentLoading(false);
    }
  };

  const updateFaq = (index, field, value) => {
    setPublicContent((prev) => ({
      ...prev,
      faqs: prev.faqs.map((row, rowIndex) => (rowIndex === index ? { ...row, [field]: value } : row)),
    }));
  };

  const addFaq = () => {
    setPublicContent((prev) => ({
      ...prev,
      faqs: [...prev.faqs, { question: '', answer: '' }],
    }));
  };

  const removeFaq = (index) => {
    setPublicContent((prev) => ({
      ...prev,
      faqs: prev.faqs.filter((_, rowIndex) => rowIndex !== index),
    }));
  };

  const updateTutorial = (index, field, value) => {
    setPublicContent((prev) => ({
      ...prev,
      tutorials: prev.tutorials.map((row, rowIndex) => (rowIndex === index ? { ...row, [field]: value } : row)),
    }));
  };

  const addTutorial = () => {
    setPublicContent((prev) => ({
      ...prev,
      tutorials: [...prev.tutorials, { title: '', url: '' }],
    }));
  };

  const removeTutorial = (index) => {
    setPublicContent((prev) => ({
      ...prev,
      tutorials: prev.tutorials.filter((_, rowIndex) => rowIndex !== index),
    }));
  };

  const updateGuide = (index, field, value) => {
    setPublicContent((prev) => ({
      ...prev,
      feature_guides: prev.feature_guides.map((row, rowIndex) => (rowIndex === index ? { ...row, [field]: value } : row)),
    }));
  };

  const addGuide = () => {
    setPublicContent((prev) => ({
      ...prev,
      feature_guides: [...prev.feature_guides, { title: '', body: '' }],
    }));
  };

  const removeGuide = (index) => {
    setPublicContent((prev) => ({
      ...prev,
      feature_guides: prev.feature_guides.filter((_, rowIndex) => rowIndex !== index),
    }));
  };

  const updateSecurityAlert = (index, value) => {
    setPublicContent((prev) => ({
      ...prev,
      security_alerts: prev.security_alerts.map((row, rowIndex) => (rowIndex === index ? value : row)),
    }));
  };

  const addSecurityAlert = () => {
    setPublicContent((prev) => ({
      ...prev,
      security_alerts: [...prev.security_alerts, ''],
    }));
  };

  const removeSecurityAlert = (index) => {
    setPublicContent((prev) => ({
      ...prev,
      security_alerts: prev.security_alerts.filter((_, rowIndex) => rowIndex !== index),
    }));
  };

  const updateNestedField = (section, field, value) => {
    setPublicContent((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value,
      },
    }));
  };

  const fetchChiefExaminerLibrary = async () => {
    setChiefLoading(true);
    setChiefError('');
    try {
      const [libraryResponse, historyResponse] = await Promise.all([
        axios.get(`${API_BASE_URL}/platform/chief-examiner-library`, getPlatformHeaders()),
        axios.get(`${API_BASE_URL}/platform/chief-examiner-library/history`, getPlatformHeaders()),
      ]);
      setChiefLibrary(libraryResponse.data || { subjects: [], meta: {} });
      setChiefHistory(historyResponse.data?.history || []);
    } catch (error) {
      setChiefError(error.response?.data?.message || 'Failed to load platform chief examiner library');
    } finally {
      setChiefLoading(false);
    }
  };

  const importChiefExaminerLibrary = async () => {
    if (chiefFiles.length === 0 && !chiefText.trim()) {
      setChiefError('Upload a file or paste structured examiner insight text.');
      return;
    }

    setChiefLoading(true);
    setChiefError('');
    setChiefSuccess('');

    try {
      const formData = new FormData();
      chiefFiles.forEach((file) => {
        formData.append('file', file);
      });
      if (chiefText.trim()) {
        formData.append('report_text', chiefText.trim());
        if (chiefFiles.length === 0) {
          formData.append('source_filename', 'manual-text');
        }
      }
      formData.append('replace_existing', chiefReplaceExisting ? 'true' : 'false');

      await axios.post(`${API_BASE_URL}/platform/chief-examiner-library/import`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
      });

      setChiefSuccess(`Platform chief examiner library updated${chiefFiles.length > 1 ? ` from ${chiefFiles.length} reports` : ''}. Tenants will receive the new insights automatically.`);
      setChiefText('');
      setChiefFiles([]);
      setChiefFileInputKey((current) => current + 1);
      await fetchChiefExaminerLibrary();
    } catch (error) {
      setChiefError(error.response?.data?.message || 'Failed to import chief examiner library');
    } finally {
      setChiefLoading(false);
    }
  };

  const restoreChiefHistory = async (versionId) => {
    try {
      setChiefLoading(true);
      setChiefError('');
      await axios.post(`${API_BASE_URL}/platform/chief-examiner-library/history/${versionId}/restore`, {}, getPlatformHeaders());
      setChiefSuccess('Platform chief examiner library restored successfully.');
      await fetchChiefExaminerLibrary();
    } catch (error) {
      setChiefError(error.response?.data?.message || 'Failed to restore chief examiner library snapshot');
    } finally {
      setChiefLoading(false);
    }
  };

  const downloadChiefHistory = async (versionId) => {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/platform/chief-examiner-library/history/${versionId}/download`,
        {
          ...getPlatformHeaders(),
          responseType: 'blob',
        }
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `platform-chief-examiner-${versionId}.json`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      setChiefError(error.response?.data?.message || 'Failed to download chief examiner snapshot');
    }
  };

  const fetchUsers = async () => {
    setUsersLoading(true);
    setUsersError('');
    try {
      const response = await axios.get(`${API_BASE_URL}/platform/users`, getPlatformHeaders());
      setUsers(response.data.users || []);
    } catch (error) {
      setUsersError(error.response?.data?.message || 'Failed to load users');
    } finally {
      setUsersLoading(false);
    }
  };

  const handleAddUser = async (event) => {
    event.preventDefault();
    setAddUserError('');

    try {
      await axios.post(`${API_BASE_URL}/platform/users`, addUserForm, getPlatformHeaders());
      setAddUserForm({ username: '', email: '', password: '' });
      fetchUsers();
    } catch (error) {
      setAddUserError(error.response?.data?.message || 'Failed to add user');
    }
  };

  const handleRemoveUser = async (userId) => {
    if (!window.confirm('Are you sure you want to remove this user?')) {
      return;
    }

    try {
      await axios.delete(`${API_BASE_URL}/platform/users/${userId}`, getPlatformHeaders());
      fetchUsers();
    } catch (error) {
      alert(error.response?.data?.message || 'Failed to remove user');
    }
  };

  const fetchRegistrationEmailTrace = async () => {
    setEmailTraceLoading(true);
    setEmailTraceError('');
    try {
      const query = emailTraceSchoolFilter.trim()
        ? `?school_id=${encodeURIComponent(emailTraceSchoolFilter.trim())}`
        : '';
      const response = await axios.get(`${API_BASE_URL}/platform/registration-email-trace${query}`, getPlatformHeaders());
      setEmailTrace(Array.isArray(response.data?.events) ? response.data.events : []);
      setEmailTraceSummary(Array.isArray(response.data?.duplicate_summary) ? response.data.duplicate_summary : []);
    } catch (error) {
      setEmailTraceError(error.response?.data?.message || 'Failed to load registration email trace');
    } finally {
      setEmailTraceLoading(false);
    }
  };

  if (!token || !currentUser) {
    return (
      <div className="min-h-screen bg-linear-to-br from-blue-900 to-indigo-800 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-2xl p-8 w-full max-w-md">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Platform Console</h1>
            <p className="text-gray-600">Admin Access Only</p>
          </div>

          {bootstrapChecked && needsBootstrap ? (
            <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-bold text-amber-900">Initial Setup Required</p>
              <p className="mt-1 text-xs text-amber-800">
                This Docker environment does not have a platform admin user yet. Create the first one with your `PLATFORM_OWNER_KEY`.
              </p>

              <form onSubmit={handleBootstrap} className="mt-4 space-y-3">
                <input
                  type="password"
                  value={bootstrapForm.ownerKey}
                  onChange={(event) => setBootstrapForm({ ...bootstrapForm, ownerKey: event.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="PLATFORM_OWNER_KEY"
                  required
                />
                <input
                  type="text"
                  value={bootstrapForm.username}
                  onChange={(event) => setBootstrapForm({ ...bootstrapForm, username: event.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="First platform username"
                  required
                />
                <input
                  type="email"
                  value={bootstrapForm.email}
                  onChange={(event) => setBootstrapForm({ ...bootstrapForm, email: event.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="owner@example.com"
                  required
                />
                <input
                  type="password"
                  value={bootstrapForm.password}
                  onChange={(event) => setBootstrapForm({ ...bootstrapForm, password: event.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="Password"
                  required
                />

                {bootstrapError ? <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded text-sm">{bootstrapError}</div> : null}
                {bootstrapSuccess ? <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded text-sm">{bootstrapSuccess}</div> : null}

                <button
                  type="submit"
                  disabled={bootstrapLoading}
                  className="w-full bg-amber-600 text-white py-2 px-4 rounded-md hover:bg-amber-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors"
                >
                  {bootstrapLoading ? 'Creating Platform Admin...' : 'Create First Platform Admin'}
                </button>
              </form>
            </div>
          ) : null}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
              <input
                type="text"
                value={loginUsername}
                onChange={(event) => setLoginUsername(event.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
                disabled={loginLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
                disabled={loginLoading}
              />
            </div>

            {loginError ? (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{loginError}</div>
            ) : null}

            <button
              type="submit"
              disabled={loginLoading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors"
            >
              {loginLoading ? 'Logging in...' : 'Login'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Platform Owner Console</h1>
              <p className="text-sm text-gray-600">Logged in as: {currentUser.username}</p>
            </div>
            <button onClick={handleLogout} className="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 transition-colors">Logout</button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex flex-wrap gap-8">
            {[
              ['public_content', 'Tenant Content'],
              ['chief_examiner', 'Chief Examiner Library'],
              ['users', 'User Management'],
              ['email_trace', 'Registration Email Trace'],
            ].map(([value, label]) => (
              <button
                key={value}
                onClick={() => setActiveTab(value)}
                className={`${activeTab === value ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'} whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors`}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'public_content' ? (
          <div className="space-y-6">
            <SectionCard
              title="Tenant-Facing Public Content"
              description="Manage the help center, login page support details, signup copy, and other shared public content from one place."
            >
              {publicContentError ? <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{publicContentError}</div> : null}
              {publicContentSuccess ? <div className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">{publicContentSuccess}</div> : null}

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900">Help Center Copy</h3>
                  <input type="text" value={publicContent.help_center.title} onChange={(event) => updateNestedField('help_center', 'title', event.target.value)} placeholder="Help center title" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                  <textarea value={publicContent.help_center.subtitle} onChange={(event) => updateNestedField('help_center', 'subtitle', event.target.value)} rows="2" placeholder="Help center subtitle" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                  <input type="text" value={publicContent.help_center.security_title} onChange={(event) => updateNestedField('help_center', 'security_title', event.target.value)} placeholder="Security alert title" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                  <textarea value={publicContent.help_center.security_body} onChange={(event) => updateNestedField('help_center', 'security_body', event.target.value)} rows="3" placeholder="Security alert intro text" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                </div>

                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900">Support Contact</h3>
                  <input type="email" value={publicContent.support.email} onChange={(event) => updateNestedField('support', 'email', event.target.value)} placeholder="Support email" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                  <input type="text" value={publicContent.support.phone} onChange={(event) => updateNestedField('support', 'phone', event.target.value)} placeholder="Support phone or WhatsApp" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                  <input type="text" value={publicContent.support.website} onChange={(event) => updateNestedField('support', 'website', event.target.value)} placeholder="Support website" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                  <input type="text" value={publicContent.support.response_time} onChange={(event) => updateNestedField('support', 'response_time', event.target.value)} placeholder="Response time note" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900">Login Page Copy</h3>
                  <input type="text" value={publicContent.auth.login_title} onChange={(event) => updateNestedField('auth', 'login_title', event.target.value)} placeholder="Login title" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                  <textarea value={publicContent.auth.login_subtitle} onChange={(event) => updateNestedField('auth', 'login_subtitle', event.target.value)} rows="2" placeholder="Login subtitle" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                </div>

                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900">Signup Page Copy</h3>
                  <input type="text" value={publicContent.auth.register_title} onChange={(event) => updateNestedField('auth', 'register_title', event.target.value)} placeholder="Signup title" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                  <textarea value={publicContent.auth.register_subtitle} onChange={(event) => updateNestedField('auth', 'register_subtitle', event.target.value)} rows="2" placeholder="Signup subtitle" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                  <textarea value={publicContent.auth.register_support_note} onChange={(event) => updateNestedField('auth', 'register_support_note', event.target.value)} rows="2" placeholder="Signup support note" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                </div>
              </div>
            </SectionCard>

            <SectionCard title="FAQs" description="These entries are shown on the login page and in the help center.">
              <div className="flex justify-end mb-4">
                <button onClick={addFaq} className="bg-green-600 text-white px-3 py-1 rounded-md hover:bg-green-700 text-sm">+ Add FAQ</button>
              </div>
              <div className="space-y-4">
                {publicContent.faqs.map((faq, index) => (
                  <div key={`faq-${index}`} className="border border-gray-200 rounded-md p-4">
                    <div className="flex justify-between items-start mb-2">
                      <span className="text-sm font-medium text-gray-700">FAQ {index + 1}</span>
                      <button onClick={() => removeFaq(index)} className="text-red-600 hover:text-red-800 text-sm">Remove</button>
                    </div>
                    <input type="text" value={faq.question} onChange={(event) => updateFaq(index, 'question', event.target.value)} placeholder="Question" className="w-full px-3 py-2 border border-gray-300 rounded-md mb-2" />
                    <textarea value={faq.answer} onChange={(event) => updateFaq(index, 'answer', event.target.value)} rows="3" placeholder="Answer" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="Tutorials, Guides, and Security Alerts">
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                <div>
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold text-gray-900">Tutorials</h3>
                    <button onClick={addTutorial} className="bg-green-600 text-white px-3 py-1 rounded-md hover:bg-green-700 text-sm">+ Add</button>
                  </div>
                  <div className="space-y-3">
                    {publicContent.tutorials.map((tutorial, index) => (
                      <div key={`tutorial-${index}`} className="border border-gray-200 rounded-md p-3">
                        <input type="text" value={tutorial.title} onChange={(event) => updateTutorial(index, 'title', event.target.value)} placeholder="Tutorial title" className="w-full px-3 py-2 border border-gray-300 rounded-md mb-2" />
                        <input type="url" value={tutorial.url} onChange={(event) => updateTutorial(index, 'url', event.target.value)} placeholder="https://..." className="w-full px-3 py-2 border border-gray-300 rounded-md mb-2" />
                        <button onClick={() => removeTutorial(index)} className="text-red-600 hover:text-red-800 text-sm">Remove</button>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold text-gray-900">Feature Guides</h3>
                    <button onClick={addGuide} className="bg-green-600 text-white px-3 py-1 rounded-md hover:bg-green-700 text-sm">+ Add</button>
                  </div>
                  <div className="space-y-3">
                    {publicContent.feature_guides.map((guide, index) => (
                      <div key={`guide-${index}`} className="border border-gray-200 rounded-md p-3">
                        <input type="text" value={guide.title} onChange={(event) => updateGuide(index, 'title', event.target.value)} placeholder="Guide title" className="w-full px-3 py-2 border border-gray-300 rounded-md mb-2" />
                        <textarea value={guide.body} onChange={(event) => updateGuide(index, 'body', event.target.value)} rows="3" placeholder="Guide body" className="w-full px-3 py-2 border border-gray-300 rounded-md mb-2" />
                        <button onClick={() => removeGuide(index)} className="text-red-600 hover:text-red-800 text-sm">Remove</button>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold text-gray-900">Security Alerts</h3>
                    <button onClick={addSecurityAlert} className="bg-green-600 text-white px-3 py-1 rounded-md hover:bg-green-700 text-sm">+ Add</button>
                  </div>
                  <div className="space-y-3">
                    {publicContent.security_alerts.map((alert, index) => (
                      <div key={`alert-${index}`} className="border border-gray-200 rounded-md p-3">
                        <textarea value={alert} onChange={(event) => updateSecurityAlert(index, event.target.value)} rows="3" placeholder="Security alert" className="w-full px-3 py-2 border border-gray-300 rounded-md mb-2" />
                        <button onClick={() => removeSecurityAlert(index)} className="text-red-600 hover:text-red-800 text-sm">Remove</button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex justify-end mt-6">
                <button onClick={savePublicContent} disabled={publicContentLoading} className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium">
                  {publicContentLoading ? 'Saving...' : 'Save Tenant Content'}
                </button>
              </div>
            </SectionCard>
          </div>
        ) : null}

        {activeTab === 'chief_examiner' ? (
          <div className="space-y-6">
            <SectionCard title="Platform Chief Examiner Library" description="Upload examiner reports here to build the shared library used across schools.">
              {chiefError ? <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{chiefError}</div> : null}
              {chiefSuccess ? <div className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">{chiefSuccess}</div> : null}

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">Current Version</p>
                  <p className="text-lg font-bold text-gray-900">{chiefLibrary.meta?.version_id || 'No upload yet'}</p>
                </div>
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">Subjects</p>
                  <p className="text-lg font-bold text-gray-900">{chiefLibrary.meta?.subject_count || chiefLibrary.subjects?.length || 0}</p>
                </div>
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">History Items</p>
                  <p className="text-lg font-bold text-gray-900">{chiefLibrary.meta?.history_count || chiefHistory.length || 0}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Upload Examiner Report Files</label>
                    <input key={chiefFileInputKey} type="file" multiple accept=".json,.txt,.md,.pdf,.png,.jpg,.jpeg,.webp" onChange={(event) => setChiefFiles(Array.from(event.target.files || []))} className="block w-full text-sm text-gray-700" />
                    <p className="mt-2 text-xs text-gray-500">Select one report or a batch of BECE PDFs, for example 2017, 2018, 2019, 2020, 2021, and 2023.</p>
                    {chiefFiles.length > 0 ? (
                      <div className="mt-3 rounded-md bg-gray-50 border border-gray-200 p-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Selected files</p>
                        <p className="mt-1 text-sm text-gray-700">{chiefFiles.length} file{chiefFiles.length === 1 ? '' : 's'} selected</p>
                        <div className="mt-2 space-y-1">
                          {chiefFiles.slice(0, 6).map((file) => (
                            <p key={`${file.name}-${file.size}`} className="text-xs text-gray-600">{file.name}</p>
                          ))}
                          {chiefFiles.length > 6 ? <p className="text-xs text-gray-500">+{chiefFiles.length - 6} more</p> : null}
                        </div>
                      </div>
                    ) : null}
                  </div>
                  <label className="inline-flex items-center gap-2 text-sm text-gray-700">
                    <input type="checkbox" checked={chiefReplaceExisting} onChange={(event) => setChiefReplaceExisting(event.target.checked)} />
                    Replace the current shared library instead of merging into it
                  </label>
                  <button onClick={importChiefExaminerLibrary} disabled={chiefLoading} className="bg-blue-600 text-white px-5 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed">
                    {chiefLoading ? 'Updating...' : 'Update Shared Library'}
                  </button>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Structured Text Input</label>
                  <textarea
                    value={chiefText}
                    onChange={(event) => setChiefText(event.target.value)}
                    rows="10"
                    placeholder={['Subject: Mathematics', 'Topic: Geometry', 'Issue: students often miss theorem reasons', 'Advice: reteach proofs with labelled diagrams', 'Practice: circle theorems; angle properties'].join('\n')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm"
                  />
                  <p className="mt-2 text-xs text-gray-500">Use pasted structured text for a single report only.</p>
                </div>
              </div>
            </SectionCard>

            <SectionCard title="Current Shared Library" description="Review the subjects and summaries currently available in the shared library.">
              {chiefLoading ? <p className="text-gray-600">Loading library...</p> : null}
              <div className="space-y-4">
                {(chiefLibrary.subjects || []).map((subject) => (
                  <div key={subject.subject} className="border border-gray-200 rounded-md p-4">
                    <h3 className="text-lg font-semibold text-gray-900">{subject.subject}</h3>
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                      {(subject.topics || []).slice(0, 6).map((topic) => (
                        <div key={`${subject.subject}-${topic.topic}`} className="rounded-md bg-gray-50 p-3 border border-gray-200">
                          <p className="font-semibold text-gray-800">{topic.topic}</p>
                          <p className="text-sm text-gray-600 mt-1">{topic.issue}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
                {(!chiefLibrary.subjects || chiefLibrary.subjects.length === 0) ? <p className="text-sm text-gray-500">No shared library has been uploaded yet.</p> : null}
              </div>
            </SectionCard>

            <SectionCard title="Version History" description="Restore or download previous platform-wide examiner library versions.">
              <div className="space-y-3">
                {chiefHistory.map((item) => (
                  <div key={item.version_id} className="border border-gray-200 rounded-md p-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                    <div>
                      <p className="font-semibold text-gray-900">{item.source_filename || item.version_id}</p>
                      <p className="text-sm text-gray-600">{item.created_at ? new Date(item.created_at).toLocaleString() : 'Unknown time'} • {item.subject_count} subjects • {item.entry_count} entries</p>
                      <p className="text-xs text-gray-500 mt-1">Created by: {item.created_by || 'System'} {item.is_active ? '• Active' : ''}</p>
                    </div>
                    <div className="flex gap-3">
                      <button onClick={() => restoreChiefHistory(item.version_id)} className="px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700">Restore</button>
                      <button onClick={() => downloadChiefHistory(item.version_id)} className="px-4 py-2 rounded-md bg-gray-200 text-gray-800 hover:bg-gray-300">Download</button>
                    </div>
                  </div>
                ))}
                {chiefHistory.length === 0 ? <p className="text-sm text-gray-500">No platform library history yet.</p> : null}
              </div>
            </SectionCard>
          </div>
        ) : null}

        {activeTab === 'users' ? (
          <div className="space-y-6">
            <SectionCard title="Add New Admin User" description="Authenticated platform admins can create and remove other platform admin users here.">
              {addUserError ? <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{addUserError}</div> : null}

              <form onSubmit={handleAddUser} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <input type="text" value={addUserForm.username} onChange={(event) => setAddUserForm({ ...addUserForm, username: event.target.value })} placeholder="Username" className="px-3 py-2 border border-gray-300 rounded-md" required />
                  <input type="email" value={addUserForm.email} onChange={(event) => setAddUserForm({ ...addUserForm, email: event.target.value })} placeholder="Email" className="px-3 py-2 border border-gray-300 rounded-md" required />
                  <input type="password" value={addUserForm.password} onChange={(event) => setAddUserForm({ ...addUserForm, password: event.target.value })} placeholder="Password" className="px-3 py-2 border border-gray-300 rounded-md" required />
                </div>
                <button type="submit" className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700">Add User</button>
              </form>
            </SectionCard>

            <SectionCard title="Admin Users">
              {usersError ? <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{usersError}</div> : null}
              {usersLoading ? <p className="text-gray-600">Loading users...</p> : null}
              {!usersLoading ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last Login</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {users.map((user) => (
                        <tr key={user.id}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{user.username}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{user.email}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm">
                            <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                              {user.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm">
                            <button onClick={() => handleRemoveUser(user.id)} className="text-red-600 hover:text-red-900">Remove</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {users.length === 0 ? <p className="text-center text-gray-500 py-4">No users found</p> : null}
                </div>
              ) : null}
            </SectionCard>
          </div>
        ) : null}

        {activeTab === 'email_trace' ? (
          <SectionCard title="Registration Email Trace" description="Track welcome-email sends and quickly detect duplicates per school.">
            <div className="flex flex-wrap gap-3 mb-4">
              <input type="text" value={emailTraceSchoolFilter} onChange={(event) => setEmailTraceSchoolFilter(event.target.value)} placeholder="Filter by school ID (optional)" className="px-3 py-2 border border-gray-300 rounded-md min-w-80" />
              <button onClick={fetchRegistrationEmailTrace} className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">Refresh Trace</button>
            </div>

            {emailTraceError ? <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{emailTraceError}</div> : null}

            {emailTraceLoading ? <p className="text-gray-600">Loading trace...</p> : null}

            {!emailTraceLoading ? (
              <>
                <div className="mb-6">
                  <h3 className="text-md font-semibold text-gray-800 mb-2">Duplicate Summary</h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">School ID</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Welcome Email Count</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Duplicate</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {emailTraceSummary.map((row) => (
                          <tr key={row.school_id}>
                            <td className="px-4 py-2 text-sm text-gray-800 font-mono">{row.school_id}</td>
                            <td className="px-4 py-2 text-sm text-gray-700">{row.welcome_email_count}</td>
                            <td className="px-4 py-2 text-sm">
                              <span className={`px-2 py-1 rounded text-xs font-semibold ${row.has_duplicates ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                                {row.has_duplicates ? 'YES' : 'NO'}
                              </span>
                            </td>
                          </tr>
                        ))}
                        {emailTraceSummary.length === 0 ? (
                          <tr>
                            <td colSpan="3" className="px-4 py-4 text-sm text-gray-500 text-center">No registration email activity found.</td>
                          </tr>
                        ) : null}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div>
                  <h3 className="text-md font-semibold text-gray-800 mb-2">Recent Events</h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">School</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {emailTrace.map((row) => (
                          <tr key={row.id}>
                            <td className="px-4 py-2 text-xs text-gray-600">{row.timestamp ? new Date(row.timestamp).toLocaleString() : '-'}</td>
                            <td className="px-4 py-2 text-sm text-gray-800 font-mono">{row.school_id}</td>
                            <td className="px-4 py-2 text-xs text-blue-700 font-semibold">{row.action}</td>
                            <td className="px-4 py-2 text-xs text-gray-600">{row.details || '-'}</td>
                          </tr>
                        ))}
                        {emailTrace.length === 0 ? (
                          <tr>
                            <td colSpan="4" className="px-4 py-4 text-sm text-gray-500 text-center">No events available.</td>
                          </tr>
                        ) : null}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            ) : null}
          </SectionCard>
        ) : null}
      </div>
    </div>
  );
}