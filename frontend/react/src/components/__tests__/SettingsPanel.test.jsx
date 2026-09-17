import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';

import SettingsPanel from '../SettingsPanel';

vi.mock('axios');
vi.mock('../TimetableManager', () => ({
  default: () => <div data-testid="timetable-manager" />,
}));
vi.mock('../TermManagementPanel', () => ({
  default: () => <div data-testid="term-management-panel" />,
}));

describe('SettingsPanel', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');
    localStorage.setItem('subscription_plan', 'Premium');

    axios.get.mockImplementation((url) => {
      if (url === '/api/school/subscription/effective-plan') {
        return Promise.resolve({
          data: {
            effective_plan: 'Premium',
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

    expect(screen.getByText('1.95%')).toBeInTheDocument();
    expect(screen.getByText('GH₵ 19.50')).toBeInTheDocument();
    expect(screen.getByText('GH₵ 1019.50')).toBeInTheDocument();
  });
});