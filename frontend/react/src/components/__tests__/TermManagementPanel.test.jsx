import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';

import TermManagementPanel from '../TermManagementPanel';

vi.mock('axios');

describe('TermManagementPanel', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');
    vi.spyOn(window, 'confirm').mockReturnValue(false);
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

  it('activates a term without a payment-required message', async () => {
    localStorage.setItem('term_calendar_prompted:TEST-001:2026/2027', 'true');

    axios.get.mockResolvedValueOnce({
      data: {
        terms: [
          { id: 7, name: 'Term 1', academic_year: '2026/2027', is_active: false },
        ],
        suggested_academic_year: '2026/2027',
      },
    });
    axios.post.mockResolvedValueOnce({
      data: {
        message: 'Activated Term 1 2026/2027',
      },
    });

    render(<TermManagementPanel />);

    const activateButton = await screen.findByRole('button', { name: /set active/i });
    fireEvent.click(activateButton);

    await waitFor(() => {
      expect(screen.getByText(/activated term 1 2026\/2027/i)).toBeInTheDocument();
    });

    expect(screen.queryByText(/payment is required before activating/i)).not.toBeInTheDocument();
  });

  it('loads an existing term into the form and updates its reopening date', async () => {
    localStorage.setItem('term_calendar_prompted:TEST-001:2026/2027', 'true');

    axios.get.mockResolvedValueOnce({
      data: {
        terms: [
          {
            id: 9,
            name: 'Term 3',
            academic_year: '2026/2027',
            start_date: '2027-04-20',
            end_date: '2027-07-22',
            billing_due_date: null,
            is_active: false,
          },
        ],
        suggested_academic_year: '2026/2027',
      },
    });
    axios.put.mockResolvedValueOnce({
      data: {
        message: 'Term updated successfully',
      },
    });

    render(<TermManagementPanel />);

  fireEvent.click(await screen.findByRole('button', { name: /edit/i }));

    const reopeningDate = screen.getByLabelText(/reopening date/i);
  fireEvent.change(reopeningDate, { target: { value: '2027-09-07' } });
  fireEvent.click(screen.getByRole('button', { name: /update term calendar/i }));

    await waitFor(() => {
      expect(axios.put).toHaveBeenCalledWith(
        '/api/school/terms/9',
        expect.objectContaining({
          billing_due_date: '2027-09-07',
          name: 'Term 3',
        }),
        expect.any(Object)
      );
    });
  });
});