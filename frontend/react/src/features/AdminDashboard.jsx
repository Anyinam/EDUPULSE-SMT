import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function AdminDashboard() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminUser, setAdminUser] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [schools, setSchools] = useState([]);
  const [schoolSummary, setSchoolSummary] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [helpContent, setHelpContent] = useState({ faqs: [], tutorials: [] });
  const [ownerKey, setOwnerKey] = useState('');
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState('');

  useEffect(() => {
    // Check if user is authenticated as admin
    const token = localStorage.getItem('token');
    const adminData = localStorage.getItem('adminUser');
    const isAdminMode = localStorage.getItem('isAdmin');

    if (!token || !isAdminMode) {
      window.location.href = '/admin/login';
      return;
    }

    try {
      setAdminUser(JSON.parse(adminData));
      setIsAdmin(true);
      fetchDashboardData();
    } catch (err) {
      console.error('Failed to load admin session:', err);
      handleLogout();
    }
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };

      // Fetch schools list
      const schoolsRes = await axios.get('/api/admin/schools', { headers }).catch(() => ({ data: { schools: [] } }));
      setSchools(schoolsRes.data.schools || []);
      setSchoolSummary(schoolsRes.data.summary || null);

      // Fetch users list
      const usersRes = await axios.get('/api/admin/users', { headers }).catch(() => ({ data: { users: [] } }));
      setUsers(usersRes.data.users || []);

      // Fetch help content
      try {
        const helpRes = await axios.get('/api/platform/help-content');
        setHelpContent(helpRes.data || { faqs: [], tutorials: [] });
      } catch (err) {
        console.error('Could not fetch help content:', err);
      }
    } catch (err) {
      setError('Failed to load dashboard data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddFAQ = () => {
    setHelpContent(prev => ({
      ...prev,
      faqs: [...prev.faqs, { question: '', answer: '' }]
    }));
  };

  const handleUpdateFAQ = (index, field, value) => {
    setHelpContent(prev => {
      const updated = [...prev.faqs];
      updated[index][field] = value;
      return { ...prev, faqs: updated };
    });
  };

  const handleRemoveFAQ = (index) => {
    setHelpContent(prev => ({
      ...prev,
      faqs: prev.faqs.filter((_, i) => i !== index)
    }));
  };

  const handleAddTutorial = () => {
    setHelpContent(prev => ({
      ...prev,
      tutorials: [...prev.tutorials, { title: '', url: '' }]
    }));
  };

  const handleUpdateTutorial = (index, field, value) => {
    setHelpContent(prev => {
      const updated = [...prev.tutorials];
      updated[index][field] = value;
      return { ...prev, tutorials: updated };
    });
  };

  const handleRemoveTutorial = (index) => {
    setHelpContent(prev => ({
      ...prev,
      tutorials: prev.tutorials.filter((_, i) => i !== index)
    }));
  };

  const handleSaveHelpContent = async () => {
    setSettingsMessage('');
    setSettingsLoading(true);

    try {
      const payload = {
        faqs: helpContent.faqs,
        tutorials: helpContent.tutorials
      };

      const headers = ownerKey ? { 'X-Platform-Owner-Key': ownerKey } : {};
      
      await axios.put('/api/platform/help-content', payload, { headers });
      setSettingsMessage('✅ Help content updated successfully!');
      setOwnerKey('');
    } catch (err) {
      const msg = err.response?.data?.message || 'Failed to save help content';
      setSettingsMessage(`⚠️ ${msg}`);
    } finally {
      setSettingsLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('isAdmin');
    localStorage.removeItem('adminUser');
    window.location.href = '/login';
  };

  if (!isAdmin || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-linear-to-br from-slate-900 to-slate-700">
        <div className="text-center">
          <div className="w-16 h-16 bg-white rounded-full animate-spin mb-6 mx-auto"></div>
          <p className="text-white text-xl font-bold">Loading Admin Dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Admin Header */}
      <header className="bg-linear-to-r from-purple-900 to-blue-900 text-white shadow-xl">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-black">EDUPULSE Platform Admin</h1>
            <p className="text-purple-200 text-sm">Logged in as: <strong>{adminUser?.username}</strong></p>
          </div>
          <button
            onClick={handleLogout}
            className="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-lg font-bold transition-all"
          >
            Logout
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {error && (
          <div className="bg-red-500 text-white p-4 rounded-lg mb-6 font-bold">
            ⚠️ {error}
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="flex gap-4 mb-8 bg-slate-800 p-2 rounded-lg overflow-x-auto">
          {[
            { id: 'overview', label: '📊 Overview', icon: '📊' },
            { id: 'schools', label: '🏫 Schools', icon: '🏫' },
            { id: 'users', label: '👥 Users', icon: '👥' },
            { id: 'subscriptions', label: '💳 Subscriptions', icon: '💳' },
            { id: 'reports', label: '📈 Reports', icon: '📈' },
            { id: 'settings', label: '⚙️ Settings', icon: '⚙️' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-lg font-bold whitespace-nowrap transition-all ${
                activeTab === tab.id
                  ? 'bg-purple-600 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="space-y-6">
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-linear-to-br from-blue-600 to-blue-700 text-white p-6 rounded-xl shadow-lg">
                <p className="text-sm font-bold uppercase text-blue-200">Total Schools</p>
                <p className="text-4xl font-black mt-2">{schools.length}</p>
              </div>
              <div className="bg-linear-to-br from-green-600 to-green-700 text-white p-6 rounded-xl shadow-lg">
                <p className="text-sm font-bold uppercase text-green-200">Total Users</p>
                <p className="text-4xl font-black mt-2">{users.length}</p>
              </div>
              <div className="bg-linear-to-br from-purple-600 to-purple-700 text-white p-6 rounded-xl shadow-lg">
                <p className="text-sm font-bold uppercase text-purple-200">School OS Plus</p>
                <p className="text-4xl font-black mt-2">{schoolSummary?.school_os_plus ?? schools.filter(s => s.effective_plan === 'Premium').length}</p>
              </div>
              <div className="bg-linear-to-br from-amber-600 to-amber-700 text-white p-6 rounded-xl shadow-lg">
                <p className="text-sm font-bold uppercase text-amber-200">Active Subscriptions</p>
                <p className="text-4xl font-black mt-2">{schoolSummary?.active_subscriptions ?? schools.filter(s => s.subscription_status === 'Active').length}</p>
              </div>
            </div>
          )}

          {/* Schools Tab */}
          {activeTab === 'schools' && (
            <div className="bg-slate-800 rounded-xl shadow-lg overflow-hidden">
              <div className="bg-linear-to-r from-purple-800 to-blue-800 p-6 text-white">
                <h2 className="text-2xl font-black">Registered Schools</h2>
                <p className="text-slate-300 mt-1">Manage all schools in the platform</p>
              </div>
              <div className="p-6">
                {schools.length === 0 ? (
                  <p className="text-slate-400 text-center py-8">No schools registered yet</p>
                ) : (
                  <div className="grid grid-cols-1 gap-4">
                    {schools.map((school) => (
                      <div key={school.id} className="bg-slate-700 p-4 rounded-lg border border-slate-600">
                        <div className="flex items-start justify-between">
                          <div>
                            <h3 className="text-white font-bold text-lg">{school.name}</h3>
                            <p className="text-slate-400 text-sm">Code: {school.code}</p>
                          </div>
                          <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                            school.effective_plan === 'Premium' 
                              ? 'bg-purple-900 text-purple-200'
                              : school.effective_plan === 'Basic'
                              ? 'bg-blue-900 text-blue-200'
                              : 'bg-slate-900 text-slate-300'
                          }`}>
                            {school.effective_plan_display_name || school.plan_display_name || school.plan || 'Free'}
                          </span>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {school.trial?.active && (
                            <span className="rounded-full bg-fuchsia-900 px-3 py-1 text-xs font-bold text-fuchsia-200">
                              Trial: {school.trial.plan_display_name || school.trial.plan}
                            </span>
                          )}
                          {school.purchased_addons?.ai_pack && (
                            <span className="rounded-full bg-emerald-900 px-3 py-1 text-xs font-bold text-emerald-200">AI Pack</span>
                          )}
                          {school.purchased_addons?.automation_pack && (
                            <span className="rounded-full bg-amber-900 px-3 py-1 text-xs font-bold text-amber-200">Automation Pack</span>
                          )}
                          {!school.purchased_addons?.ai_pack && !school.purchased_addons?.automation_pack && (
                            <span className="rounded-full bg-slate-800 px-3 py-1 text-xs font-bold text-slate-300">No paid add-ons</span>
                          )}
                        </div>
                        <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-400">
                          <p>📧 {school.email || 'No email'}</p>
                          <p>👥 {school.student_count || 0} students</p>
                          <p>📅 {school.created_at ? new Date(school.created_at).toLocaleDateString() : 'Unknown'}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Users Tab */}
          {activeTab === 'users' && (
            <div className="bg-slate-800 rounded-xl shadow-lg overflow-hidden">
              <div className="bg-linear-to-r from-green-800 to-emerald-800 p-6 text-white">
                <h2 className="text-2xl font-black">Platform Users</h2>
                <p className="text-slate-300 mt-1">Manage platform admin users</p>
              </div>
              <div className="p-6">
                {users.length === 0 ? (
                  <p className="text-slate-400 text-center py-8">No users found</p>
                ) : (
                  <div className="grid grid-cols-1 gap-3">
                    {users.map((user) => (
                      <div key={user.id} className="bg-slate-700 p-4 rounded-lg border border-slate-600 flex items-center justify-between">
                        <div>
                          <h3 className="text-white font-bold">{user.username}</h3>
                          <p className="text-slate-400 text-sm">{user.email}</p>
                        </div>
                        <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                          user.is_active ? 'bg-green-900 text-green-200' : 'bg-red-900 text-red-200'
                        }`}>
                          {user.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Subscriptions Tab */}
          {activeTab === 'subscriptions' && (
            <div className="bg-slate-800 rounded-xl shadow-lg overflow-hidden">
              <div className="bg-linear-to-r from-amber-800 to-orange-800 p-6 text-white">
                <h2 className="text-2xl font-black">Subscription Management</h2>
                <p className="text-slate-300 mt-1">Monitor and manage school subscriptions</p>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-slate-700 p-4 rounded-lg">
                    <p className="text-slate-400 text-sm font-bold">School OS Plus</p>
                    <p className="text-3xl font-black text-purple-400 mt-2">
                      {schoolSummary?.school_os_plus ?? schools.filter(s => s.effective_plan === 'Premium').length}
                    </p>
                  </div>
                  <div className="bg-slate-700 p-4 rounded-lg">
                    <p className="text-slate-400 text-sm font-bold">School OS</p>
                    <p className="text-3xl font-black text-blue-400 mt-2">
                      {schoolSummary?.school_os ?? schools.filter(s => s.effective_plan === 'Basic').length}
                    </p>
                  </div>
                  <div className="bg-slate-700 p-4 rounded-lg">
                    <p className="text-slate-400 text-sm font-bold">Free</p>
                    <p className="text-3xl font-black text-slate-400 mt-2">
                      {schoolSummary?.free_tier ?? schools.filter(s => !s.effective_plan || s.effective_plan === 'Free Tier').length}
                    </p>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-slate-700 p-4 rounded-lg">
                    <p className="text-slate-400 text-sm font-bold">AI Pack Customers</p>
                    <p className="text-3xl font-black text-emerald-400 mt-2">
                      {schoolSummary?.ai_pack ?? schools.filter(s => s.purchased_addons?.ai_pack).length}
                    </p>
                  </div>
                  <div className="bg-slate-700 p-4 rounded-lg">
                    <p className="text-slate-400 text-sm font-bold">Automation Pack Customers</p>
                    <p className="text-3xl font-black text-amber-400 mt-2">
                      {schoolSummary?.automation_pack ?? schools.filter(s => s.purchased_addons?.automation_pack).length}
                    </p>
                  </div>
                  <div className="bg-slate-700 p-4 rounded-lg">
                    <p className="text-slate-400 text-sm font-bold">Active Trials</p>
                    <p className="text-3xl font-black text-fuchsia-400 mt-2">
                      {schoolSummary?.trial_schools ?? schools.filter(s => s.trial?.active).length}
                    </p>
                  </div>
                </div>
                <div className="mt-6 overflow-hidden rounded-lg border border-slate-700">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-900 text-slate-300">
                      <tr>
                        <th className="px-4 py-3 font-bold">School</th>
                        <th className="px-4 py-3 font-bold">Base Plan</th>
                        <th className="px-4 py-3 font-bold">Effective Plan</th>
                        <th className="px-4 py-3 font-bold">Paid Add-Ons</th>
                        <th className="px-4 py-3 font-bold">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700 bg-slate-800 text-slate-200">
                      {schools.map((school) => (
                        <tr key={school.id}>
                          <td className="px-4 py-3">
                            <p className="font-bold text-white">{school.name}</p>
                            <p className="text-xs text-slate-400">{school.id}</p>
                          </td>
                          <td className="px-4 py-3">{school.plan_display_name || school.plan || 'Free'}</td>
                          <td className="px-4 py-3">{school.effective_plan_display_name || school.effective_plan || school.plan || 'Free'}</td>
                          <td className="px-4 py-3">
                            {school.purchased_addons?.ai_pack || school.purchased_addons?.automation_pack
                              ? [school.purchased_addons?.ai_pack ? 'AI Pack' : null, school.purchased_addons?.automation_pack ? 'Automation Pack' : null].filter(Boolean).join(' • ')
                              : 'None'}
                          </td>
                          <td className="px-4 py-3">{school.subscription_status || school.status || 'Unknown'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Reports Tab */}
          {activeTab === 'reports' && (
            <div className="bg-slate-800 rounded-xl shadow-lg overflow-hidden">
              <div className="bg-linear-to-r from-indigo-800 to-purple-800 p-6 text-white">
                <h2 className="text-2xl font-black">System Reports</h2>
                <p className="text-slate-300 mt-1">Platform analytics and statistics</p>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-slate-700 p-6 rounded-lg">
                    <h3 className="text-white font-bold mb-4">Activity Summary</h3>
                    <div className="space-y-3 text-sm text-slate-300">
                      <p>Total Platform Users: <strong className="text-white">{users.length}</strong></p>
                      <p>Total Registered Schools: <strong className="text-white">{schools.length}</strong></p>
                      <p>Subscription Revenue: <strong className="text-purple-400">GH₵ --</strong></p>
                      <p>System Uptime: <strong className="text-green-400">99.9%</strong></p>
                    </div>
                  </div>
                  <div className="bg-slate-700 p-6 rounded-lg">
                    <h3 className="text-white font-bold mb-4">Platform Health</h3>
                    <div className="space-y-3">
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-slate-300">API Response Time</span>
                          <span className="text-green-400 font-bold">45ms</span>
                        </div>
                        <div className="bg-slate-600 h-2 rounded-full overflow-hidden">
                          <div className="bg-green-500 h-full w-3/4"></div>
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-slate-300">Database Load</span>
                          <span className="text-blue-400 font-bold">35%</span>
                        </div>
                        <div className="bg-slate-600 h-2 rounded-full overflow-hidden">
                          <div className="bg-blue-500 h-full w-1/3"></div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Settings Tab */}
          {activeTab === 'settings' && (
            <div className="bg-slate-800 rounded-xl shadow-lg overflow-hidden">
              <div className="bg-linear-to-r from-slate-700 to-slate-600 p-6 text-white">
                <h2 className="text-2xl font-black">Platform Settings & Content Management</h2>
                <p className="text-slate-300 mt-1">Manage FAQ, tutorials, and global help content</p>
              </div>
              <div className="p-6 space-y-6">
                {settingsMessage && (
                  <div className={`p-4 rounded-lg font-bold ${
                    settingsMessage.includes('✅')
                      ? 'bg-green-900 text-green-200 border border-green-700'
                      : 'bg-red-900 text-red-200 border border-red-700'
                  }`}>
                    {settingsMessage}
                  </div>
                )}

                {/* FAQ Section */}
                <div className="border border-slate-700 rounded-lg p-6 bg-slate-700">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xl font-bold text-white">❓ Frequently Asked Questions (FAQ)</h3>
                    <button
                      onClick={handleAddFAQ}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold transition-all"
                    >
                      + Add FAQ
                    </button>
                  </div>
                  
                  {helpContent.faqs.length === 0 ? (
                    <p className="text-slate-400 text-center py-6">No FAQs added yet. Click "Add FAQ" to create one.</p>
                  ) : (
                    <div className="space-y-4">
                      {helpContent.faqs.map((faq, index) => (
                        <div key={index} className="bg-slate-600 p-4 rounded-lg border border-slate-500">
                          <input
                            type="text"
                            placeholder="Question"
                            value={faq.question}
                            onChange={(e) => handleUpdateFAQ(index, 'question', e.target.value)}
                            className="w-full bg-slate-500 text-white p-2 rounded border border-slate-400 focus:border-blue-500 outline-none mb-3"
                          />
                          <textarea
                            placeholder="Answer"
                            value={faq.answer}
                            onChange={(e) => handleUpdateFAQ(index, 'answer', e.target.value)}
                            rows="3"
                            className="w-full bg-slate-500 text-white p-2 rounded border border-slate-400 focus:border-blue-500 outline-none mb-3"
                          />
                          <button
                            onClick={() => handleRemoveFAQ(index)}
                            className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white text-sm rounded font-bold transition-all"
                          >
                            Delete
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* YouTube Tutorials Section */}
                <div className="border border-slate-700 rounded-lg p-6 bg-slate-700">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xl font-bold text-white">🎥 YouTube Tutorials</h3>
                    <button
                      onClick={handleAddTutorial}
                      className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-bold transition-all"
                    >
                      + Add Tutorial
                    </button>
                  </div>

                  {helpContent.tutorials.length === 0 ? (
                    <p className="text-slate-400 text-center py-6">No tutorials added yet. Click "Add Tutorial" to create one.</p>
                  ) : (
                    <div className="space-y-4">
                      {helpContent.tutorials.map((tutorial, index) => (
                        <div key={index} className="bg-slate-600 p-4 rounded-lg border border-slate-500">
                          <input
                            type="text"
                            placeholder="Tutorial Title"
                            value={tutorial.title}
                            onChange={(e) => handleUpdateTutorial(index, 'title', e.target.value)}
                            className="w-full bg-slate-500 text-white p-2 rounded border border-slate-400 focus:border-red-500 outline-none mb-3"
                          />
                          <input
                            type="url"
                            placeholder="YouTube URL (https://youtube.com/...)"
                            value={tutorial.url}
                            onChange={(e) => handleUpdateTutorial(index, 'url', e.target.value)}
                            className="w-full bg-slate-500 text-white p-2 rounded border border-slate-400 focus:border-red-500 outline-none mb-3"
                          />
                          <button
                            onClick={() => handleRemoveTutorial(index)}
                            className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white text-sm rounded font-bold transition-all"
                          >
                            Delete
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Platform Owner Authorization */}
                <div className="border border-slate-700 rounded-lg p-6 bg-slate-700">
                  <h3 className="text-lg font-bold text-white mb-4">🔐 Platform Owner Authorization</h3>
                  <p className="text-slate-400 text-sm mb-4">Enter Platform Owner Key to save changes (find this in your .env file)</p>
                  <input
                    type="password"
                    placeholder="PLATFORM_OWNER_KEY"
                    value={ownerKey}
                    onChange={(e) => setOwnerKey(e.target.value)}
                    className="w-full bg-slate-600 text-white p-2 rounded border border-slate-500 focus:border-purple-500 outline-none mb-4"
                  />
                  <button
                    onClick={handleSaveHelpContent}
                    disabled={settingsLoading || !ownerKey.trim()}
                    className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white font-bold py-3 rounded-lg transition-all"
                  >
                    {settingsLoading ? '💾 Saving...' : '💾 Save All Changes'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
