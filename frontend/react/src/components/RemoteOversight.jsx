import React, { useState, useEffect } from 'react';
import axios from 'axios';
import FeatureLock from './FeatureLock';

export default function RemoteOversight() {
  return <FeatureLock feature="payment_tracking" requiredPlan="Basic"><RemoteOversightContent /></FeatureLock>;
}

function RemoteOversightContent() {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState({});
  const [recentPayments, setRecentPayments] = useState([]);
  const [lowStockItems, setLowStockItems] = useState([]);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [searchText, setSearchText] = useState('');
  const [eventFilter, setEventFilter] = useState('all');
  const [timeWindow, setTimeWindow] = useState('all');
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [streamStatus, setStreamStatus] = useState('connecting');
  const [thresholds, setThresholds] = useState({
    unpaid_tuition: 10,
    pending_cash: 5,
    low_stock_count: 3,
    critical_risk_students: 3,
  });
  const [editingThresholds, setEditingThresholds] = useState(false);
  const [acknowledgedAlertIds, setAcknowledgedAlertIds] = useState([]);

  const STALE_AFTER_MS = 45000;

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id')
  });

  const getActionCategory = (action = '') => {
    const normalized = String(action).toUpperCase();
    if (normalized.includes('PAYMENT') || normalized.includes('CASH') || normalized.includes('BANK')) return 'finance';
    if (normalized.includes('ATTENDANCE')) return 'attendance';
    if (normalized.includes('REPORT') || normalized.includes('GRADE') || normalized.includes('EXAM') || normalized.includes('LESSON')) return 'academics';
    if (normalized.includes('WHATSAPP') || normalized.includes('EMAIL') || normalized.includes('MESSAGE')) return 'communication';
    if (normalized.includes('INVENTORY') || normalized.includes('STOCK')) return 'inventory';
    return 'general';
  };

  useEffect(() => {
    let isMounted = true;
    let eventSource = null;

    const fetchSnapshot = async () => {
      try {
        const res = await axios.get('/api/proprietor/live-feed', {
          headers: getAuthHeaders()
        });
        if (!isMounted) return;
        const incomingLogs = Array.isArray(res.data.logs) ? res.data.logs : [];
        setLogs(incomingLogs);
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

    const startSSE = async () => {
      try {
        const tokenRes = await axios.get('/api/proprietor/live-events/token', { headers: getAuthHeaders() });
        const streamToken = tokenRes.data?.stream_token;
        if (!streamToken) return;

      const sinceId = logs[0]?.id || 0;
      const url = `/api/proprietor/live-events?stream_token=${encodeURIComponent(streamToken)}&since_id=${encodeURIComponent(sinceId)}`;
      eventSource = new EventSource(url);

      eventSource.onopen = () => {
        if (isMounted) setStreamStatus('live');
      };

      eventSource.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const payload = JSON.parse(event.data || '{}');
          if (payload.type === 'new_logs' && Array.isArray(payload.logs) && payload.logs.length > 0) {
            setLogs((prev) => {
              const merged = [...payload.logs.reverse(), ...prev];
              const deduped = [];
              const seen = new Set();
              for (const item of merged) {
                const key = item.id || `${item.action}-${item.time}-${item.details}`;
                if (!seen.has(key)) {
                  seen.add(key);
                  deduped.push(item);
                }
              }
              return deduped.slice(0, 50);
            });
            setLastUpdate(new Date());
          }
        } catch (parseErr) {
          console.error('Failed to parse SSE payload', parseErr);
        }
      };

      eventSource.onerror = () => {
        if (isMounted) setStreamStatus('reconnecting');
      };
      } catch (err) {
        console.error('Failed to initialize live stream token', err);
        if (isMounted) setStreamStatus('reconnecting');
      }
    };

    const fetchThresholds = async () => {
      try {
        const res = await axios.get('/api/proprietor/live-dashboard/thresholds', { headers: getAuthHeaders() });
        setThresholds((prev) => ({ ...prev, ...(res.data || {}) }));
      } catch (err) {
        console.error('Failed to fetch thresholds', err);
      }
    };

    const fetchAcknowledgedAlerts = async () => {
      try {
        const res = await axios.get('/api/proprietor/live-dashboard/alerts/ack', { headers: getAuthHeaders() });
        setAcknowledgedAlertIds(Array.isArray(res.data?.acknowledged_alert_ids) ? res.data.acknowledged_alert_ids : []);
      } catch (err) {
        console.error('Failed to fetch acknowledged alerts', err);
      }
    };

    fetchSnapshot();
    fetchThresholds();
    fetchAcknowledgedAlerts();
    startSSE();
    const interval = setInterval(fetchSnapshot, 15000);

    return () => {
      isMounted = false;
      clearInterval(interval);
      if (eventSource) {
        eventSource.close();
      }
    };
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

  const isStale = lastUpdate ? (Date.now() - lastUpdate.getTime() > STALE_AFTER_MS) : false;
  const nowMs = Date.now();

  const filteredLogs = logs.filter((log) => {
    const category = getActionCategory(log.action);
    if (eventFilter !== 'all' && category !== eventFilter) return false;

    if (searchText.trim()) {
      const q = searchText.trim().toLowerCase();
      const text = `${log.user || ''} ${log.action || ''} ${log.details || ''}`.toLowerCase();
      if (!text.includes(q)) return false;
    }

    if (timeWindow !== 'all' && log.timestamp_iso) {
      const ts = new Date(log.timestamp_iso).getTime();
      const delta = nowMs - ts;
      if (timeWindow === '15m' && delta > 15 * 60 * 1000) return false;
      if (timeWindow === '1h' && delta > 60 * 60 * 1000) return false;
      if (timeWindow === '24h' && delta > 24 * 60 * 60 * 1000) return false;
    }

    return true;
  });

  const thresholdAlerts = [
    stats.unpaid_tuition >= thresholds.unpaid_tuition
      ? { id: `unpaid_tuition:${stats.unpaid_tuition}`, message: `High tuition risk: ${stats.unpaid_tuition} students unpaid` }
      : null,
    stats.pending_cash >= thresholds.pending_cash
      ? { id: `pending_cash:${stats.pending_cash}`, message: `Cash approvals backlog: ${stats.pending_cash} pending` }
      : null,
    stats.low_stock_count >= thresholds.low_stock_count
      ? { id: `low_stock_count:${stats.low_stock_count}`, message: `Inventory pressure: ${stats.low_stock_count} low-stock items` }
      : null,
    stats.critical_risk_students >= thresholds.critical_risk_students
      ? { id: `critical_risk_students:${stats.critical_risk_students}`, message: `Intervention needed: ${stats.critical_risk_students} at-risk students` }
      : null,
  ].filter(Boolean).filter((alert) => !acknowledgedAlertIds.includes(alert.id));

  const saveThresholds = async () => {
    try {
      const payload = {
        unpaid_tuition: Number(thresholds.unpaid_tuition || 0),
        pending_cash: Number(thresholds.pending_cash || 0),
        low_stock_count: Number(thresholds.low_stock_count || 0),
        critical_risk_students: Number(thresholds.critical_risk_students || 0),
      };
      const res = await axios.put('/api/proprietor/live-dashboard/thresholds', payload, { headers: getAuthHeaders() });
      setThresholds((prev) => ({ ...prev, ...(res.data || {}) }));
      setEditingThresholds(false);
      alert('Thresholds updated successfully.');
    } catch (err) {
      console.error('Failed to save thresholds', err);
      alert('Failed to save thresholds.');
    }
  };

  const acknowledgeAlert = async (alertId) => {
    try {
      await axios.post('/api/proprietor/live-dashboard/alerts/ack', { alert_id: alertId }, { headers: getAuthHeaders() });
      setAcknowledgedAlertIds((prev) => Array.from(new Set([...prev, alertId])));
    } catch (err) {
      console.error('Failed to acknowledge alert', err);
      alert('Failed to acknowledge alert.');
    }
  };

  return (
    <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-slate-800 flex items-center gap-2">
          <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
          Live Operations Feed
        </h3>
        <div className="text-right">
          <p className={`text-[10px] font-semibold ${isStale ? 'text-red-500' : 'text-slate-400'}`}>
            {lastUpdate ? `Updated ${lastUpdate.toLocaleTimeString()}` : 'Loading...'}
          </p>
          <p className={`text-[10px] ${streamStatus === 'live' ? 'text-green-600' : 'text-amber-600'}`}>
            {streamStatus === 'live' ? 'Live stream connected' : 'Reconnecting stream...'}
          </p>
        </div>
      </div>

      {thresholdAlerts.length > 0 && (
        <div className="mb-4 space-y-2">
          {thresholdAlerts.map((alertItem) => (
            <div key={alertItem.id} className="text-xs font-semibold text-red-800 bg-red-50 border border-red-200 rounded px-3 py-2 flex items-center justify-between gap-2">
              <span>{alertItem.message}</span>
              <button
                type="button"
                onClick={() => acknowledgeAlert(alertItem.id)}
                className="text-[10px] px-2 py-1 rounded bg-red-100 hover:bg-red-200"
              >
                Acknowledge
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="mb-4 p-3 border rounded-xl bg-white">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-bold text-slate-700">Alert Threshold Settings</p>
          <button
            type="button"
            onClick={() => setEditingThresholds((v) => !v)}
            className="text-[10px] px-2 py-1 rounded bg-slate-100 hover:bg-slate-200"
          >
            {editingThresholds ? 'Close' : 'Edit'}
          </button>
        </div>
        {editingThresholds && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <input type="number" min="0" value={thresholds.unpaid_tuition} onChange={(e) => setThresholds((p) => ({ ...p, unpaid_tuition: e.target.value }))} className="text-xs p-2 border rounded" placeholder="Unpaid tuition threshold" />
            <input type="number" min="0" value={thresholds.pending_cash} onChange={(e) => setThresholds((p) => ({ ...p, pending_cash: e.target.value }))} className="text-xs p-2 border rounded" placeholder="Pending cash threshold" />
            <input type="number" min="0" value={thresholds.low_stock_count} onChange={(e) => setThresholds((p) => ({ ...p, low_stock_count: e.target.value }))} className="text-xs p-2 border rounded" placeholder="Low stock threshold" />
            <input type="number" min="0" value={thresholds.critical_risk_students} onChange={(e) => setThresholds((p) => ({ ...p, critical_risk_students: e.target.value }))} className="text-xs p-2 border rounded" placeholder="Critical student threshold" />
            <button type="button" onClick={saveThresholds} className="md:col-span-2 text-xs px-3 py-2 rounded bg-blue-600 text-white hover:bg-blue-700">Save Thresholds</button>
          </div>
        )}
      </div>

      {/* Quick Stats Bar */}
      {stats && Object.keys(stats).length > 0 && (
        <div className="grid grid-cols-2 gap-2 mb-4 p-3 bg-slate-50 rounded-lg">
          <div className="text-center">
            <p className="text-xs text-slate-500 uppercase font-bold">Today's Revenue</p>
            <p className="text-lg font-black text-green-600">GH₵ {(stats.today_revenue || 0).toFixed(2)}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-slate-500 uppercase font-bold">Student Meals Today</p>
            <p className="text-lg font-black text-orange-600">{stats.student_meals || 0}</p>
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

      <div className="mb-3 p-3 border rounded-xl bg-slate-50">
        <p className="text-xs font-bold text-slate-600 mb-2">Unified Timeline Filters</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <input
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search by user, action, details"
            className="text-xs p-2 border rounded"
          />
          <select
            value={eventFilter}
            onChange={(e) => setEventFilter(e.target.value)}
            className="text-xs p-2 border rounded"
          >
            <option value="all">All categories</option>
            <option value="academics">Academics</option>
            <option value="finance">Finance</option>
            <option value="attendance">Attendance</option>
            <option value="inventory">Inventory</option>
            <option value="communication">Communication</option>
            <option value="general">General</option>
          </select>
          <select
            value={timeWindow}
            onChange={(e) => setTimeWindow(e.target.value)}
            className="text-xs p-2 border rounded"
          >
            <option value="all">Any time</option>
            <option value="15m">Last 15 mins</option>
            <option value="1h">Last 1 hour</option>
            <option value="24h">Last 24 hours</option>
          </select>
        </div>
      </div>
      
      {/* Activity Log */}
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {filteredLogs.length === 0 ? (
          <div className="text-center py-10">
            <p className="text-slate-400 text-xs italic">System Quiet. No recent activity.</p>
            <p className="text-slate-300 text-[10px] mt-1">Last checked: {lastUpdate?.toLocaleTimeString()}</p>
          </div>
        ) : (
          filteredLogs.map((log, i) => (
            <button
              type="button"
              key={log.id || i}
              onClick={() => setSelectedEvent(log)}
              className="w-full text-left flex gap-3 items-start border-b border-slate-50 pb-3 last:border-0 hover:bg-slate-50 p-2 rounded transition-colors"
            >
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
            </button>
          ))
        )}
      </div>

      {/* Auto-refresh indicator */}
      <div className="mt-4 pt-3 border-t text-center">
        <p className="text-[10px] text-slate-400">
          🔄 Snapshot every 15s + push stream for new events
        </p>
      </div>

      {selectedEvent && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setSelectedEvent(null)}>
          <div className="bg-white rounded-2xl w-full max-w-xl p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-3">
              <h4 className="text-sm font-black text-slate-800">Event Details</h4>
              <button className="text-xs px-2 py-1 rounded bg-slate-100" onClick={() => setSelectedEvent(null)}>Close</button>
            </div>
            <div className="space-y-2 text-xs">
              <p><span className="font-semibold">User:</span> {selectedEvent.user || 'Unknown'}</p>
              <p><span className="font-semibold">Action:</span> {selectedEvent.action || '-'}</p>
              <p><span className="font-semibold">Category:</span> {getActionCategory(selectedEvent.action)}</p>
              <p><span className="font-semibold">Time:</span> {selectedEvent.timestamp_iso ? new Date(selectedEvent.timestamp_iso).toLocaleString() : selectedEvent.time}</p>
              <div>
                <p className="font-semibold mb-1">Details:</p>
                <div className="p-2 border rounded bg-slate-50 text-slate-700 whitespace-pre-wrap">{selectedEvent.details || 'No details'}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}