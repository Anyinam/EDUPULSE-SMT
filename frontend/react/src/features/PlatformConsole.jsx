import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

export default function PlatformConsole() {
  const [token, setToken] = useState(localStorage.getItem('platform_token'));
  const [currentUser, setCurrentUser] = useState(null);
  const [activeTab, setActiveTab] = useState('help');
  
  // Login state
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  
  // Help content state
  const [helpContent, setHelpContent] = useState({ faqs: [], tutorials: [] });
  const [helpLoading, setHelpLoading] = useState(false);
  const [helpError, setHelpError] = useState('');
  const [helpSuccess, setHelpSuccess] = useState('');
  
  // User management state
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState('');
  const [addUserForm, setAddUserForm] = useState({ username: '', email: '', password: '' });
  const [addUserError, setAddUserError] = useState('');
  const [ownerKey, setOwnerKey] = useState('');
  const [emailTrace, setEmailTrace] = useState([]);
  const [emailTraceSummary, setEmailTraceSummary] = useState([]);
  const [emailTraceLoading, setEmailTraceLoading] = useState(false);
  const [emailTraceError, setEmailTraceError] = useState('');
  const [emailTraceSchoolFilter, setEmailTraceSchoolFilter] = useState('');

  // Check authentication on mount
  useEffect(() => {
    if (token) {
      fetchCurrentUser();
    }
  }, [token]);

  // Fetch current user
  const fetchCurrentUser = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/platform/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCurrentUser(response.data);
    } catch (error) {
      console.error('Auth check failed:', error);
      handleLogout();
    }
  };

  // Handle login
  const handleLogin = async (e) => {
    e.preventDefault();
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

  // Handle logout
  const handleLogout = () => {
    setToken(null);
    setCurrentUser(null);
    localStorage.removeItem('platform_token');
  };

  // Fetch help content
  const fetchHelpContent = async () => {
    setHelpLoading(true);
    setHelpError('');
    try {
      const response = await axios.get(`${API_BASE_URL}/platform/help-content`, {
        headers: { 'X-Platform-Owner-Key': ownerKey },
      });
      setHelpContent(response.data);
    } catch (error) {
      setHelpError(error.response?.data?.message || 'Failed to load help content');
    } finally {
      setHelpLoading(false);
    }
  };

  // Save help content
  const saveHelpContent = async () => {
    setHelpLoading(true);
    setHelpError('');
    setHelpSuccess('');
    try {
      await axios.put(
        `${API_BASE_URL}/platform/help-content`,
        helpContent,
        { headers: { 'X-Platform-Owner-Key': ownerKey } }
      );
      setHelpSuccess('Help content saved successfully!');
      setTimeout(() => setHelpSuccess(''), 3000);
    } catch (error) {
      setHelpError(error.response?.data?.message || 'Failed to save help content');
    } finally {
      setHelpLoading(false);
    }
  };

  // Add FAQ
  const addFaq = () => {
    setHelpContent({
      ...helpContent,
      faqs: [...helpContent.faqs, { question: '', answer: '' }],
    });
  };

  // Update FAQ
  const updateFaq = (index, field, value) => {
    const newFaqs = [...helpContent.faqs];
    newFaqs[index][field] = value;
    setHelpContent({ ...helpContent, faqs: newFaqs });
  };

  // Remove FAQ
  const removeFaq = (index) => {
    const newFaqs = helpContent.faqs.filter((_, i) => i !== index);
    setHelpContent({ ...helpContent, faqs: newFaqs });
  };

  // Add Tutorial
  const addTutorial = () => {
    setHelpContent({
      ...helpContent,
      tutorials: [...helpContent.tutorials, { title: '', url: '' }],
    });
  };

  // Update Tutorial
  const updateTutorial = (index, field, value) => {
    const newTutorials = [...helpContent.tutorials];
    newTutorials[index][field] = value;
    setHelpContent({ ...helpContent, tutorials: newTutorials });
  };

  // Remove Tutorial
  const removeTutorial = (index) => {
    const newTutorials = helpContent.tutorials.filter((_, i) => i !== index);
    setHelpContent({ ...helpContent, tutorials: newTutorials });
  };

  // Fetch users
  const fetchUsers = async () => {
    setUsersLoading(true);
    setUsersError('');
    try {
      const response = await axios.get(`${API_BASE_URL}/platform/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setUsers(response.data.users || []);
    } catch (error) {
      setUsersError(error.response?.data?.message || 'Failed to load users');
    } finally {
      setUsersLoading(false);
    }
  };

  const fetchRegistrationEmailTrace = async () => {
    setEmailTraceLoading(true);
    setEmailTraceError('');
    try {
      const query = emailTraceSchoolFilter
        ? `?school_id=${encodeURIComponent(emailTraceSchoolFilter.trim())}`
        : '';
      const response = await axios.get(`${API_BASE_URL}/platform/registration-email-trace${query}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setEmailTrace(Array.isArray(response.data?.events) ? response.data.events : []);
      setEmailTraceSummary(Array.isArray(response.data?.duplicate_summary) ? response.data.duplicate_summary : []);
    } catch (error) {
      setEmailTraceError(error.response?.data?.message || 'Failed to load registration email trace');
    } finally {
      setEmailTraceLoading(false);
    }
  };

  // Add user
  const handleAddUser = async (e) => {
    e.preventDefault();
    setAddUserError('');
    
    if (!ownerKey) {
      setAddUserError('Owner key required to add users');
      return;
    }

    try {
      await axios.post(
        `${API_BASE_URL}/platform/users`,
        addUserForm,
        { headers: { 'X-Platform-Owner-Key': ownerKey } }
      );
      setAddUserForm({ username: '', email: '', password: '' });
      fetchUsers();
    } catch (error) {
      setAddUserError(error.response?.data?.message || 'Failed to add user');
    }
  };

  // Remove user
  const handleRemoveUser = async (userId) => {
    if (!ownerKey) {
      alert('Owner key required to remove users');
      return;
    }

    if (!confirm('Are you sure you want to remove this user?')) {
      return;
    }

    try {
      await axios.delete(`${API_BASE_URL}/platform/users/${userId}`, {
        headers: { 'X-Platform-Owner-Key': ownerKey },
      });
      fetchUsers();
    } catch (error) {
      alert(error.response?.data?.message || 'Failed to remove user');
    }
  };

  // Load data when tab changes
  useEffect(() => {
    if (!token || !currentUser) return;
    
    if (activeTab === 'help' && helpContent.faqs.length === 0) {
      if (ownerKey) fetchHelpContent();
    } else if (activeTab === 'users' && users.length === 0) {
      fetchUsers();
    } else if (activeTab === 'email_trace' && emailTrace.length === 0) {
      fetchRegistrationEmailTrace();
    }
  }, [activeTab, token, currentUser]);

  // Login screen
  if (!token || !currentUser) {
    return (
      <div className="min-h-screen bg-linear-to-br from-blue-900 to-indigo-800 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-2xl p-8 w-full max-w-md">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Platform Console</h1>
            <p className="text-gray-600">Admin Access Only</p>
          </div>
          
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Username
              </label>
              <input
                type="text"
                value={loginUsername}
                onChange={(e) => setLoginUsername(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
                disabled={loginLoading}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
                disabled={loginLoading}
              />
            </div>
            
            {loginError && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                {loginError}
              </div>
            )}
            
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

  // Main console
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Platform Owner Console</h1>
              <p className="text-sm text-gray-600">Logged in as: {currentUser.username}</p>
            </div>
            <button
              onClick={handleLogout}
              className="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('help')}
              className={`${
                activeTab === 'help'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors`}
            >
              Help Content
            </button>
            <button
              onClick={() => setActiveTab('users')}
              className={`${
                activeTab === 'users'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors`}
            >
              User Management
            </button>
            <button
              onClick={() => setActiveTab('email_trace')}
              className={`${
                activeTab === 'email_trace'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors`}
            >
              Registration Email Trace
            </button>
          </nav>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Help Content Tab */}
        {activeTab === 'help' && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Login Page Help Content</h2>
            
            {/* Owner Key Input */}
            <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-md p-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Platform Owner Key (required for editing)
              </label>
              <input
                type="password"
                value={ownerKey}
                onChange={(e) => setOwnerKey(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Enter your platform owner key"
              />
              {ownerKey && (
                <button
                  onClick={fetchHelpContent}
                  className="mt-2 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm"
                >
                  Load Help Content
                </button>
              )}
            </div>

            {helpError && (
              <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                {helpError}
              </div>
            )}

            {helpSuccess && (
              <div className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
                {helpSuccess}
              </div>
            )}

            {/* FAQs */}
            <div className="mb-8">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-gray-900">FAQs</h3>
                <button
                  onClick={addFaq}
                  className="bg-green-600 text-white px-3 py-1 rounded-md hover:bg-green-700 text-sm"
                >
                  + Add FAQ
                </button>
              </div>
              
              {helpContent.faqs.map((faq, index) => (
                <div key={index} className="mb-4 p-4 border border-gray-200 rounded-md">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-sm font-medium text-gray-700">FAQ {index + 1}</span>
                    <button
                      onClick={() => removeFaq(index)}
                      className="text-red-600 hover:text-red-800 text-sm"
                    >
                      Remove
                    </button>
                  </div>
                  <input
                    type="text"
                    value={faq.question}
                    onChange={(e) => updateFaq(index, 'question', e.target.value)}
                    placeholder="Question"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md mb-2"
                  />
                  <textarea
                    value={faq.answer}
                    onChange={(e) => updateFaq(index, 'answer', e.target.value)}
                    placeholder="Answer"
                    rows="3"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
              ))}
            </div>

            {/* Tutorials */}
            <div className="mb-8">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-gray-900">Video Tutorials</h3>
                <button
                  onClick={addTutorial}
                  className="bg-green-600 text-white px-3 py-1 rounded-md hover:bg-green-700 text-sm"
                >
                  + Add Tutorial
                </button>
              </div>
              
              {helpContent.tutorials.map((tutorial, index) => (
                <div key={index} className="mb-4 p-4 border border-gray-200 rounded-md">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-sm font-medium text-gray-700">Tutorial {index + 1}</span>
                    <button
                      onClick={() => removeTutorial(index)}
                      className="text-red-600 hover:text-red-800 text-sm"
                    >
                      Remove
                    </button>
                  </div>
                  <input
                    type="text"
                    value={tutorial.title}
                    onChange={(e) => updateTutorial(index, 'title', e.target.value)}
                    placeholder="Tutorial Title"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md mb-2"
                  />
                  <input
                    type="url"
                    value={tutorial.url}
                    onChange={(e) => updateTutorial(index, 'url', e.target.value)}
                    placeholder="YouTube URL (https://...)"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
              ))}
            </div>

            {/* Save Button */}
            <div className="flex justify-end">
              <button
                onClick={saveHelpContent}
                disabled={helpLoading || !ownerKey}
                className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium"
              >
                {helpLoading ? 'Saving...' : 'Save Help Content'}
              </button>
            </div>
          </div>
        )}

        {/* User Management Tab */}
        {activeTab === 'users' && (
          <div className="space-y-6">
            {/* Add User Form */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Add New Admin User</h2>
              
              {/* Owner Key Input */}
              <div className="mb-4 bg-yellow-50 border border-yellow-200 rounded-md p-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Platform Owner Key (required to add/remove users)
                </label>
                <input
                  type="password"
                  value={ownerKey}
                  onChange={(e) => setOwnerKey(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Enter your platform owner key"
                />
              </div>

              {addUserError && (
                <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                  {addUserError}
                </div>
              )}

              <form onSubmit={handleAddUser} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <input
                    type="text"
                    value={addUserForm.username}
                    onChange={(e) => setAddUserForm({ ...addUserForm, username: e.target.value })}
                    placeholder="Username"
                    className="px-3 py-2 border border-gray-300 rounded-md"
                    required
                  />
                  <input
                    type="email"
                    value={addUserForm.email}
                    onChange={(e) => setAddUserForm({ ...addUserForm, email: e.target.value })}
                    placeholder="Email"
                    className="px-3 py-2 border border-gray-300 rounded-md"
                    required
                  />
                  <input
                    type="password"
                    value={addUserForm.password}
                    onChange={(e) => setAddUserForm({ ...addUserForm, password: e.target.value })}
                    placeholder="Password"
                    className="px-3 py-2 border border-gray-300 rounded-md"
                    required
                  />
                </div>
                <button
                  type="submit"
                  disabled={!ownerKey}
                  className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  Add User
                </button>
              </form>
            </div>

            {/* Users List */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Admin Users</h2>
              
              {usersError && (
                <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                  {usersError}
                </div>
              )}

              {usersLoading ? (
                <p className="text-gray-600">Loading users...</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Username
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Email
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Status
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Last Login
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {users.map((user) => (
                        <tr key={user.id}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                            {user.username}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {user.email}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm">
                            <span
                              className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                                user.is_active
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-red-100 text-red-800'
                              }`}
                            >
                              {user.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {user.last_login
                              ? new Date(user.last_login).toLocaleDateString()
                              : 'Never'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm">
                            <button
                              onClick={() => handleRemoveUser(user.id)}
                              disabled={!ownerKey}
                              className="text-red-600 hover:text-red-900 disabled:text-gray-400 disabled:cursor-not-allowed"
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {users.length === 0 && (
                    <p className="text-center text-gray-500 py-4">No users found</p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'email_trace' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Registration Email Trace</h2>
              <p className="text-sm text-gray-600 mb-4">Track welcome-email sends and quickly detect duplicates per school.</p>

              <div className="flex flex-wrap gap-3 mb-4">
                <input
                  type="text"
                  value={emailTraceSchoolFilter}
                  onChange={(e) => setEmailTraceSchoolFilter(e.target.value)}
                  placeholder="Filter by school ID (optional)"
                  className="px-3 py-2 border border-gray-300 rounded-md min-w-80"
                />
                <button
                  onClick={fetchRegistrationEmailTrace}
                  className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
                >
                  Refresh Trace
                </button>
              </div>

              {emailTraceError && (
                <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                  {emailTraceError}
                </div>
              )}

              {emailTraceLoading ? (
                <p className="text-gray-600">Loading trace...</p>
              ) : (
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
                          {emailTraceSummary.length === 0 && (
                            <tr>
                              <td colSpan="3" className="px-4 py-4 text-sm text-gray-500 text-center">No registration email activity found.</td>
                            </tr>
                          )}
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
                          {emailTrace.length === 0 && (
                            <tr>
                              <td colSpan="4" className="px-4 py-4 text-sm text-gray-500 text-center">No events available.</td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
