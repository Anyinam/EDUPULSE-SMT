import React, { useState, useEffect } from 'react';
import { AlertCircle, Bell, Check, X } from 'lucide-react';
import axios from 'axios';

const TeacherAlerts = ({ autoRefresh = true }) => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    fetchNotifications();
    
    if (autoRefresh) {
      const interval = setInterval(fetchNotifications, 30000); // Refresh every 30 seconds
      return () => clearInterval(interval);
    }
  }, []);

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      const response = await axios.get(
        '/api/notifications',
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNotifications(response.data.notifications || []);
      setUnreadCount(response.data.unread_count || 0);
    } catch (err) {
      console.error('Failed to fetch notifications', err);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkRead = async (notificationId) => {
    try {
      const token = localStorage.getItem('token');
      await axios.post(
        `/api/notifications/${notificationId}/read`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      fetchNotifications();
    } catch (err) {
      console.error('Error marking notification as read', err);
    }
  };

  if (notifications.length === 0) {
    return null;
  }

  const displayNotifications = showAll ? notifications : notifications.slice(0, 3);

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-slate-800 flex items-center gap-2">
          <Bell size={20} className="text-blue-600" />
          Important Alerts ({unreadCount} Unread)
        </h3>
        {unreadCount > 0 && (
          <span className="bg-red-500 text-white text-xs font-bold px-2 py-1 rounded-full">
            {unreadCount}
          </span>
        )}
      </div>

      <div className="space-y-3">
        {displayNotifications.map((notif) => (
          <div
            key={notif.id}
            className={`p-4 rounded-lg border ${
              notif.type === 'promotion'
                ? 'bg-green-50 border-green-200'
                : notif.type === 'promotion_reversed'
                ? 'bg-orange-50 border-orange-200'
                : notif.type === 'repetition'
                ? 'bg-red-50 border-red-200'
                : 'bg-blue-50 border-blue-200'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <p className={`font-bold text-sm ${
                  notif.type === 'promotion'
                    ? 'text-green-800'
                    : notif.type === 'promotion_reversed'
                    ? 'text-orange-800'
                    : notif.type === 'repetition'
                    ? 'text-red-800'
                    : 'text-blue-800'
                }`}>
                  {notif.subject}
                </p>
                <p className={`text-sm mt-1 ${
                  notif.type === 'promotion'
                    ? 'text-green-700'
                    : notif.type === 'promotion_reversed'
                    ? 'text-orange-700'
                    : notif.type === 'repetition'
                    ? 'text-red-700'
                    : 'text-blue-700'
                }`}>
                  {notif.message}
                </p>
                <p className="text-xs text-slate-500 mt-2">
                  {new Date(notif.created_at).toLocaleDateString()} {new Date(notif.created_at).toLocaleTimeString()}
                </p>
              </div>

              {!notif.is_read && (
                <button
                  onClick={() => handleMarkRead(notif.id)}
                  className="p-2 bg-white rounded-lg hover:bg-slate-100 transition"
                  title="Mark as read"
                >
                  <Check size={16} className="text-green-600" />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {notifications.length > 3 && !showAll && (
        <button
          onClick={() => setShowAll(true)}
          className="mt-4 w-full p-2 text-sm font-bold text-blue-600 hover:bg-blue-50 rounded-lg transition"
        >
          View all {notifications.length} notifications
        </button>
      )}

      {showAll && notifications.length > 3 && (
        <button
          onClick={() => setShowAll(false)}
          className="mt-4 w-full p-2 text-sm font-bold text-slate-600 hover:bg-slate-100 rounded-lg transition"
        >
          Show less
        </button>
      )}
    </div>
  );
};

export default TeacherAlerts;
