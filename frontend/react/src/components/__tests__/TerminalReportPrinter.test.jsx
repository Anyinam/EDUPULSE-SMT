import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import TerminalReportPrinter from '../TerminalReportPrinter';

vi.mock('axios');
vi.mock('../../hooks/useBranding', () => ({ useBranding: () => ({ branding: {} }) }));

describe('terminal report academic defaults', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token');
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-10-03T12:00:00'));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
    localStorage.clear();
  });

  it.each(['active', 'missing', 'error'])('uses school active term or current academic year when calendar is %s', async (calendarState) => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/school/terms') {
        if (calendarState === 'error') return Promise.reject(new Error('offline'));
        return Promise.resolve({ data: { terms: calendarState === 'active'
          ? [{ name: 'Term 2', academic_year: '2027/2028', is_active: true }]
          : [] } });
      }
      if (url === '/api/school/grades') return Promise.resolve({ data: ['JHS 1'] });
      if (url.startsWith('/api/students/by-class/')) return Promise.resolve({ data: [{ id: 1, name: 'Ama Mensah' }] });
      return Promise.resolve({ data: {} });
    });
    render(<TerminalReportPrinter />);
    const year = calendarState === 'active' ? '2027/2028' : '2026/2027';
    const term = calendarState === 'active' ? 'Term 2' : 'Term 1';
    await waitFor(() => expect(screen.getByRole('textbox', { name: 'Report Year' })).toBeEnabled());
    expect(screen.getByRole('textbox', { name: 'Report Year' })).toHaveValue(year);
    expect(screen.getByRole('combobox', { name: 'Report Term' })).toHaveValue(term);
    await waitFor(() => expect(axios.get.mock.calls.some(([, config]) => config?.params?.year === year && config?.params?.term === term)).toBe(true));
    expect(axios.get.mock.calls.some(([, config]) => config?.params?.year === '2024/2025')).toBe(false);
  });
});