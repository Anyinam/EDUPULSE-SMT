import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function SupportModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('new'); // 'new' or 'history'
  const [form, setForm] = useState({ type: 'Bug Report', description: '' });
  const [history, setHistory] = useState([]);

  const getAuthHeaders = () => ({
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  useEffect(() => {
    if (isOpen && activeTab === 'history') {
      axios.get('/api/support/history', getAuthHeaders())
        .then(res => setHistory(res.data))
        .catch(err => console.error(err));
    }
  }, [isOpen, activeTab]);

  const sendTicket = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post('/api/support/ticket', form, getAuthHeaders());
      setForm({ type: 'Bug Report', description: '' });
      setActiveTab('history'); // Switch to history tab to show submitted ticket
      
      // Show success message (modern toast-style alert)
      const successMsg = response.data.message || "Support ticket submitted successfully. Check your email for confirmation.";
      alert("✅ " + successMsg);
      
      // Refresh history
      axios.get('/api/support/history', getAuthHeaders())
        .then(res => setHistory(res.data))
        .catch(err => console.error(err));
        
    } catch (err) {
      alert("❌ Failed to submit ticket. Please try again.");
    }
  };

  return (
    <>
      <button 
        onClick={() => setIsOpen(true)} 
        className="fixed bottom-6 right-6 bg-blue-900 text-white p-4 rounded-full shadow-2xl hover:bg-blue-800 transition-all z-50 flex items-center gap-2 font-bold"
      >
        <span>❓</span> <span className="hidden md:inline">Help & Support</span>
      </button>

      {isOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
            <div className="bg-slate-50 p-6 border-b border-slate-100 flex justify-between items-center">
              <h3 className="text-xl font-bold text-slate-800">Help & Support</h3>
              <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-slate-600 font-bold text-xl">×</button>
            </div>
            
            <div className="flex border-b border-slate-100">
              <button onClick={() => setActiveTab('new')} className={`flex-1 py-3 text-sm font-bold ${activeTab === 'new' ? 'text-blue-900 border-b-2 border-blue-900' : 'text-slate-400'}`}>New Ticket</button>
              <button onClick={() => setActiveTab('history')} className={`flex-1 py-3 text-sm font-bold ${activeTab === 'history' ? 'text-blue-900 border-b-2 border-blue-900' : 'text-slate-400'}`}>My Tickets</button>
            </div>
            
            {activeTab === 'new' ? (
              <form onSubmit={sendTicket} className="p-6 space-y-4">
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Ticket Type</label>
                  <select 
                    className="w-full p-3 border border-slate-200 rounded-xl bg-slate-50 outline-none focus:ring-2 focus:ring-blue-500"
                    value={form.type}
                    onChange={e => setForm({...form, type: e.target.value})}
                  >
                    <option>Bug Report</option>
                    <option>Feature Request</option>
                    <option>General Inquiry</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Description</label>
                  <textarea 
                    className="w-full p-3 border border-slate-200 rounded-xl bg-slate-50 outline-none focus:ring-2 focus:ring-blue-500 h-32 resize-none"
                    placeholder="Describe your issue or idea..."
                    value={form.description}
                    onChange={e => setForm({...form, description: e.target.value})}
                    required
                  ></textarea>
                </div>

                <div className="pt-2">
                  <button className="w-full bg-blue-900 text-white py-3 rounded-xl font-bold hover:bg-blue-800 shadow-lg">
                    Submit Ticket
                  </button>
                </div>
              </form>
            ) : (
              <div className="p-6 h-80 overflow-y-auto space-y-4">
                {history.length === 0 ? (
                  <p className="text-center text-slate-400 text-sm mt-10">No tickets found.</p>
                ) : (
                  history.map(t => (
                    <div key={t.id} className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-xs font-bold text-slate-500 uppercase">{t.type}</span>
                        <span className={`text-[10px] px-2 py-1 rounded-full font-bold ${t.status === 'Resolved' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>{t.status}</span>
                      </div>
                      <p className="text-sm text-slate-700 mb-3">{t.description}</p>
                      {t.admin_response && (
                        <div className="bg-blue-100 p-3 rounded-lg border border-blue-200">
                          <p className="text-xs font-bold text-blue-800 mb-1">👨‍💻 Admin Reply:</p>
                          <p className="text-xs text-blue-900">{t.admin_response}</p>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}