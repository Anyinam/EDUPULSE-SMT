import React, { useState, useEffect } from 'react';
import axios from 'axios';
import PlatformComplianceQueue from '../components/PlatformComplianceQueue';

export default function SuperAdminDashboard({ tokenStorageKey = 'token', embedded = false }) {
  const [tickets, setTickets] = useState([]);
  const [reply, setReply] = useState("");
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [health, setHealth] = useState(null);
  const [broadcastMsg, setBroadcastMsg] = useState("");
  const [schools, setSchools] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [verificationCases, setVerificationCases] = useState([]);
  const [editingModules, setEditingModules] = useState(null);
  const [moduleForm, setModuleForm] = useState({});

  const getAuthHeaders = () => ({
    headers: { 'Authorization': `Bearer ${localStorage.getItem(tokenStorageKey)}` }
  });

  useEffect(() => {
    fetchTickets();
    fetchHealth();
    fetchAnalytics();
    fetchSchools();
    fetchVerificationCases();
    const interval = setInterval(fetchHealth, 30000); // Poll every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchTickets = async () => {
    try {
      const res = await axios.get('/api/admin/tickets', getAuthHeaders());
      setTickets(res.data);
    } catch (err) {
      console.error("Failed to fetch tickets");
    }
  };

  const fetchHealth = async () => {
    try {
      const res = await axios.get('/api/admin/system-health', getAuthHeaders());
      setHealth(res.data);
    } catch (err) {
      console.error("Failed to fetch health stats");
    }
  };

  const fetchAnalytics = async () => {
    try {
      const res = await axios.get('/api/admin/global-analytics', getAuthHeaders());
      setAnalytics(res.data);
    } catch (err) {
      console.error("Failed to fetch global analytics");
    }
  };

  const fetchSchools = async () => {
    try {
      const res = await axios.get('/api/admin/schools', getAuthHeaders());
      setSchools(res.data);
    } catch (err) {
      console.error("Failed to fetch schools");
    }
  };

  const fetchVerificationCases = async () => {
    try {
      const res = await axios.get('/api/platform/compliance/schools?status=all', getAuthHeaders());
      setVerificationCases(Array.isArray(res.data?.cases) ? res.data.cases : []);
    } catch (err) {
      console.error('Failed to fetch verification queue summary');
    }
  };

  const sendReply = async () => {
    if (!selectedTicket || !reply) return;
    try {
      await axios.post(`/api/admin/ticket/${selectedTicket.id}/reply`, { response: reply }, getAuthHeaders());
      alert("Reply sent!");
      setReply("");
      setSelectedTicket(null);
      fetchTickets();
    } catch (err) {
      alert("Failed to send reply.");
    }
  };

  const sendBroadcast = async () => {
    if (!broadcastMsg) return;
    if (!window.confirm("Broadcast this message to ALL schools?")) return;
    try {
      await axios.post('/api/admin/broadcast', { message: broadcastMsg, type: 'Maintenance' }, getAuthHeaders());
      alert("System alert broadcasted.");
      setBroadcastMsg("");
    } catch (err) {
      alert("Failed to broadcast.");
    }
  };

  const handleToggleSchool = async (schoolId, currentStatus) => {
    if (!window.confirm(`Are you sure you want to ${currentStatus ? 'disable' : 'enable'} this school?`)) return;
    try {
      await axios.post(`/api/admin/school/${schoolId}/toggle`, {}, getAuthHeaders());
      alert("School status updated.");
      fetchSchools();
    } catch (err) {
      alert("Failed to update school status.");
    }
  };

  const handleImpersonate = async (schoolId) => {
    if (!window.confirm(`⚠️ Security Warning: You are about to log in as the Proprietor of ${schoolId}. Proceed?`)) return;
    try {
      const res = await axios.post(`/api/admin/impersonate/${schoolId}`, {}, getAuthHeaders());
      
      // Overwrite local storage with target user credentials
      localStorage.setItem('token', res.data.token);
      localStorage.setItem('school_id', res.data.school_id);
      localStorage.setItem('role', res.data.role);
      
      window.location.href = '/proprietor'; // Redirect to their dashboard
    } catch (err) {
      alert(err.response?.data?.message || "Impersonation failed.");
    }
  };

  const handleBackup = async () => {
    try {
      const res = await axios.get('/api/admin/backup', getAuthHeaders());
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `edupulse_backup_${new Date().toISOString().split('T')[0]}.sql`);
      document.body.appendChild(link);
      link.click();
    } catch (err) {
      alert("Backup failed.");
    }
  };

  const openModuleEditor = (school) => {
    setEditingModules(school);
    setModuleForm(school.modules || { canteen: true, admissions: true, finance: true, hr: true, inventory: true });
  };

  const saveModules = async () => {
    try {
      await axios.post(`/api/admin/school/${editingModules.id}/modules`, { modules: moduleForm }, getAuthHeaders());
      alert("Modules updated.");
      setEditingModules(null);
      fetchSchools();
    } catch (err) {
      alert("Failed to update modules.");
    }
  };

  const verificationReviewCount = verificationCases.filter(
    (item) => ['pending', 'review_required'].includes(String(item?.status || '').toLowerCase())
  ).length;
  const verifiedCount = verificationCases.filter(
    (item) => String(item?.status || '').toLowerCase() === 'verified'
  ).length;
  const jumpToVerificationQueue = () => {
    document.getElementById('school-verification-queue')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const wrapperClassName = embedded
    ? 'rounded-3xl bg-slate-900 p-8 text-white font-sans shadow-lg'
    : 'p-8 bg-slate-900 min-h-screen text-white font-sans';

  return (
    <div className={wrapperClassName}>
      <header className="mb-8 border-b border-slate-700 pb-4 flex justify-between items-end gap-4">
        <div>
          <h1 className="text-3xl font-black">{embedded ? 'Operations Console' : '🚀 EduPulse Command Center'}</h1>
          <p className="text-slate-400">{embedded ? 'Tenant operations, support, compliance, and platform monitoring.' : 'Software Administration & Support'}</p>
        </div>
        <button onClick={handleBackup} className="bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-lg font-bold text-sm flex items-center gap-2">
          💾 Download DB Backup
        </button>
      </header>

      {/* System Health Widget */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-lg">
           <p className="text-slate-400 text-xs font-bold uppercase mb-2">Server Status</p>
           <div className="flex items-center gap-2">
             <span className={`w-3 h-3 rounded-full ${health?.server_status === 'Operational' ? 'bg-green-500' : 'bg-red-500'}`}></span>
             <p className="text-2xl font-bold">{health?.server_status || 'Checking...'}</p>
           </div>
        </div>
        <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-lg">
           <p className="text-slate-400 text-xs font-bold uppercase mb-2">Database</p>
           <p className="text-2xl font-bold text-blue-400">{health?.db_status || '...'} <span className="text-sm text-slate-500 font-normal">({health?.db_latency})</span></p>
        </div>
        <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-lg">
           <p className="text-slate-400 text-xs font-bold uppercase mb-2">Active Connections</p>
           <p className="text-2xl font-bold text-purple-400">{health?.active_connections || '...'}</p>
        </div>
        <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-lg">
           <p className="text-slate-400 text-xs font-bold uppercase mb-2">CPU Load</p>
           <p className="text-2xl font-bold text-orange-400">{health?.cpu_load || '...'}</p>
        </div>
      </div>

      {/* Global Analytics Widget */}
      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-lg">
            <p className="text-slate-400 text-xs font-bold uppercase mb-2">Total Schools</p>
            <p className="text-3xl font-black text-white">{analytics.total_schools}</p>
          </div>
          <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-lg">
            <p className="text-slate-400 text-xs font-bold uppercase mb-2">Total Students Managed</p>
            <p className="text-3xl font-black text-white">{analytics.total_students}</p>
          </div>
        </div>
      )}

      <div className="mb-8 rounded-2xl border border-amber-600/50 bg-linear-to-r from-amber-950/70 via-slate-900 to-slate-900 p-6 shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.2em] text-amber-300">Verification Review</p>
            <h2 className="mt-1 text-2xl font-black text-white">School submissions waiting in the super admin queue</h2>
            <p className="mt-2 max-w-2xl text-sm text-slate-300">Open the compliance queue to inspect uploaded certificates and manually approve or reject school verification submissions.</p>
          </div>
          <button onClick={jumpToVerificationQueue} className="rounded-xl bg-amber-500 px-5 py-3 text-sm font-black text-slate-950 hover:bg-amber-400 transition-colors">
            Open Verification Queue
          </button>
        </div>
        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-amber-500/40 bg-slate-950/40 p-4">
            <p className="text-xs font-bold uppercase text-amber-200">Needs Review</p>
            <p className="mt-2 text-3xl font-black text-white">{verificationReviewCount}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-950/40 p-4">
            <p className="text-xs font-bold uppercase text-slate-400">Verified</p>
            <p className="mt-2 text-3xl font-black text-white">{verifiedCount}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-950/40 p-4">
            <p className="text-xs font-bold uppercase text-slate-400">Total Cases</p>
            <p className="mt-2 text-3xl font-black text-white">{verificationCases.length}</p>
          </div>
        </div>
      </div>

      {/* Tenant Overview */}
      <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-lg mb-8">
        <h3 className="font-bold text-slate-300 mb-4">🏢 Tenant Overview</h3>
        <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-400">
                <thead className="bg-slate-900 text-slate-200 uppercase font-bold">
                    <tr>
                        <th className="p-3">School ID</th>
                        <th className="p-3">Name</th>
                        <th className="p-3">Plan</th>
                        <th className="p-3">Status</th>
                        <th className="p-3">Actions</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                    {schools.map(s => (
                        <tr key={s.id} className="hover:bg-slate-700/50">
                            <td className="p-3 font-mono">{s.id}</td>
                            <td className="p-3 font-bold text-white">{s.name}</td>
                            <td className="p-3">{s.plan}</td>
                            <td className="p-3">
                                <span className={`px-2 py-1 rounded text-xs font-bold ${s.is_active ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                    {s.is_active ? 'Active' : 'Suspended'}
                                </span>
                            </td>
                            <td className="p-3 flex gap-2">
                                <button onClick={() => handleToggleSchool(s.id, s.is_active)} className={`px-3 py-1 rounded font-bold text-xs transition-colors ${s.is_active ? 'bg-red-600 text-white hover:bg-red-500' : 'bg-green-600 text-white hover:bg-green-500'}`}>
                                    {s.is_active ? 'Disable' : 'Enable'}
                                </button>
                                <button onClick={() => handleImpersonate(s.id)} className="px-3 py-1 rounded font-bold text-xs bg-blue-600 text-white hover:bg-blue-500 transition-colors">
                                    🕵️ Impersonate
                                </button>
                                <button onClick={() => openModuleEditor(s)} className="px-3 py-1 rounded font-bold text-xs bg-purple-600 text-white hover:bg-purple-500 transition-colors">
                                    ⚙️ Modules
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
      </div>

      <div id="school-verification-queue" className="mb-8 scroll-mt-8">
        <PlatformComplianceQueue tokenStorageKey={tokenStorageKey} />
      </div>

      {/* Broadcast Widget */}
      <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-lg mb-8">
        <h3 className="font-bold text-slate-300 mb-4">📢 System-Wide Broadcast</h3>
        <div className="flex gap-4">
          <input 
            className="flex-1 bg-slate-900 border border-slate-600 rounded-xl p-3 text-white focus:border-blue-500 outline-none"
            placeholder="Enter maintenance message or system alert..."
            value={broadcastMsg}
            onChange={e => setBroadcastMsg(e.target.value)}
          />
          <button onClick={sendBroadcast} className="bg-red-600 px-6 py-3 rounded-xl font-bold hover:bg-red-500 shadow-lg">
            Broadcast Alert
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Ticket List */}
        <div className="lg:col-span-1 bg-slate-800 rounded-2xl p-4 overflow-y-auto max-h-[80vh]">
          <h3 className="font-bold text-slate-300 mb-4">Incoming Tickets</h3>
          <div className="space-y-3">
            {tickets.map(t => (
              <div 
                key={t.id} 
                onClick={() => setSelectedTicket(t)}
                className={`p-4 rounded-xl cursor-pointer transition-all ${selectedTicket?.id === t.id ? 'bg-blue-600' : 'bg-slate-700 hover:bg-slate-600'}`}
              >
                <div className="flex justify-between mb-1">
                  <span className="text-xs font-bold uppercase opacity-70">{t.school_id}</span>
                  <span className={`text-[10px] px-2 rounded-full ${t.status === 'Resolved' ? 'bg-green-500 text-white' : 'bg-yellow-500 text-black'}`}>{t.status}</span>
                </div>
                <p className="font-bold text-sm truncate">{t.type}: {t.description}</p>
                <p className="text-xs text-slate-400 mt-2">{t.created_at}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Reply Panel */}
        <div className="lg:col-span-2 bg-slate-800 rounded-2xl p-8">
          {selectedTicket ? (
            <>
              <div className="mb-6">
                <h2 className="text-2xl font-bold mb-2">{selectedTicket.type}</h2>
                <p className="text-slate-400 text-sm mb-4">From Tenant: <span className="text-white font-mono">{selectedTicket.school_id}</span></p>
                <div className="bg-slate-700 p-4 rounded-xl text-slate-200 leading-relaxed">
                  {selectedTicket.description}
                </div>
              </div>

              {selectedTicket.status !== 'Resolved' ? (
                <div className="space-y-4">
                  <textarea 
                    className="w-full h-32 bg-slate-900 border border-slate-600 rounded-xl p-4 text-white focus:border-blue-500 outline-none"
                    placeholder="Type your reply here..."
                    value={reply}
                    onChange={e => setReply(e.target.value)}
                  ></textarea>
                  <button onClick={sendReply} className="bg-blue-600 px-6 py-3 rounded-xl font-bold hover:bg-blue-500 w-full">
                    Send Reply & Resolve
                  </button>
                </div>
              ) : (
                <div className="bg-green-900/30 border border-green-800 p-4 rounded-xl">
                  <p className="text-green-400 font-bold mb-1">✅ Resolved</p>
                  <p className="text-slate-300 text-sm">Your Reply: {selectedTicket.admin_response}</p>
                </div>
              )}
            </>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-500">
              Select a ticket to view details
            </div>
          )}
        </div>
      </div>

      {/* Module Editor Modal */}
      {editingModules && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 p-8 rounded-2xl w-full max-w-md border border-slate-700">
            <h3 className="text-xl font-bold mb-4">Manage Modules: {editingModules.name}</h3>
            <div className="space-y-3 mb-6">
              {['canteen', 'admissions', 'finance', 'hr', 'inventory'].map(mod => (
                <label key={mod} className="flex items-center gap-3 p-3 bg-slate-700 rounded-lg cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={moduleForm[mod] !== false}
                    onChange={e => setModuleForm({...moduleForm, [mod]: e.target.checked})}
                    className="w-5 h-5 rounded text-blue-600 focus:ring-blue-500 bg-slate-900 border-slate-600"
                  />
                  <span className="capitalize font-bold">{mod}</span>
                </label>
              ))}
            </div>
            <div className="flex gap-3">
              <button onClick={() => setEditingModules(null)} className="flex-1 py-3 rounded-xl font-bold bg-slate-700 hover:bg-slate-600">Cancel</button>
              <button onClick={saveModules} className="flex-1 py-3 rounded-xl font-bold bg-green-600 hover:bg-green-500">Save Changes</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}