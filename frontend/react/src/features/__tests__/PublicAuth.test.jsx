import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import Login from '../login';
import Register from '../Register';

vi.mock('axios');
vi.mock('../../components/TermsModal', () => ({ default: ({ isOpen, onClose }) => isOpen && <div role="dialog" aria-label="Terms"><button onClick={onClose}>Close</button></div> }));
vi.mock('../../components/PrivacyModal', () => ({ default: ({ isOpen, onClose }) => isOpen && <div role="dialog" aria-label="Privacy"><button onClick={onClose}>Close</button></div> }));
vi.mock('../../components/DataRetentionModal', () => ({ default: ({ isOpen, onClose }) => isOpen && <div role="dialog" aria-label="Retention"><button onClick={onClose}>Close</button></div> }));
vi.mock('../../components/DataProcessingModal', () => ({ default: ({ isOpen, onClose }) => isOpen && <div role="dialog" aria-label="Data Processing"><button onClick={onClose}>Close</button></div> }));

const plans = [
  { name: 'Free Tier', display_name: 'Free', base_fee_per_term: 0, marketing_features: [] },
  { name: 'Basic', display_name: 'School OS', base_fee_per_term: 300, included_students: 50, price_per_student_per_term: 7, marketing_features: [{ name: 'Attendance' }], addon_options: ['AI Pack'], packaging_summary: 'Core school operations' },
];

async function renderAuth(path = '/login') {
  let view;
  await act(async () => {
    view = render(<MemoryRouter initialEntries={[path]}><Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/" element={<h1>Home destination</h1>} />
      <Route path="/pricing" element={<h1>Pricing destination</h1>} />
    </Routes></MemoryRouter>);
  });
  return view;
}

function fillLogin() {
  fireEvent.change(screen.getByLabelText('School ID'), { target: { value: ' cca-ofk ' } });
  fireEvent.change(screen.getByLabelText('Staff username or email'), { target: { value: ' staff@school.com ' } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: ' Password123 ' } });
}

