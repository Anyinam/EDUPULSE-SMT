import React from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import ForgotPassword from '../ForgotPassword';
import ResetPassword from '../ResetPassword';

vi.mock('axios');
vi.mock('../../components/TermsModal', () => ({ default: ({ isOpen, onClose }) => isOpen && <div role="dialog" aria-label="Terms"><button onClick={onClose}>Close</button></div> }));
vi.mock('../../components/PrivacyModal', () => ({ default: ({ isOpen, onClose }) => isOpen && <div role="dialog" aria-label="Privacy"><button onClick={onClose}>Close</button></div> }));
vi.mock('../../components/DataRetentionModal', () => ({ default: ({ isOpen, onClose }) => isOpen && <div role="dialog" aria-label="Retention"><button onClick={onClose}>Close</button></div> }));

function renderRecovery(path = '/forgot-password') {
  return render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/forgot-password" element={<ForgotPassword />} />
    <Route path="/reset-password" element={<ResetPassword />} />
    <Route path="/login" element={<h1>Login destination</h1>} />
  </Routes></MemoryRouter>);
}

function fillRecovery() {
  fireEvent.change(screen.getByLabelText('School ID'), { target: { value: ' cca-ofk ' } });
  fireEvent.change(screen.getByLabelText('Registered email'), { target: { value: ' staff@school.edu ' } });
}

function fillPassword(password = ' Password123 ') {
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: password } });
}

beforeEach(() => vi.resetAllMocks());

describe('Public recovery shell', () => {
  it.each([
    ['/forgot-password', 'Forgot password?', 'Recover your account | EduPulse SMT'],
    ['/reset-password?token=reset-token', 'Set new password', 'Reset your password | EduPulse SMT'],
  ])('uses the shared shell at %s', (path, heading, title) => {
    renderRecovery(path);
    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument();
    expect(screen.getByRole('contentinfo')).toBeInTheDocument();
    expect(document.title).toBe(title);
    expect(screen.getByRole('heading', { name: heading }).closest('section')).toHaveClass('public-auth');
  });
});

