import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { getAuthToken, validateTokenExpiry } from './utils/authUtils';
import ConnectionStatus from './components/ConnectionStatus';
const Layout = lazy(() => import('./components/Layout'));
const PublicHome = lazy(() => import('./features/PublicHome'));
const Login = lazy(() => import('./features/login'));
const AdminLogin = lazy(() => import('./features/AdminLogin'));
const AdminDashboard = lazy(() => import('./features/AdminDashboard'));
const PlatformConsole = lazy(() => import('./features/PlatformConsole'));
const ProprietorPanel = lazy(() => import('./features/ProprietorPanel'));
const TeacherDashboard = lazy(() => import('./features/TeacherDashboard'));
const HomeroomDashboard = lazy(() => import('./features/HomeroomDashboard'));
const HeadmasterDashboard = lazy(() => import('./features/HeadmasterDashboard'));
const SuperAdminDashboard = lazy(() => import('./features/SuperAdminDashboard'));
const KitchenDashboard = lazy(() => import('./features/KitchenDashboard'));
const FinanceDashboard = lazy(() => import('./features/FinanceDashboard'));
const ReportBuilder = lazy(() => import('./features/ReportBuilder'));
const ProfileSettings = lazy(() => import('./features/ProfileSettings'));
const StaffManagement = lazy(() => import('./features/StaffManagement'));
const SettingsPanel = lazy(() => import('./components/SettingsPanel'));
const StudentPaymentTracker = lazy(() => import('./components/StudentPaymentTracker'));
const PaymentReceipts = lazy(() => import('./components/PaymentReceipts'));
const InventoryManager = lazy(() => import('./features/InventoryManager'));
const SubscriptionPlans = lazy(() => import('./features/SubscriptionPlans'));
const PricingComparison = lazy(() => import('./features/PricingComparison'));
const AdmissionsPanel = lazy(() => import('./features/AdmissionsPanel'));
const PaymentCallback = lazy(() => import('./features/PaymentCallback'));
const Logout = lazy(() => import('./features/Logout'));
const Register = lazy(() => import('./features/Register'));
const ForgotPassword = lazy(() => import('./features/ForgotPassword'));
const ResetPassword = lazy(() => import('./features/ResetPassword'));
const HelpCenter = lazy(() => import('./features/HelpCenter'));
const AdminSupport = lazy(() => import('./features/AdminSupport'));
const FirstLoginPasswordChange = lazy(() => import('./features/FirstLoginPasswordChange'));
const ParentAdmissionsPortal = lazy(() => import('./features/ParentAdmissionsPortal'));
const ParentAdmissionStatus = lazy(() => import('./features/ParentAdmissionStatus'));

function RouteFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 text-slate-600">
      Loading EduPulse...
    </div>
  );
}

function getStoredPostLoginTarget() {
  return localStorage.getItem('post_login_target') || '/login';
}

function isActiveSession() {
  return Boolean(getAuthToken()) && validateTokenExpiry() && Boolean(localStorage.getItem('school_id'));
}

function normalizeRoleValue(value) {
  return typeof value === 'string' ? value.trim().toLowerCase() : '';
}

function getStoredRoles() {
  try {
    const parsedRoles = JSON.parse(localStorage.getItem('roles') || '[]');
    const roleList = Array.isArray(parsedRoles) ? parsedRoles : [parsedRoles];
    return roleList.map(normalizeRoleValue).filter(Boolean);
  } catch (err) {
    return [];
  }
}

function isKitchenPrimarySession() {
  const primaryRole = normalizeRoleValue(localStorage.getItem('role'));
  const roles = getStoredRoles();
  if (primaryRole === 'kitchen') {
    return true;
  }
  return roles.includes('kitchen') && !roles.some((role) => ['teacher', 'homeroom', 'headmaster', 'proprietor'].includes(role));
}

function SubjectTeachingRoute() {
  return isKitchenPrimarySession() ? <Navigate to="/kitchen" replace /> : <TeacherDashboard />;
}

function LoginRoute() {
  return isActiveSession() ? <Navigate to={getStoredPostLoginTarget()} replace /> : <Login />;
}

function RootRoute() {
  return isActiveSession() ? <Navigate to={getStoredPostLoginTarget()} replace /> : <PublicHome />;
}

function PaymentReceiptsRoute() {
  if (!isActiveSession()) return <Navigate to="/login" replace />;
  const roles = [...getStoredRoles(), normalizeRoleValue(localStorage.getItem('role'))];
  return roles.some((role) => ['proprietor', 'finance', 'headmaster', 'homeroom', 'teacher'].includes(role))
    ? <PaymentReceipts />
    : <Navigate to="/profile" replace />;
}

export default function App() {
  return (
    <Router>
      <ConnectionStatus />
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/" element={<RootRoute />} />
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/logout" element={<Logout />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/pricing" element={<PricingComparison />} />
          <Route path="/pricing-comparison" element={<PricingComparison />} />
          <Route path="/subscription" element={<SubscriptionPlans />} />
          <Route path="/payment/callback" element={<PaymentCallback />} />
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/platform-console" element={<PlatformConsole />} />
          <Route path="/first-login-password" element={<FirstLoginPasswordChange />} />
          <Route path="apply/:schoolId" element={<ParentAdmissionsPortal />} />
          <Route path="apply/:schoolId/status/:statusToken" element={<ParentAdmissionStatus />} />

          <Route path="/" element={<Layout />}>
            <Route path="proprietor" element={<ProprietorPanel />} />
            <Route path="proprietor/admissions" element={<AdmissionsPanel />} />
            <Route path="headmaster" element={<HeadmasterDashboard />} />
            <Route path="headmaster/admissions" element={<AdmissionsPanel />} />
            <Route path="super-admin" element={<Navigate to="/platform-console" replace />} />
            <Route path="kitchen" element={<KitchenDashboard />} />
            <Route path="finance" element={<FinanceDashboard />} />
            <Route path="homeroom" element={<HomeroomDashboard />} />
            <Route path="teacher" element={<TeacherDashboard />} />
            <Route path="subject-teaching" element={<SubjectTeachingRoute />} />
            <Route path="report-builder" element={<ReportBuilder />} />
            <Route path="profile" element={<ProfileSettings />} />
            <Route path="settings" element={<SettingsPanel />} />
            <Route path="staff" element={<StaffManagement />} />
            <Route path="payment-tracker" element={<StudentPaymentTracker />} />
            <Route path="payment-receipts" element={<PaymentReceiptsRoute />} />
            <Route path="inventory" element={<InventoryManager />} />
            <Route path="help" element={<HelpCenter />} />
            <Route path="admin/support" element={<AdminSupport />} />
          </Route>
          <Route path="*" element={<RootRoute />} />
        </Routes>
      </Suspense>
    </Router>
  );
}