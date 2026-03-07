import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function RemoteOversight() {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState({});
  const [recentPayments, setRecentPayments] = useState([]);
  const [lowStockItems, setLowStockItems] = useState([]);
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const res = await axios.get('/api/proprietor/live-feed', {
          headers: { 
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'X-School-ID': localStorage.getItem('school_id') 
          }
        });
        setLogs(res.data.logs || []);
        setStats(res.data.stats || {});
        setRecentPayments(res.data.recent_payments || []);
        setLowStockItems(res.data.low_stock_items || []);
        setLastUpdate(new Date());
      } catch (err) {
        console.error("Failed to fetch live feed", err);
        if (err.response && err.response.status === 401) {
          window.location.href = '/login';
        }
      }
    };
    
    fetchLogs();
    const interval = setInterval(fetchLogs, 15000); // Poll every 15s
    return () => clearInterval(interval);
  }, []);

  const getActionIcon = (action) => {
    if (action.includes('PAYMENT') || action.includes('CASH')) return '💰';
    if (action.includes('ATTENDANCE')) return '✅';
    if (action.includes('REPORT') || action.includes('GRADE')) return '📄';
    if (action.includes('LESSON')) return '📝';
    if (action.includes('LOGIN') || action.includes('LOGOUT')) return '🔐';
    if (action.includes('STUDENT')) return '👤';
    if (action.includes('STAFF')) return '👥';
    return '📌';
  };

  return (
    <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-slate-800 flex items-center gap-2">
          <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
          Live Operations Feed
        </h3>
        <span className="text-[10px] text-slate-400">
          {lastUpdate ? `Updated ${lastUpdate.toLocaleTimeString()}` : 'Loading...'}
        </span>
      </div>

      {/* Quick Stats Bar */}
      {stats && Object.keys(stats).length > 0 && (
        <div className="grid grid-cols-2 gap-2 mb-4 p-3 bg-slate-50 rounded-lg">
          <div className="text-center">
            <p className="text-xs text-slate-500 uppercase font-bold">Today's Revenue</p>
            <p className="text-lg font-black text-green-600">GH₵ {(stats.today_revenue || 0).toFixed(2)}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-slate-500 uppercase font-bold">Meals Count</p>
            <p className="text-lg font-black text-orange-600">{stats.canteen_count || 0}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-slate-500 uppercase font-bold">Total Students</p>
            <p className="text-lg font-black text-blue-600">{stats.total_students || 0}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-slate-500 uppercase font-bold">Unpaid Tuition</p>
            <p className="text-lg font-black text-red-600">{stats.unpaid_tuition || 0}</p>
          </div>
          {stats.pending_cash > 0 && (
            <div className="col-span-2 text-center bg-yellow-50 rounded p-2">
              <p className="text-xs text-yellow-800 font-bold">
                ⏳ {stats.pending_cash} payment(s) awaiting confirmation
              </p>
            </div>
          )}
          {stats.critical_risk_students > 0 && (
            <div className="col-span-2 text-center bg-red-50 rounded p-2">
              <p className="text-xs text-red-800 font-bold">
                🚨 {stats.critical_risk_students} at-risk student(s) need intervention
              </p>
            </div>
          )}
          {stats.low_stock_count > 0 && (
            <div className="col-span-2 text-center bg-amber-50 rounded p-2">
              <p className="text-xs text-amber-800 font-bold">
                📦 {stats.low_stock_count} inventory item(s) low on stock
              </p>
            </div>
          )}
        </div>
      )}

      {(recentPayments.length > 0 || lowStockItems.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
          {recentPayments.length > 0 && (
            <div className="border rounded-xl p-3 bg-white">
              <p className="text-xs font-bold text-slate-600 mb-2">Recent Payments</p>
              <div className="space-y-2">
                {recentPayments.map((p) => (
                  <div key={p.id} className="flex items-center justify-between text-xs">
                    <div>
                      <p className="font-semibold text-slate-700">{p.student}</p>
                      <p className="text-[10px] text-slate-400">{p.type} • {p.method}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-green-700">GH₵ {Number(p.amount || 0).toFixed(2)}</p>
                      <p className="text-[10px] text-slate-400">{p.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {lowStockItems.length > 0 && (
            <div className="border rounded-xl p-3 bg-white">
              <p className="text-xs font-bold text-slate-600 mb-2">Low Stock Alerts</p>
              <div className="space-y-2">
                {lowStockItems.map((item) => (
                  <div key={item.id} className="flex items-center justify-between text-xs">
                    <div>
                      <p className="font-semibold text-slate-700">{item.item_name}</p>
                      <p className="text-[10px] text-slate-400">SKU: {item.sku || 'N/A'}</p>
                    </div>
                    <p className="font-bold text-amber-700">{item.quantity} left</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Activity Log */}
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {logs.length === 0 ? (
          <div className="text-center py-10">
            <p className="text-slate-400 text-xs italic">System Quiet. No recent activity.</p>
            <p className="text-slate-300 text-[10px] mt-1">Last checked: {lastUpdate?.toLocaleTimeString()}</p>
          </div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="flex gap-3 items-start border-b border-slate-50 pb-3 last:border-0 hover:bg-slate-50 p-2 rounded transition-colors">
              <span className="text-lg">{getActionIcon(log.action)}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-bold text-slate-700 flex-1">
                    <span className="text-blue-600">{log.user}</span>
                    <span className="font-normal text-slate-500 mx-1">•</span>
                    <span className="text-slate-600">{log.action}</span>
                  </p>
                  <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-2 py-1 rounded shrink-0">
                    {log.time}
                  </span>
                </div>
                {log.details && (
                  <p className="text-[10px] text-slate-400 mt-1 truncate">{log.details}</p>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Auto-refresh indicator */}
      <div className="mt-4 pt-3 border-t text-center">
        <p className="text-[10px] text-slate-400">
          🔄 Auto-refreshing every 15 seconds
        </p>
      </div>
    </div>
  );
}