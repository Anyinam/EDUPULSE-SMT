import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';
import axios from 'axios';
import PricingComparison from '../PricingComparison';

vi.mock('axios');
vi.mock('../../components/TermsModal', () => ({ default: ({ isOpen, onClose }) => isOpen && <div role="dialog" aria-label="Terms"><button onClick={onClose}>Close</button></div> }));
vi.mock('../../components/PrivacyModal', () => ({ default: ({ isOpen, onClose }) => isOpen && <div role="dialog" aria-label="Privacy"><button onClick={onClose}>Close</button></div> }));
vi.mock('../../components/DataRetentionModal', () => ({ default: ({ isOpen, onClose }) => isOpen && <div role="dialog" aria-label="Retention"><button onClick={onClose}>Close</button></div> }));

const plans = [
  { name: 'Free Tier', display_name: 'Free', base_fee_per_term: 0, included_students: 0, price_per_student_per_term: 0, max_students: 50, marketing_features: [{ name: 'Grade viewing', included: true }, { name: 'Payment tracking', included: false }], addon_options: [] },
  { name: 'Basic', display_name: 'School OS', base_fee_per_term: 300, included_students: 50, price_per_student_per_term: 7, max_students: 200, popular: true, marketing_features: [{ name: 'Attendance', included: true, note: 'Full access' }], addon_options: ['AI Pack - GH\u20b5200/term'] },
  { name: 'Premium', display_name: 'School OS Plus', base_fee_per_term: 600, included_students: 100, price_per_student_per_term: 9, max_students: '\u221e', marketing_features: [], addon_options: ['Automation Pack - GH\u20b5250/term'] },
];

function renderPricing() {
  return render(<MemoryRouter initialEntries={['/pricing']}><Routes><Route path="/pricing" element={<PricingComparison />} /><Route path="/register" element={<h1>School registration</h1>} /></Routes></MemoryRouter>);
}

async function loadedPricing() {
  renderPricing();
  await screen.findByRole('article', { name: 'School OS' });
}

function estimate(planName) {
  return within(screen.getByRole('article', { name: planName })).getByLabelText('Estimated term cost');
}

