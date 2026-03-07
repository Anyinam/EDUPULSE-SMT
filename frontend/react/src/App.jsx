import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Login from './features/login';
import AdminLogin from './features/AdminLogin';
import AdminDashboard from './features/AdminDashboard';
import PlatformConsole from './features/PlatformConsole';
import ProprietorPanel from './features/ProprietorPanel';
import TeacherDashboard from './features/TeacherDashboard';
import HomeroomDashboard from './features/HomeroomDashboard';
import HeadmasterDashboard from './features/HeadmasterDashboard';
import SuperAdminDashboard from './features/SuperAdminDashboard';
import KitchenDashboard from './features/KitchenDashboard';
import FinanceDashboard from './features/FinanceDashboard';
import ReportBuilder from './features/ReportBuilder';
import ProfileSettings from './features/ProfileSettings';
import StaffManagement from './features/StaffManagement';
import SettingsPanel from './components/SettingsPanel';
import StudentPaymentTracker from './components/StudentPaymentTracker';
import InventoryManager from './features/InventoryManager';
import SubscriptionPlans from './features/SubscriptionPlans';
import PricingComparison from './features/PricingComparison';
import AdmissionsPanel from './features/AdmissionsPanel';
import PaymentCallback from './features/PaymentCallback';
import Logout from './features/Logout';
import Register from './features/Register';
import HelpCenter from './features/HelpCenter';
import AdminSupport from './features/AdminSupport';

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/logout" element={<Logout />} />
        <Route path="/register" element={<Register />} />
        <Route path="/pricing" element={<PricingComparison />} />
        <Route path="/pricing-comparison" element={<PricingComparison />} />
        <Route path="/subscription" element={<SubscriptionPlans />} />
        <Route path="/payment/callback" element={<PaymentCallback />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/platform-console" element={<PlatformConsole />} />
        
        {/* Protected Routes inside Layout */}
        <Route path="/" element={<Layout />}>
          <Route path="proprietor" element={<ProprietorPanel />} />
          <Route path="proprietor/admissions" element={<AdmissionsPanel />} />
          <Route path="headmaster" element={<HeadmasterDashboard />} />
          <Route path="headmaster/admissions" element={<AdmissionsPanel />} />
          <Route path="super-admin" element={<SuperAdminDashboard />} />
          <Route path="kitchen" element={<KitchenDashboard />} />
          <Route path="finance" element={<FinanceDashboard />} />
          <Route path="homeroom" element={<HomeroomDashboard />} />
          <Route path="teacher" element={<TeacherDashboard />} />
          <Route path="subject-teaching" element={<TeacherDashboard />} />
          <Route path="report-builder" element={<ReportBuilder />} />
          <Route path="profile" element={<ProfileSettings />} />
          <Route path="settings" element={<SettingsPanel />} />
          <Route path="staff" element={<StaffManagement />} />
          <Route path="payment-tracker" element={<StudentPaymentTracker />} />
          <Route path="inventory" element={<InventoryManager />} />
          <Route path="help" element={<HelpCenter />} />
          <Route path="admin/support" element={<AdminSupport />} />
        </Route>
      </Routes>
    </Router>
  );
}