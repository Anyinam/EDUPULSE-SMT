import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';

import SettingsPanel, { calculateTuitionTransferPreview } from '../SettingsPanel';

vi.mock('axios');
vi.mock('../TimetableManager', () => ({
  default: () => <div data-testid="timetable-manager" />,
}));
vi.mock('../TermManagementPanel', () => ({
  default: () => <div data-testid="term-management-panel" />,
}));

describe('SettingsPanel', () => {
  it.each([
    [25, { total: 25.76, provider: 0.50, margin: 0.25, surplus: 0.01 }],
    [75, { total: 77.26, provider: 1.51, margin: 0.75, surplus: 0 }],
    [0, { total: 0, provider: 0, margin: 0, surplus: 0 }],
  ])('grosses up tuition %s using cents', (base, expected) => {
    expect(calculateTuitionTransferPreview(base)).toEqual(expected);
  });

  it('uses authoritative rates and flat fees instead of a fixed total', () => {
    expect(calculateTuitionTransferPreview(25, {
      estimated_provider_fee_rate_pct: 2, estimated_provider_fee_flat: 0.10,
      platform_margin_rate_pct: 3, platform_fee_flat: 0.05,
    })).toEqual({ total: 26.43, provider: 0.63, margin: 0.80, surplus: 0 });
  });

  beforeEach(() => {
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');
    localStorage.setItem('subscription_plan', 'Premium');

    axios.get.mockImplementation((url) => {
      if (url === '/api/school/subscription/effective-plan') {
        return Promise.resolve({
          data: {
            effective_plan: 'Premium',
            features: { feeding: 'full_access' },
            trial: { active: false, plan: '', end_date: null },
          },
        });
      }

      if (url === '/api/school/settings') {
        return Promise.resolve({
          data: {
            name: 'Test School',
            primary_color: '#1e3a8a',
            ai_registrar_enabled: true,
          },
        });
      }

      if (url === '/api/school/grading-scheme') {
        return Promise.resolve({
          data: {
            class_score_max: 30,
            exam_score_max: 70,
          },
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: '1000',
            tuition_convenience_fee_percentage: '1.95',
            tuition_installment_plan: {
              enabled: true,
              installment_count: 2,
              schedule: [
                {
                  installment_number: 1,
                  label: 'Installment 1',
                  amount: '500',
                  start_date: '2026-10-01',
                  due_date: '2026-10-31',
                },
                {
                  installment_number: 2,
                  label: 'Installment 2',
                  amount: '500',
                  start_date: '2026-11-01',
                  due_date: '2026-11-30',
                },
              ],
            },
            feeding_fee: '450',
            feeding_daily_fee: '15',
            feeding_weekly_fee: '75',
            feeding_monthly_fee: '300',
            transport_fee: '120',
            terminal_report_fee: '25',
            admission_fee_enabled: true,
            admission_fee_amount: '80',
            other_fees: {
              Sports: '15.5',
            },
          },
        });
      }

      if (url === '/api/school/report-template') {
        return Promise.resolve({
          data: {
            report_template_id: 'gradman_v1',
            report_template_config: {},
          },
        });
      }

      if (url === '/api/school/report-template/history') {
        return Promise.resolve({
          data: {
            history: [],
          },
        });
      }

      return Promise.reject(new Error(`Unhandled GET ${url}`));
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('renders fee summaries when the API returns numeric fee values as strings', async () => {
    render(<SettingsPanel />);

    expect(await screen.findByText(/system branding & settings/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText('GH₵ 1000.00').length).toBeGreaterThan(0);
    });

    expect(screen.getByRole('spinbutton', { name: /estimated processing rate/i })).toHaveAttribute('readonly');
    expect(screen.getByRole('spinbutton', { name: /edupulse service rate/i })).toHaveAttribute('readonly');
    expect(screen.getByText('GH₵ 20.09')).toBeInTheDocument();
    expect(screen.getByText('GH₵ 10.00')).toBeInTheDocument();
    expect(screen.getByText('GH₵ 1030.09')).toBeInTheDocument();
    expect(screen.queryByText(/admissions configuration/i)).not.toBeInTheDocument();
  });

  it('hydrates authoritative pricing as read-only and recalculates the full tuition quote', async () => {
    const defaultGet = axios.get.getMockImplementation();
    axios.get.mockImplementation((url, config) => url === '/api/school/fees'
      ? Promise.resolve({ data: { tuition_fee: 25, tuition_transfer_pricing: {
        fee_model: 'gross_up_margin_v1', estimated_provider_fee_rate_pct: 1.95,
        platform_margin_rate_pct: 1, estimated_provider_fee_flat: 0, platform_fee_flat: 0,
      } } }) : defaultGet(url, config));
    render(<SettingsPanel />);
    await screen.findByText('GH₵ 25.76');
    expect(screen.getByText('Total convenience fee: GH₵ 0.76')).toBeInTheDocument();
    const margin = screen.getByRole('spinbutton', { name: /edupulse service rate/i });
    fireEvent.change(margin, { target: { value: '9' } });
    expect(margin).toHaveValue(1);
    expect(screen.queryByText('Tuition Convenience Fee (%)')).not.toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue('25'), { target: { value: '75' } });
    expect(screen.getByText('GH₵ 77.26')).toBeInTheDocument();
    expect(screen.getByText('GH₵ 1.51')).toBeInTheDocument();
    expect(screen.getByText('GH₵ 0.75')).toBeInTheDocument();
  });

  it('renders non-default server rates instead of fallback rates', async () => {
    const defaultGet = axios.get.getMockImplementation();
    axios.get.mockImplementation((url, config) => url === '/api/school/fees'
      ? Promise.resolve({ data: { tuition_fee: 25, tuition_transfer_pricing: {
        fee_model: 'gross_up_margin_v1', estimated_provider_fee_rate_pct: 2,
        platform_margin_rate_pct: 3, estimated_provider_fee_flat: 0.10, platform_fee_flat: 0.05,
      } } }) : defaultGet(url, config));
    render(<SettingsPanel />);
    await screen.findByText('GH₵ 26.43');
    expect(screen.getByRole('spinbutton', { name: /estimated processing rate/i })).toHaveValue(2);
    expect(screen.getByRole('spinbutton', { name: /edupulse service rate/i })).toHaveValue(3);
  });

  it.each(['free', 'loading', 'error'])('preserves tuition and branding saves without feeding keys when access is %s', async (accessState) => {
    const defaultGet = axios.get.getMockImplementation();
    axios.get.mockImplementation((url, config) => {
      if (url === '/api/school/subscription/effective-plan') {
        if (accessState === 'loading') return new Promise(() => {});
        if (accessState === 'error') return Promise.reject(new Error('unavailable'));
        return Promise.resolve({ data: { effective_plan: 'Free Tier', features: { feeding: 'view_only' } } });
      }
      return defaultGet(url, config);
    });
    axios.post.mockResolvedValue({ data: {} });
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<SettingsPanel />);
    const dailyFee = await screen.findByRole('spinbutton', { name: 'Feeding Fee (Daily Plan)' });
    expect(dailyFee).toBeDisabled();
    expect(screen.getByRole('spinbutton', { name: 'Feeding Fee (Weekly Plan)' })).toBeDisabled();
    expect(screen.getByRole('spinbutton', { name: 'Feeding Fee (Monthly Plan)' })).toBeDisabled();
    fireEvent.submit(dailyFee.closest('form'));
    await waitFor(() => expect(axios.post).toHaveBeenCalledWith('/api/school/fees', expect.any(Object), expect.any(Object)));
    const payload = axios.post.mock.calls.find(([url]) => url === '/api/school/fees')[1];
    expect(Object.keys(payload).filter((key) => key.startsWith('feeding'))).toEqual([]);
    expect(payload.tuition_fee).toBe(1000);
    expect(payload).not.toHaveProperty('tuition_convenience_fee_percentage');
    expect(payload).not.toHaveProperty('tuition_transfer_pricing');
    expect(payload.tuition_installment_plan.enabled).toBe(true);
    expect(axios.post).toHaveBeenCalledWith('/api/school/settings', expect.objectContaining({ name: 'Test School' }), expect.any(Object));
  });

  it('allows feeding controls and payload keys with confirmed full access', async () => {
    axios.post.mockResolvedValue({ data: {} });
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<SettingsPanel />);
    const dailyFee = await screen.findByRole('spinbutton', { name: 'Feeding Fee (Daily Plan)' });
    expect(dailyFee).toBeEnabled();
    fireEvent.submit(dailyFee.closest('form'));
    await waitFor(() => expect(axios.post).toHaveBeenCalledWith('/api/school/fees', expect.objectContaining({
      feeding_fee: 450,
      feeding_daily_fee: 15,
      feeding_weekly_fee: 75,
      feeding_monthly_fee: 300,
    }), expect.any(Object)));
  });

  it.each([false, true])('preserves bank reconnect on Free with unsaved bank edits: %s', async (editBankDetails) => {
    const defaultGet = axios.get.getMockImplementation();
    let connected = false;
    axios.get.mockImplementation((url, config) => {
      if (url === '/api/school/subscription/effective-plan') {
        return Promise.resolve({ data: { effective_plan: 'Free Tier', features: { feeding: 'view_only' } } });
      }
      if (url === '/api/school/settings') {
        return Promise.resolve({ data: {
          name: 'Test School', bank_name: 'Test Bank', bank_account: '1234567890',
          bank_account_name: 'Test School', bank_branch: 'Main',
          paystack_subaccount_code: connected ? 'ACCT_test' : '',
        } });
      }
      return defaultGet(url, config);
    });
    axios.post.mockImplementation((url) => {
      if (url === '/api/school/settings/paystack/reconnect') {
        connected = true;
        return Promise.resolve({ data: { paystack_subaccount_code: 'ACCT_test' } });
      }
      return Promise.resolve({ data: {} });
    });
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<SettingsPanel />);
    await screen.findByRole('button', { name: 'Reconnect Settlement Account' });
    if (editBankDetails) {
      fireEvent.change(screen.getByPlaceholderText('School bank account number'), { target: { value: '9876543210' } });
    }
    fireEvent.click(screen.getByRole('button', { name: editBankDetails ? 'Save and Connect Settlement Account' : 'Reconnect Settlement Account' }));
    await screen.findByText('Connected');
    expect(axios.post.mock.calls.map(([url]) => url)).toEqual(editBankDetails
      ? ['/api/school/settings', '/api/school/settings/paystack/reconnect']
      : ['/api/school/settings/paystack/reconnect']);
    if (editBankDetails) {
      expect(axios.post.mock.calls[0][1]).toEqual({
        bank_name: 'Test Bank', bank_account: '9876543210', bank_account_name: 'Test School', bank_branch: 'Main',
      });
    }
    expect(axios.get.mock.calls.filter(([url]) => url === '/api/school/settings')).toHaveLength(2);
  });

  it('renders the saved tuition installment schedule', async () => {
    render(<SettingsPanel />);

    expect(await screen.findByText(/tuition installment plan/i)).toBeInTheDocument();
    expect(screen.getByText(/current schedule uses 2 installments/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue('Installment 1')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Installment 2')).toBeInTheDocument();
    expect(screen.getByText(/installment total: gh₵ 1000.00/i)).toBeInTheDocument();
    expect(screen.getByText(/2026-10-01/i)).toBeInTheDocument();
    expect(screen.getByText(/2026-11-30/i)).toBeInTheDocument();
  });

  it('supports 2, 3, and custom installment presets and shows total mismatch warnings', async () => {
    render(<SettingsPanel />);

    expect(await screen.findByText(/tuition installment plan/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /3 installments/i }));
    await waitFor(() => {
      expect(screen.getByText(/current schedule uses 3 installments/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /^custom$/i }));
    const customCountInput = screen.getByDisplayValue('3');
    fireEvent.change(customCountInput, { target: { value: '4' } });

    await waitFor(() => {
      expect(screen.getByDisplayValue('4')).toBeInTheDocument();
    });

    const amountInputs = screen.getAllByDisplayValue('250');
    fireEvent.change(amountInputs[0], { target: { value: '300' } });

    expect(screen.getByText(/before this schedule can be saved/i)).toBeInTheDocument();
  });
});