describe('PricingComparison', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    axios.get.mockResolvedValue({ data: { plans } });
  });

  it('keeps the shared layout and heading visible while loading', () => {
    axios.get.mockReturnValue(new Promise(() => {}));
    renderPricing();
    expect(screen.getByRole('heading', { name: 'EduPulse SMT pricing' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Loading current plans');
    expect(screen.getByRole('contentinfo')).toBeInTheDocument();
  });

  it('uses live prices, feature notes and add-on descriptions', async () => {
    await loadedPricing();
    expect(axios.get).toHaveBeenCalledWith('/api/subscription/plans');
    expect(estimate('School OS')).toHaveTextContent('GH\u20b5 650');
    expect(estimate('School OS Plus')).toHaveTextContent('GH\u20b5 600');
    expect(screen.getByText('Full access')).toBeInTheDocument();
    expect(screen.getByText('AI Pack - GH\u20b5200/term')).toBeInTheDocument();
    expect(screen.getByText('Automation Pack - GH\u20b5250/term')).toBeInTheDocument();
    expect(within(screen.getByRole('article', { name: 'Free' })).getByText('Receipt printing included')).toBeInTheDocument();
    expect(screen.queryByText(/Start.*Trial/i)).not.toBeInTheDocument();
  });

  it.each([
    [0, 'GH\u20b5 0', 'GH\u20b5 300', 'GH\u20b5 600'],
    [50, 'GH\u20b5 0', 'GH\u20b5 300', 'GH\u20b5 600'],
    [51, 'Unavailable', 'GH\u20b5 307', 'GH\u20b5 600'],
    [200, 'Unavailable', 'GH\u20b5 1,350', 'GH\u20b5 1,500'],
    [201, 'Unavailable', 'Unavailable', 'GH\u20b5 1,509'],
  ])('calculates %i active students and enforces plan caps', async (students, free, basic, premium) => {
    await loadedPricing();
    fireEvent.change(screen.getByLabelText('Active students'), { target: { value: String(students) } });
    expect(estimate('Free')).toHaveTextContent(free);
    expect(estimate('School OS')).toHaveTextContent(basic);
    expect(estimate('School OS Plus')).toHaveTextContent(premium);
  });

  it.each(['', '-1', '1.5', '1e309'])('does not quote an invalid student count: %s', async (value) => {
    await loadedPricing();
    const input = screen.getByLabelText('Active students');
    expect(input).toHaveAttribute('min', '0');
    fireEvent.change(input, { target: { value } });
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(estimate('School OS')).toHaveTextContent('Enter a valid student count');
  });

  it('recalculates from changed API values instead of fixed prices', async () => {
    axios.get.mockResolvedValue({ data: { plans: plans.map(plan => plan.name === 'Basic' ? { ...plan, base_fee_per_term: '410', included_students: '60', price_per_student_per_term: '8' } : plan) } });
    await loadedPricing();
    expect(estimate('School OS')).toHaveTextContent('GH\u20b5 730');
  });

  it.each(['Free', 'School OS', 'School OS Plus'])('navigates %s signup to the real registration route', async (name) => {
    await loadedPricing();
    const link = within(screen.getByRole('article', { name })).getByRole('link', { name: name === 'Free' ? 'Create free account' : 'Create account' });
    expect(link).toHaveAttribute('href', '/register');
    fireEvent.click(link);
    expect(screen.getByRole('heading', { name: 'School registration' })).toBeInTheDocument();
  });

  it('retains the page on failure and retries without fabricated quotes', async () => {
    axios.get.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ data: { plans } });
    renderPricing();
    expect(await screen.findByRole('alert')).toHaveTextContent('Current pricing is unavailable');
    expect(screen.getByRole('heading', { name: 'EduPulse SMT pricing' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Estimated term cost')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry loading plans' }));
    await screen.findByRole('article', { name: 'School OS' });
    expect(axios.get).toHaveBeenCalledTimes(2);
  });

  it('treats an empty response as unavailable rather than an empty comparison', async () => {
    axios.get.mockResolvedValue({ data: { plans: [] } });
    renderPricing();
    expect(await screen.findByRole('alert')).toHaveTextContent('Current pricing is unavailable');
    expect(screen.getByRole('button', { name: 'Retry loading plans' })).toBeInTheDocument();
  });

  it.each([undefined, null, '', 'not a price', -1, Infinity])('does not fabricate a quote for a malformed rate: %s', async (rate) => {
    axios.get.mockResolvedValue({ data: { plans: plans.map(plan => plan.name === 'Basic' ? { ...plan, price_per_student_per_term: rate } : plan) } });
    renderPricing();
    expect(await screen.findByRole('alert')).toHaveTextContent('Current pricing is unavailable');
    expect(screen.queryByLabelText('Estimated term cost')).not.toBeInTheDocument();
  });

  it('keeps trial duration and add-ons separate from registration', async () => {
    await loadedPricing();
    expect(screen.getByRole('heading', { name: 'A one-time, 30-day trial' })).toBeInTheDocument();
    expect(screen.getByText(/Trial activation is separate from account creation/)).toBeInTheDocument();
    expect(screen.getByText(/not bundled into the base fee or calculator estimates/)).toBeInTheDocument();
    expect(within(screen.getByRole('article', { name: 'School OS' })).getByText('Choose your plan during registration.')).toBeInTheDocument();
  });

  it.each([['Terms of Service', 'Terms'], ['Privacy Policy', 'Privacy'], ['Data Retention Policy', 'Retention']])('opens and closes %s', async (label, dialog) => {
    await loadedPricing();
    fireEvent.click(within(screen.getByRole('main')).getByRole('button', { name: label }));
    expect(screen.getByRole('dialog', { name: dialog })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});