describe('Forgot password', () => {
  it('associates labels and autocomplete with the recovery fields', () => {
    renderRecovery();
    expect(screen.getByLabelText('School ID')).toHaveAttribute('autocomplete', 'organization');
    expect(screen.getByLabelText('Registered email')).toHaveAttribute('type', 'email');
    expect(screen.getByLabelText('Registered email')).toHaveAttribute('autocomplete', 'email');
    expect(screen.getByLabelText('Registered email')).toBeRequired();
  });

  it('normalizes identifiers, blocks duplicate submissions, and reports success', async () => {
    let resolveRequest;
    axios.post.mockImplementation(() => new Promise(resolve => { resolveRequest = resolve; }));
    renderRecovery();
    fillRecovery();
    const form = screen.getByRole('form', { name: 'Request password reset' });
    fireEvent.submit(form);
    fireEvent.submit(form);
    expect(axios.post).toHaveBeenCalledExactlyOnceWith('/api/forgot-password', { schoolCode: 'CCA-OFK', email: 'staff@school.edu' });
    expect(screen.getByRole('button', { name: 'Sending...' })).toBeDisabled();
    expect(screen.getByLabelText('School ID')).toBeDisabled();
    expect(screen.getByLabelText('Registered email')).toBeDisabled();
    expect(form).toHaveAttribute('aria-busy', 'true');
    await act(async () => resolveRequest({ data: { message: 'If an account exists, a reset link has been sent.' } }));
    expect(screen.getByRole('status')).toHaveTextContent('If an account exists');
    expect(screen.getByRole('button', { name: 'Send reset link' })).toBeEnabled();
  });

  it.each([['Service unavailable', 'Service unavailable'], [null, 'Request failed. Please try again.']])('allows retry after an error: %s', async (message, expected) => {
    axios.post.mockRejectedValueOnce({ response: { data: { message } } });
    renderRecovery();
    fillRecovery();
    await act(async () => fireEvent.submit(screen.getByRole('form')));
    expect(screen.getByRole('alert')).toHaveTextContent(expected);
    expect(screen.getByRole('button', { name: 'Send reset link' })).toBeEnabled();
    axios.post.mockResolvedValueOnce({ data: { message: 'Link sent.' } });
    await act(async () => fireEvent.submit(screen.getByRole('form')));
    expect(axios.post).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Link sent.');
  });

  it.each([['Terms of Service', 'Terms'], ['Privacy Policy', 'Privacy'], ['Data Retention Policy', 'Retention']])('preserves the %s modal', (label, dialog) => {
    renderRecovery();
    const main = within(screen.getByRole('main'));
    fireEvent.click(main.getByText('Legal policies'));
    fireEvent.click(main.getByRole('button', { name: label }));
    expect(screen.getByRole('dialog', { name: dialog })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('returns to login using a router link', () => {
    renderRecovery();
    fireEvent.click(screen.getByRole('link', { name: 'Back to login' }));
    expect(screen.getByRole('heading', { name: 'Login destination' })).toBeInTheDocument();
  });
});

describe('Reset password', () => {
  it.each(['/reset-password', '/reset-password?token=', '/reset-password?token=%20%20'])('blocks a missing token at %s and offers recovery', (path) => {
    renderRecovery(path);
    expect(screen.getByRole('alert')).toHaveTextContent('Invalid or missing reset token.');
    expect(screen.queryByRole('form')).not.toBeInTheDocument();
    expect(axios.post).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('link', { name: 'Request a new reset link' }));
    expect(screen.getByLabelText('School ID')).toBeInTheDocument();
  });

  it('sets accessible new-password fields and the backend minimum length', () => {
    renderRecovery('/reset-password?token=reset-token');
    expect(screen.getByLabelText('New password')).toHaveAttribute('type', 'password');
    expect(screen.getByLabelText('New password')).toHaveAttribute('autocomplete', 'new-password');
    expect(screen.getByLabelText('New password')).toHaveAttribute('minlength', '8');
    expect(screen.getByLabelText('New password')).toBeRequired();
    expect(screen.getByLabelText('Confirm new password (optional)')).toHaveAttribute('autocomplete', 'new-password');
    expect(screen.getByLabelText('Confirm new password (optional)')).not.toBeRequired();
  });

  it.each(['Short1', 'lowercase123', 'NoDigitsHere', '  Abcd1  '])('blocks passwords that fail backend rules: %s', (password) => {
    renderRecovery('/reset-password?token=reset-token');
    fillPassword(password);
    fireEvent.submit(screen.getByRole('form'));
    expect(screen.getByRole('alert')).toHaveTextContent('at least 8 characters');
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('blocks an entered mismatch and submits after correction', async () => {
    axios.post.mockResolvedValue({ data: {} });
    renderRecovery('/reset-password?token=reset-token');
    fillPassword();
    fireEvent.change(screen.getByLabelText('Confirm new password (optional)'), { target: { value: 'Different123' } });
    fireEvent.submit(screen.getByRole('form'));
    expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match.');
    expect(axios.post).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Confirm new password (optional)'), { target: { value: ' Password123 ' } });
    await act(async () => fireEvent.submit(screen.getByRole('form')));
    expect(axios.post).toHaveBeenCalledExactlyOnceWith('/api/reset-password', { token: 'reset-token', password: ' Password123 ' });
  });

  it('submits without confirmation, preserves token and password, blocks duplicates, and waits for explicit login', async () => {
    let resolveRequest;
    axios.post.mockImplementation(() => new Promise(resolve => { resolveRequest = resolve; }));
    renderRecovery('/reset-password?token=reset%2Btoken');
    fillPassword(' ALLUPPER123 ');
    const form = screen.getByRole('form');
    fireEvent.submit(form);
    fireEvent.submit(form);
    expect(axios.post).toHaveBeenCalledExactlyOnceWith('/api/reset-password', { token: 'reset+token', password: ' ALLUPPER123 ' });
    expect(screen.getByRole('button', { name: 'Resetting...' })).toBeDisabled();
    expect(screen.getByLabelText('New password')).toBeDisabled();
    expect(screen.getByLabelText('Confirm new password (optional)')).toBeDisabled();
    await act(async () => resolveRequest({ data: {} }));
    expect(screen.getByRole('status')).toHaveTextContent('Password reset successfully!');
    expect(screen.queryByRole('form')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Login destination' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('link', { name: 'Back to login' }));
    expect(screen.getByRole('heading', { name: 'Login destination' })).toBeInTheDocument();
  });

  it.each([['Token expired.', 'Token expired.'], [null, 'Reset failed. Token may be expired.']])('shows reset errors and allows retry: %s', async (message, expected) => {
    axios.post.mockRejectedValueOnce({ response: { data: { message } } });
    renderRecovery('/reset-password?token=reset-token');
    fillPassword();
    await act(async () => fireEvent.submit(screen.getByRole('form')));
    expect(screen.getByRole('alert')).toHaveTextContent(expected);
    expect(screen.getByRole('button', { name: 'Reset password' })).toBeEnabled();
    expect(screen.getByLabelText('New password')).toHaveValue(' Password123 ');
    expect(screen.getByRole('link', { name: 'Request a new reset link' })).toHaveAttribute('href', '/forgot-password');
    axios.post.mockResolvedValueOnce({ data: {} });
    await act(async () => fireEvent.submit(screen.getByRole('form')));
    expect(axios.post).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});