import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';

import TermManagementPanel from '../TermManagementPanel';

vi.mock('axios');

describe('TermManagementPanel', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');
    axios.get.mockResolvedValue({
      data: {
        terms: [],
        suggested_academic_year: '2026/2027',
      },
    });
    axios.post.mockResolvedValue({
      data: {
        message: 'Imported 3 published term(s) for 2026/2027',
        created_count: 3,
        skipped_count: 0,
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('auto-prompts first-time schools to import the published GES calendar', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<TermManagementPanel />);

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalledWith(
        expect.stringContaining('Import the published GES academic calendar now?')
      );
    });

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        '/api/school/terms/import-national-calendar',
        { academic_year: '2026/2027' },
        expect.any(Object)
      );
    });

    expect(localStorage.getItem('term_calendar_prompted:TEST-001:2026/2027')).toBe('true');
  });

  it('keeps the term inactive and shows the payment link when activation requires billing first', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);

    axios.get.mockResolvedValueOnce({
      data: {
        terms: [
          { id: 7, name: 'Term 1', academic_year: '2026/2027', is_active: false },
        ],
        suggested_academic_year: '2026/2027',
      },
    });
    axios.post.mockRejectedValueOnce({
      response: {
        data: {
          error: 'billing_payment_required',
          message: 'Payment is required before activating Term 1 2026/2027.',
          payment_link: 'https://paystack.test/authorize',
          reference: 'TERM-PAY-001',
        },
      },
    });

    render(<TermManagementPanel />);

    const activateButton = await screen.findByRole('button', { name: /set active/i });
    activateButton.click();

    await waitFor(() => {
      expect(screen.getByText(/payment is required before activating term 1 2026\/2027/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/payment link ready: https:\/\/paystack.test\/authorize/i)).toBeInTheDocument();
    expect(screen.getByText(/the term will activate after payment is completed/i)).toBeInTheDocument();
  });
});