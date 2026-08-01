import React from 'react';
import { render, waitFor } from '@testing-library/react';
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
});