function fillRegistration() {
  for (const [label, value] of [['School Name', ' Test School '], ['School ID', ' test-id '], ['Proprietor Username', ' owner '], ['Email Address', 'owner@school.com'], ['Password', ' Password123 ']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
}

function acceptConsents() {
  for (const checkbox of screen.getAllByRole('checkbox')) fireEvent.click(checkbox);
}

beforeEach(() => {
  vi.resetAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  axios.get.mockImplementation(url => Promise.resolve({ data: url === '/api/subscription/plans' ? { plans } : { auth: { login_title: 'Welcome Back', register_title: 'Create Tenant' } } }));
});

afterEach(() => vi.useRealTimers());

describe('Public login', () => {
  it('keeps the shared public shell, own heading, and password field', async () => {
    await renderAuth();
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/public/platform-content'));
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument();
    expect(screen.getByRole('contentinfo')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password');
    expect(screen.getByRole('link', { name: 'Forgot password?' })).toHaveAttribute('href', '/forgot-password');
    expect(screen.queryByText('Governance with Pulse.')).not.toBeInTheDocument();
  });

  it('trims identifiers only and disables duplicate submission while pending', async () => {
    let rejectLogin;
    axios.post.mockImplementation(() => new Promise((resolve, reject) => { rejectLogin = reject; }));
    await renderAuth();
    fillLogin();
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }));
    expect(screen.getByRole('button', { name: 'Please wait...' })).toBeDisabled();
    expect(axios.post).toHaveBeenCalledExactlyOnceWith('/api/login', { schoolCode: 'CCA-OFK', username: 'staff@school.com', password: ' Password123 ' });
    await act(async () => rejectLogin({ response: { data: { message: 'Credentials not recognized' } } }));
    expect(screen.getByRole('alert')).toHaveTextContent('Credentials not recognized');
    expect(screen.getByRole('button', { name: 'Log in' })).toBeEnabled();
  });

  it('preserves 2FA verification, development fallback, cooldown and resend tokens', async () => {
    axios.post.mockResolvedValueOnce({ status: 202, data: { message: '2fa_required', token: 'challenge', dev_code: '123456', fallback_notice: 'Email fallback' } });
    await renderAuth();
    fillLogin();
    vi.useFakeTimers();
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Log in' })));
    expect(screen.getByLabelText('Verification code')).toHaveValue('123456');
    expect(screen.getByLabelText('School ID')).toBeDisabled();
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
    expect(screen.getByText('Development Mode: Email Delivery Fallback')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resend Code in 30s' })).toBeDisabled();
    await act(async () => vi.advanceTimersByTime(30000));
    axios.post.mockResolvedValueOnce({ data: { token: 'renewed-challenge', dev_code: '654321', message: 'Verification code resent.' } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Resend Code' })));
    expect(axios.post).toHaveBeenLastCalledWith('/api/2fa/resend', { token: 'challenge' });
    expect(screen.getByLabelText('Verification code')).toHaveValue('654321');
    axios.post.mockRejectedValueOnce({ response: { data: { message: 'Invalid verification code' } } });
    fireEvent.change(screen.getByLabelText('Verification code'), { target: { value: ' 654321 ' } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Verify & Continue' })));
    expect(axios.post).toHaveBeenLastCalledWith('/api/2fa/verify', { token: 'renewed-challenge', code: '654321' });
    expect(screen.getByRole('alert')).toHaveTextContent('Invalid verification code');
    expect(screen.getByRole('button', { name: 'Verify & Continue' })).toBeEnabled();
  });

  it.each([['Terms of Service', 'Terms'], ['Privacy Policy', 'Privacy'], ['Data Retention Policy', 'Retention']])('retains the %s modal', async (label, dialog) => {
    await renderAuth();
    const main = within(screen.getByRole('main'));
    fireEvent.click(main.getByText('Legal policies'));
    fireEvent.click(main.getByRole('button', { name: label }));
    expect(screen.getByRole('dialog', { name: dialog })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows and clears the existing session-expired notice', async () => {
    sessionStorage.setItem('session_expired_message', 'Your session expired.');
    await renderAuth();
    expect(screen.getByRole('alert')).toHaveTextContent('Your session expired.');
    expect(sessionStorage.getItem('session_expired_message')).toBeNull();
  });
});

describe('Public registration', () => {
  it.each([0, 1, 2, 3])('requires consent %i before leaving school details', async (missingConsent) => {
    await renderAuth('/register');
    fillRegistration();
    screen.getAllByRole('checkbox').forEach((checkbox, index) => { if (index !== missingConsent) fireEvent.click(checkbox); });
    fireEvent.click(screen.getByRole('button', { name: /Continue to Plan Selection/ }));
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByLabelText('School Name')).toBeInTheDocument();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it.each([['Terms of Service', 'Terms'], ['Privacy Policy', 'Privacy'], ['Data Retention Policy', 'Retention'], ['Data Processing Agreement', 'Data Processing']])('retains explicit %s access', async (label, dialog) => {
    await renderAuth('/register');
    fireEvent.click(within(screen.getByRole('main')).getByRole('button', { name: label }));
    expect(screen.getByRole('dialog', { name: dialog })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it.each(['Free', 'School OS'])('preserves steps, %s payload, consents, and failed-submit recovery', async (planName) => {
    let rejectRegistration;
    axios.post.mockImplementation(() => new Promise((resolve, reject) => { rejectRegistration = reject; }));
    await renderAuth('/register');
    expect(screen.getByRole('heading', { name: 'Create your school account' })).toBeInTheDocument();
    fillRegistration();
    acceptConsents();
    fireEvent.click(screen.getByRole('button', { name: /Continue to Plan Selection/ }));
    expect(await screen.findByRole('radio', { name: 'Free' })).toBeChecked();
    fireEvent.click(screen.getByRole('radio', { name: planName }));
    expect(screen.getByText('Core school operations')).toBeInTheDocument();
    expect(screen.getByText('AI Pack')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(screen.getByRole('radio', { name: planName })).toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.click(screen.getByRole('button', { name: planName === 'Free' ? 'Complete Registration' : 'Proceed to Payment' }));
    expect(screen.getByRole('button', { name: 'Creating account...' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Back' })).toBeDisabled();
    expect(axios.post).toHaveBeenCalledExactlyOnceWith('/api/register', {
      schoolName: 'Test School', schoolCode: 'TEST-ID', username: 'owner', email: 'owner@school.com', password: ' Password123 ', selectedPlan: planName === 'Free' ? 'Free' : 'Basic',
      termsAccepted: true, termsVersion: '2026-03-07', policyAccepted: true, policyVersion: '2026-03-07', schoolDataAuthorityConfirmed: true, legacyAndExamConsentPlanConfirmed: true, aggregatedAnalyticsAccepted: true,
    });
    await act(async () => rejectRegistration({ response: { data: { message: 'Registration failed', errors: 'Duplicate school' } } }));
    expect(screen.getByRole('alert')).toHaveTextContent('Registration failed: Duplicate school');
    expect(screen.getByLabelText('Password')).toHaveValue(' Password123 ');
    expect(screen.getAllByRole('checkbox').every(checkbox => checkbox.checked)).toBe(true);
  });
});

describe('Shared auth navigation', () => {
  it.each([['Pricing', 'Pricing destination'], ['EduPulse SMT home', 'Home destination'], ['Create free account', 'Create your school account']])('navigates %s from login', async (linkName, heading) => {
    await renderAuth();
    fireEvent.click(within(screen.getByRole('banner')).getByRole('link', { name: linkName }));
    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument();
  });

  it('navigates from registration to login', async () => {
    await renderAuth('/register');
    fireEvent.click(within(screen.getByRole('banner')).getByRole('link', { name: 'Log in' }));
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
  });
});