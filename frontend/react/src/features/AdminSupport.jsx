import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function AdminSupport() {
  const [tickets, setTickets] = useState([]);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [response, setResponse] = useState('');
  const [filter, setFilter] = useState('all'); // 'all', 'Open', 'Resolved'

  const getAuthHeaders = () => ({
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  useEffect(() => {
    fetchTickets();
  }, []);

  const fetchTickets = async () => {
    try {
      const res = await axios.get('/api/admin/tickets', getAuthHeaders());
      setTickets(res.data);
    } catch (err) {
      console.error('Failed to fetch tickets:', err);
      alert('Failed to load tickets. Check console for errors.');
    }
  };

  const sendReply = async (e) => {
    e.preventDefault();
    if (!response.trim()) {
      alert('Please enter a response');
      return;
    }

    try {
      await axios.post(
        `/api/admin/ticket/${selectedTicket.id}/reply`,
        { response, status: 'Resolved' },
        getAuthHeaders()
      );
      alert('✅ Reply sent! User will receive an email notification.');
      setResponse('');
      setSelectedTicket(null);
      fetchTickets(); // Refresh list
    } catch (err) {
      alert('❌ Failed to send reply');
    }
  };

  const filteredTickets = filter === 'all' 
    ? tickets 
    : tickets.filter(t => t.status === filter);

  return (
    <div className="p-8 bg-slate-50 min-h-screen">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-slate-800">Support Tickets</h1>
          <button 
            onClick={fetchTickets} 
            className="bg-blue-900 text-white px-4 py-2 rounded-lg hover:bg-blue-800 font-semibold"
          >
            🔄 Refresh
          </button>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2 mb-6">
          {['all', 'Open', 'Resolved'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg font-semibold transition-all ${
                filter === f 
                  ? 'bg-blue-900 text-white' 
                  : 'bg-white text-slate-600 hover:bg-slate-100'
              }`}
            >
              {f === 'all' ? 'All Tickets' : f}
              <span className="ml-2 text-xs">
                ({f === 'all' ? tickets.length : tickets.filter(t => t.status === f).length})
              </span>
            </button>
          ))}
        </div>

        {/* Tickets Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Ticket List */}
          <div className="space-y-4">
            {filteredTickets.length === 0 ? (
              <div className="bg-white p-8 rounded-xl text-center text-slate-400">
                No tickets found
              </div>
            ) : (
              filteredTickets.map(ticket => (
                <div
                  key={ticket.id}
                  onClick={() => setSelectedTicket(ticket)}
                  className={`bg-white p-6 rounded-xl shadow-sm border-2 cursor-pointer hover:shadow-md transition-all ${
                    selectedTicket?.id === ticket.id 
                      ? 'border-blue-900' 
                      : 'border-transparent'
                  }`}
                >
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <span className="text-xs font-bold text-slate-500 uppercase">
                        Ticket #{ticket.id}
                      </span>
                      <h3 className="text-sm font-bold text-slate-700 mt-1">
                        {ticket.type}
                      </h3>
                    </div>
                    <span className={`text-xs px-3 py-1 rounded-full font-bold ${
                      ticket.status === 'Resolved' 
                        ? 'bg-green-100 text-green-700' 
                        : 'bg-yellow-100 text-yellow-700'
                    }`}>
                      {ticket.status}
                    </span>
                  </div>

                  <p className="text-sm text-slate-600 mb-3 line-clamp-2">
                    {ticket.description}
                  </p>

                  <div className="flex justify-between items-center text-xs text-slate-400">
                    <span>🏫 {ticket.school_id}</span>
                    <span>📅 {new Date(ticket.created_at).toLocaleDateString()}</span>
                  </div>

                  {ticket.admin_response && (
                    <div className="mt-3 bg-blue-50 p-2 rounded text-xs text-blue-800">
                      ✅ Replied
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Ticket Details & Reply Form */}
          <div className="sticky top-8">
            {selectedTicket ? (
              <div className="bg-white p-6 rounded-xl shadow-lg">
                <div className="flex justify-between items-start mb-4">
                  <h2 className="text-xl font-bold text-slate-800">
                    Ticket #{selectedTicket.id}
                  </h2>
                  <button 
                    onClick={() => setSelectedTicket(null)}
                    className="text-slate-400 hover:text-slate-600 text-xl"
                  >
                    ×
                  </button>
                </div>

                <div className="space-y-4 mb-6">
                  <div className="bg-slate-50 p-4 rounded-lg">
                    <p className="text-xs font-bold text-slate-500 uppercase mb-2">
                      Type
                    </p>
                    <p className="text-sm text-slate-700">{selectedTicket.type}</p>
                  </div>

                  <div className="bg-slate-50 p-4 rounded-lg">
                    <p className="text-xs font-bold text-slate-500 uppercase mb-2">
                      Description
                    </p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">
                      {selectedTicket.description}
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-slate-50 p-4 rounded-lg">
                      <p className="text-xs font-bold text-slate-500 uppercase mb-1">
                        School ID
                      </p>
                      <p className="text-sm text-slate-700">{selectedTicket.school_id}</p>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-lg">
                      <p className="text-xs font-bold text-slate-500 uppercase mb-1">
                        Status
                      </p>
                      <p className="text-sm text-slate-700">{selectedTicket.status}</p>
                    </div>
                  </div>

                  {selectedTicket.admin_response && (
                    <div className="bg-green-50 p-4 rounded-lg border-2 border-green-200">
                      <p className="text-xs font-bold text-green-700 uppercase mb-2">
                        Your Previous Response
                      </p>
                      <p className="text-sm text-green-900 whitespace-pre-wrap">
                        {selectedTicket.admin_response}
                      </p>
                    </div>
                  )}
                </div>

                {/* Reply Form */}
                <form onSubmit={sendReply} className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
                      {selectedTicket.admin_response ? 'Update Response' : 'Your Response'}
                    </label>
                    <textarea
                      value={response}
                      onChange={(e) => setResponse(e.target.value)}
                      placeholder="Type your response here..."
                      className="w-full p-4 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 h-32 resize-none"
                      required
                    />
                  </div>

                  <button
                    type="submit"
                    className="w-full bg-blue-900 text-white py-3 rounded-lg font-bold hover:bg-blue-800 shadow-lg"
                  >
                    📧 Send Reply & Notify User
                  </button>

                  <p className="text-xs text-slate-400 text-center">
                    User will receive email notification automatically
                  </p>
                </form>
              </div>
            ) : (
              <div className="bg-white p-12 rounded-xl shadow-lg text-center text-slate-400">
                <p className="text-lg mb-2">👈 Select a ticket to view details</p>
                <p className="text-sm">Click any ticket on the left to respond</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
