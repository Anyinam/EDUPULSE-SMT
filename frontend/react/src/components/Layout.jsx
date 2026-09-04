import React, { useState, useEffect } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import { Logo } from './Logo';
import SupportModal from './Support';
import SchoolVerifiedBadge from './SchoolVerifiedBadge';
import { useBranding } from '../hooks/useBranding';
import useEffectiveSubscriptionPlan from '../hooks/useEffectiveSubscriptionPlan';

export default function Layout() {
  const location = useLocation();
  const role = localStorage.getItem('role');
  const { isPremium: canAccessPremiumInsights } = useEffectiveSubscriptionPlan();
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

  const roles = safeJsonParse(localStorage.getItem('roles'), []);
  const { branding } = useBranding({ refreshOnMount: true });
  const modules = safeJsonParse(localStorage.getItem('enabled_modules'), null) || { canteen: true, admissions: true, finance: true, hr: true, inventory: true };
  const assignedClass = localStorage.getItem('assigned_class');

  const hasRole = (r) => roles.includes(r) || role === r;

  const [notifications, setNotifications] = useState([]);
  const [showNotifs, setShowNotifs] = useState(false);
  const [hasUnread, setHasUnread] = useState(false);
  const [dismissedSystemAlert, setDismissedSystemAlert] = useState('');
  const [expandedMenus, setExpandedMenus] = useState({}); // Track expanded menu sections
  const currentSystemAlert = notifications.find((notification) => notification.isSystem);

  // Developer-only access check
  const isDeveloper = (
    window.location.hostname === 'localhost' || 
    window.location.hostname === '127.0.0.1' ||
    role === 'super-admin' ||
    localStorage.getItem('dev_mode') === 'true'
  );

  const toggleMenu = (menuName) => {
    setExpandedMenus(prev => ({
      ...prev,
      [menuName]: !prev[menuName]
    }));
  };

  useEffect(() => {
    const requiresPasswordReset = localStorage.getItem('requires_password_reset') === 'true';
    if (requiresPasswordReset && location.pathname !== '/first-login-password') {
      window.location.href = '/first-login-password';
      return;
    }
  }, [location.pathname]);

  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        const res = await axios.get('/api/staff/notifications', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
                'X-School-ID': localStorage.getItem('school_id')
            }
        });
        
        const newNotifs = [];
        if (res.data.system_alert) {
            newNotifs.push({ ...res.data.system_alert, isSystem: true });
        }
        if (res.data.latest_notice) {
            newNotifs.push(res.data.latest_notice);
        }
        setNotifications(newNotifs);
        setHasUnread(newNotifs.length > 0);
      } catch (err) {
        console.error("Failed to fetch notifications");
      }
    };

    fetchNotifications();
    const interval = setInterval(fetchNotifications, 60000); // Poll every minute
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!currentSystemAlert) {
      setDismissedSystemAlert('');
      return;
    }

    const currentAlertMessage = currentSystemAlert.message || '';
    if (currentAlertMessage !== dismissedSystemAlert) {
      return;
    }
  }, [currentSystemAlert, dismissedSystemAlert]);

  // Keyboard shortcut for dev mode toggle (Ctrl+Shift+D)
  useEffect(() => {
    const handleKeyPress = (e) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'D') {
        e.preventDefault();
        const currentDevMode = localStorage.getItem('dev_mode') === 'true';
        if (currentDevMode) {
          localStorage.removeItem('dev_mode');
          alert('🔧 Developer mode disabled');
        } else {
          localStorage.setItem('dev_mode', 'true');
          alert('🔧 Developer mode enabled');
        }
        window.location.reload();
      }
    };
    
    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, []);

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Dynamic Sidebar based on Branding & Access Control */}
      <nav 
        className="w-64 text-white p-6 shadow-2xl flex flex-col"
        style={{ backgroundColor: 'var(--school-primary, #1e3a8a)' }}
      >
        <div className="flex items-center gap-3 mb-10">
          <Logo size="md" variant="default" />
          <div>
            <h2 className="text-xl font-bold tracking-tight uppercase">{branding.name || 'EduPulse SMT'}</h2>
            <div className="mt-2">
              <SchoolVerifiedBadge verified={Boolean(branding.is_verified)} compact className="border-white/20 bg-white/10 text-white" />
            </div>
          </div>
        </div>

        <ul className="space-y-4 flex-1 text-sm font-medium">
          {/* DASHBOARDS SECTION */}
          <li className="text-[10px] uppercase tracking-wider text-white/60 font-bold">📊 Dashboards</li>
          
          {/* Proprietor */}
          {hasRole('proprietor') && (
            <>
              {modules.finance && <li><Link to="/proprietor" className="hover:text-blue-200 pl-3">📊 Dashboard & Insights</Link></li>}
              {modules.finance && <li><Link to="/proprietor?tab=payment-tracker" className="hover:text-blue-200 pl-3">💳 Payment Tracker</Link></li>}
              {modules.finance && <li><Link to="/proprietor?tab=finance" className="hover:text-blue-200 pl-3">📈 Transaction History</Link></li>}
              {canAccessPremiumInsights && <li><Link to="/proprietor?tab=exam-intelligence" className="hover:text-blue-200 pl-3">📘 Exam Intelligence</Link></li>}
              {modules.finance && canAccessPremiumInsights && <li><Link to="/proprietor?tab=rescue-activity" className="hover:text-blue-200 pl-3">🚨 Rescue Activity</Link></li>}
              {modules.finance && <li><Link to="/proprietor?tab=audit" className="hover:text-blue-200 pl-3">🔒 Audit Report</Link></li>}
              {modules.admissions && <li><Link to="/proprietor?tab=terminal-reports" className="hover:text-blue-200 pl-3">📄 Terminal Reports</Link></li>}
              {modules.hr && <li><Link to="/proprietor?tab=staff" className="hover:text-blue-200 pl-3">👥 Staff & HR</Link></li>}
              {modules.inventory && <li><Link to="/proprietor?tab=inventory" className="hover:text-blue-200 pl-3">📦 Inventory</Link></li>}
              {modules.admissions && <li><Link to="/proprietor?tab=admissions" className="hover:text-blue-200 pl-3">🎓 Admissions</Link></li>}
              <li><Link to="/proprietor?tab=students" className="hover:text-blue-200 pl-3">📚 Students</Link></li>
              <li><Link to="/proprietor?tab=verification" className="hover:text-blue-200 pl-3">🏛️ School Verification</Link></li>
              <li><Link to="/proprietor?tab=subscription" className="hover:text-blue-200 pl-3">💳 Subscription</Link></li>
              <li><Link to="/proprietor?tab=calendar" className="hover:text-blue-200 pl-3">📅 Holiday Calendar</Link></li>
            </>
          )}

          {/* Headmaster */}
          {hasRole('headmaster') && (
            <>
              <li><Link to="/headmaster" className="hover:text-blue-200 pl-3 transition-colors">🎓 Headmaster Dashboard</Link></li>
              {canAccessPremiumInsights && <li><Link to="/headmaster?tab=exam-intelligence" className="hover:text-blue-200 pl-3 transition-colors">📘 Exam Intelligence</Link></li>}
              {canAccessPremiumInsights && <li><Link to="/headmaster?tab=rescue-activity" className="hover:text-blue-200 pl-3 transition-colors">🚨 Rescue Activity</Link></li>}
              <li><Link to="/headmaster/admissions" className="hover:text-blue-200 pl-3 transition-colors">🎓 Admissions</Link></li>
              {hasRole('homeroom') && <li><Link to="/report-builder" className="hover:text-blue-200 pl-3 transition-colors">📝 Report Builder</Link></li>}
              {hasRole('homeroom') && <li><Link to="/homeroom" className="hover:text-blue-200 pl-3 transition-colors">🏠 Homeroom Dashboard</Link></li>}
              {hasRole('teacher') && <li><Link to="/subject-teaching" className="hover:text-blue-200 pl-3 transition-colors">🎓 Subject Teaching</Link></li>}
            </>
          )}

          {/* Finance Staff */}
          {hasRole('finance') && (
            <>
              <div>
                <button 
                  onClick={() => toggleMenu('finance-staff')} 
                  className="hover:text-blue-200 pl-3 w-full text-left flex items-center justify-between py-2"
                >
                  <span>💳 Finance Dashboard</span>
                  <span className={`transition-transform mr-2 ${expandedMenus['finance-staff'] ? 'rotate-180' : ''}`}>▼</span>
                </button>
                {expandedMenus['finance-staff'] && (
                  <div className="ml-4 space-y-2 py-2 border-l border-white/20 pl-3">
                    <Link to="/finance" className="hover:text-blue-200 block text-sm opacity-90">📊 Dashboard</Link>
                    <Link to="/finance?tab=payment-tracker" className="hover:text-blue-200 block text-sm opacity-90">💳 Payment Tracker</Link>
                  </div>
                )}
              </div>
            </>
          )}

          {/* Inventory Manager */}
          {hasRole('inventory_manager') && modules.inventory && (
            <li><Link to="/inventory" className="hover:text-blue-200 pl-3 transition-colors">📦 Inventory</Link></li>
          )}

          {/* Kitchen Staff */}
          {hasRole('kitchen') && (
            <li><Link to="/kitchen" className="hover:text-blue-200 pl-3 transition-colors">👩‍🍳 Kitchen Dashboard</Link></li>
          )}

          {/* Teachers */}
          {(hasRole('teacher') || hasRole('homeroom')) && !hasRole('headmaster') && (
            <>
              {(assignedClass || hasRole('homeroom')) && <li><Link to="/homeroom" className="hover:text-blue-200 pl-3 transition-colors">🏠 Homeroom Dashboard</Link></li>}
              {(assignedClass || hasRole('homeroom')) && <li><Link to="/report-builder" className="hover:text-blue-200 pl-3 transition-colors">📝 Report Builder</Link></li>}
              {(assignedClass || hasRole('homeroom') || hasRole('teacher')) && <li><Link to="/subject-teaching" className="hover:text-blue-200 pl-3 transition-colors">🎓 Subject Teaching</Link></li>}
            </>
          )}

          {/* SETTINGS & ADMIN SECTION */}
          <li className="text-[10px] uppercase tracking-wider text-white/60 font-bold mt-6">⚙️ Settings</li>
          <li>
            <Link to="/help" className="hover:text-blue-200 pl-3 inline-flex items-center gap-2">
              <span>❓ Help Center</span>
            </Link>
          </li>
          {hasRole('proprietor') && <li><Link to="/proprietor?tab=settings" className="hover:text-blue-200 pl-3">⚙️ System Settings</Link></li>}
          {hasRole('proprietor') && <li><Link to="/proprietor?tab=profile" className="hover:text-blue-200 pl-3">👤 My Profile</Link></li>}
          {!hasRole('proprietor') && <li><Link to="/profile" className="hover:text-blue-200 pl-3">👤 My Profile</Link></li>}
          <li><Link to="/logout" className="hover:text-red-200 text-red-100 pl-3">🚪 Logout</Link></li>
        </ul>
        
        
      </nav>

      <main className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Top Header for Notifications */}
        <header className="bg-white h-16 border-b border-slate-200 flex items-center justify-end px-8 shadow-sm shrink-0 z-20">
            <div className="relative">
                <button 
                    onClick={() => { setShowNotifs(!showNotifs); setHasUnread(false); }}
                    className="p-2 rounded-full hover:bg-slate-100 relative transition-colors"
                >
                    <span className="text-xl">🔔</span>
                    {hasUnread && <span className="absolute top-0 right-0 w-3 h-3 bg-red-500 rounded-full border-2 border-white"></span>}
                </button>

                {showNotifs && (
                    <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-2xl border border-slate-100 overflow-hidden z-50">
                        <div className="p-4 border-b border-slate-50 bg-slate-50/50">
                            <h3 className="font-bold text-slate-700 text-sm">Notifications</h3>
                        </div>
                        <div className="max-h-64 overflow-y-auto">
                            {notifications.length === 0 ? (
                                <div className="p-4 text-center text-slate-400 text-xs">No new notifications</div>
                            ) : (
                                notifications.map((n, i) => (
                                    <div key={i} className="p-4 border-b border-slate-50 hover:bg-blue-50 transition-colors">
                                        {n.isSystem ? (
                                            <p className="text-xs font-bold text-red-600 uppercase mb-1">🚨 System Alert</p>
                                        ) : (
                                            <p className="text-xs font-bold text-blue-600 uppercase mb-1">📢 Announcement</p>
                                        )}
                                        <p className="text-sm text-slate-600">{n.message || n.details}</p>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                )}
            </div>
        </header>

        <div className="flex-1 overflow-y-auto">
          {currentSystemAlert && dismissedSystemAlert !== (currentSystemAlert.message || '') && (
            <div className="border-b border-amber-200 bg-amber-50 px-8 py-4">
              <div className="flex items-start justify-between gap-4 rounded-2xl border border-amber-300 bg-white/70 px-4 py-3 shadow-sm">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-amber-700">System Alert</p>
                  <p className="mt-1 text-sm font-medium text-slate-800">{currentSystemAlert.message}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setDismissedSystemAlert(currentSystemAlert.message || '')}
                  className="shrink-0 rounded-lg border border-amber-300 px-3 py-1 text-xs font-bold text-amber-700 hover:bg-amber-100"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}
            <Outlet />
        </div>
      </main>
      <SupportModal />
    </div>
  );
}