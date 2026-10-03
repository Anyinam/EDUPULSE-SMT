import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
      if (url === '/api/school/classes?active_only=true') return Promise.resolve({ data: [{ name: 'JHS 1', class_name: 'JHS 1' }] });
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

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

const mockReportApi = (overrides = {}) => {
  axios.get.mockImplementation((url) => {
    if (Object.hasOwn(overrides, url)) return overrides[url]();
    if (url === '/api/school/classes?active_only=true') {
      return Promise.resolve({ data: [{ class_name: 'School A' }, { name: 'School B' }, 'School C'] });
    }
    if (url === '/api/school/terms') {
      return Promise.resolve({ data: { terms: [{ name: 'Term 2', academic_year: '2027/2028', is_active: true }] } });
    }
    if (url === '/api/school/grading-scheme') return Promise.resolve({ data: {} });
    if (url.startsWith('/api/students/by-class/')) {
      const className = decodeURIComponent(url.split('/').at(-1));
      return Promise.resolve({ data: [{ id: className, name: `${className} learner` }] });
    }
    if (url.endsWith('/terminal-report')) {
      const studentId = url.split('/')[3];
      return Promise.resolve({ data: { student_name: `${studentId} report`, class_name: studentId } });
    }
    if (url.endsWith('/reports')) return Promise.resolve({ data: [] });
    throw new Error(`Unexpected endpoint: ${url}`);
  });
};

describe('terminal report active classes and request ownership', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('school_id', 'test-school');
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('uses only the school active class list, trimming and deduplicating names without national grades', async () => {
    mockReportApi({
      '/api/school/classes?active_only=true': () => Promise.resolve({ data: [
        { class_name: ' School A ', name: 'Ignored alias' }, { name: 'School B' },
        'School A', ' School B ', '', '  ', null, {}, { class_name: 123 },
      ] }),
    });
    render(<TerminalReportPrinter />);
    const classSelect = screen.getByRole('combobox', { name: 'Report Class' });
    await waitFor(() => expect(classSelect).toBeEnabled());
    expect(within(classSelect).getAllByRole('option').map(option => option.value)).toEqual(['School A', 'School B']);
    expect(classSelect).toHaveValue('School A');
    expect(axios.get).toHaveBeenCalledWith('/api/school/classes?active_only=true', {
      headers: { Authorization: 'Bearer test-token', 'X-School-ID': 'test-school' },
    });
    expect(axios.get.mock.calls.some(([url]) => url.includes('national') || url === '/api/school/classes')).toBe(false);
    expect(await screen.findByRole('heading', { name: 'School A report' })).toBeInTheDocument();
  });

  it.each([[], [null, {}, ' ', { name: '' }], { classes: ['Phantom'] }])('shows an empty class list without phantom classes for %j', async (data) => {
    mockReportApi({ '/api/school/classes?active_only=true': () => Promise.resolve({ data }) });
    render(<TerminalReportPrinter />);
    const classSelect = screen.getByRole('combobox', { name: 'Report Class' });
    await waitFor(() => expect(within(classSelect).getByRole('option')).toHaveTextContent('No active classes found'));
    expect(classSelect).toBeDisabled();
    expect(classSelect).toHaveValue('');
    expect(screen.getByRole('combobox', { name: 'Report Student' })).toHaveValue('');
    expect(axios.get.mock.calls.some(([url]) => url.startsWith('/api/students/'))).toBe(false);
  });

  it('distinguishes loading from a failed class request without falling back to grades', async () => {
    const classes = deferred();
    mockReportApi({ '/api/school/classes?active_only=true': () => classes.promise });
    render(<TerminalReportPrinter />);
    const classSelect = screen.getByRole('combobox', { name: 'Report Class' });
    expect(classSelect).toBeDisabled();
    expect(within(classSelect).getByRole('option')).toHaveTextContent('Loading classes...');
    await act(async () => { classes.reject(new Error('offline')); });
    expect(within(classSelect).getByRole('option')).toHaveTextContent('Unable to load classes');
    expect(classSelect).toHaveValue('');
    expect(screen.getByText(/Error loading classes: offline/)).toBeInTheDocument();
    expect(axios.get.mock.calls.some(([url]) => url.startsWith('/api/students/'))).toBe(false);
  });

  it.each(['empty', 'error'])('clears the old selection and preview immediately when the new roster is %s', async (state) => {
    const students = deferred();
    mockReportApi({ '/api/students/by-class/School%20B': () => students.promise });
    render(<TerminalReportPrinter />);
    await screen.findByRole('heading', { name: 'School A report' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Report Class' }), { target: { value: 'School B' } });
    expect(screen.getByRole('combobox', { name: 'Report Student' })).toHaveValue('');
    expect(screen.getByRole('combobox', { name: 'Report Student' })).toBeDisabled();
    expect(screen.queryByRole('heading', { name: 'School A report' })).not.toBeInTheDocument();
    await act(async () => {
      if (state === 'error') students.reject(new Error('roster offline'));
      else students.resolve({ data: [] });
    });
    expect(screen.getByRole('combobox', { name: 'Report Student' })).toHaveValue('');
    expect(screen.getByText(state === 'error' ? /Error loading students: roster offline/ : /No students in this class/)).toBeInTheDocument();
    expect(axios.get.mock.calls.filter(([url]) => url.endsWith('/terminal-report')).map(([url]) => url)).toEqual(['/api/students/School A/terminal-report']);
  });

  it.each(['resolve', 'reject'])('ignores an obsolete student request that later %s after fast switching', async (outcome) => {
    const oldStudents = deferred();
    mockReportApi({ '/api/students/by-class/School%20B': () => oldStudents.promise });
    render(<TerminalReportPrinter />);
    await screen.findByRole('heading', { name: 'School A report' });
    const classSelect = screen.getByRole('combobox', { name: 'Report Class' });
    fireEvent.change(classSelect, { target: { value: 'School B' } });
    fireEvent.change(classSelect, { target: { value: 'School C' } });
    await screen.findByRole('heading', { name: 'School C report' });
    await act(async () => {
      if (outcome === 'reject') oldStudents.reject(new Error('stale roster error'));
      else oldStudents.resolve({ data: [{ id: 'old', name: 'Stale learner' }] });
    });
    expect(screen.getByRole('combobox', { name: 'Report Student' })).toHaveValue('School C');
    expect(screen.queryByText('Stale learner')).not.toBeInTheDocument();
    expect(screen.queryByText(/stale roster error/)).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'School C report' })).toBeInTheDocument();
    expect(axios.get.mock.calls.some(([url]) => url === '/api/students/old/terminal-report')).toBe(false);
  });

  it.each([
    ['resolve', 'before'], ['reject', 'before'],
    ['resolve', 'after'], ['reject', 'after'],
  ])('ignores an obsolete report that %s %s the current report arrives', async (outcome, timing) => {
    const oldReport = deferred();
    const newReport = deferred();
    mockReportApi({
      '/api/students/School A/terminal-report': () => oldReport.promise,
      '/api/students/School B/terminal-report': () => newReport.promise,
    });
    render(<TerminalReportPrinter />);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/students/School A/terminal-report', expect.any(Object)));
    fireEvent.change(screen.getByRole('combobox', { name: 'Report Class' }), { target: { value: 'School B' } });
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/students/School B/terminal-report', expect.any(Object)));
    if (timing === 'after') {
      await act(async () => { newReport.resolve({ data: { student_name: 'Current report' } }); });
    }
    await act(async () => {
      if (outcome === 'reject') oldReport.reject(new Error('stale report error'));
      else oldReport.resolve({ data: { student_name: 'Stale report' } });
    });
    if (timing === 'before') expect(screen.getByText(/Loading report/)).toBeInTheDocument();
    else expect(screen.getByRole('heading', { name: 'Current report' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Stale report' })).not.toBeInTheDocument();
    expect(screen.queryByText(/No report data available/)).not.toBeInTheDocument();
    expect(axios.get.mock.calls.some(([url]) => url === '/api/students/School A/reports')).toBe(false);
    if (timing === 'before') {
      await act(async () => { newReport.resolve({ data: { student_name: 'Current report' } }); });
    }
    expect(screen.getByRole('heading', { name: 'Current report' })).toBeInTheDocument();
  });

  it.each(['resolve', 'reject'])('ignores obsolete performance history that later %s', async (outcome) => {
    const oldHistory = deferred();
    mockReportApi({
      '/api/students/School A/reports': () => oldHistory.promise,
      '/api/students/School B/reports': () => Promise.resolve({ data: [{ academic_term: 'Term 2', academic_year: '2027/2028', term_average: '82' }] }),
    });
    render(<TerminalReportPrinter />);
    await screen.findByRole('heading', { name: 'School A report' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Report Class' }), { target: { value: 'School B' } });
    await screen.findByText('82%');
    await act(async () => {
      if (outcome === 'reject') oldHistory.reject(new Error('stale history error'));
      else oldHistory.resolve({ data: [{ academic_term: 'Term 1', academic_year: '2026/2027', term_average: '12' }] });
    });
    expect(screen.getByText('82%')).toBeInTheDocument();
    expect(screen.queryByText('12%')).not.toBeInTheDocument();
  });

  it('does not replace a manually selected reporting period with a late report', async () => {
    const oldReport = deferred();
    let firstReport = true;
    mockReportApi({
      '/api/students/School A/terminal-report': () => {
        if (firstReport) {
          firstReport = false;
          return oldReport.promise;
        }
        return Promise.resolve({ data: { student_name: 'Manually selected period' } });
      },
    });
    render(<TerminalReportPrinter />);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/students/School A/terminal-report', expect.any(Object)));
    fireEvent.change(screen.getByRole('textbox', { name: 'Report Year' }), { target: { value: '2025/2026' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Report Term' }), { target: { value: 'Term 3' } });
    await screen.findByRole('heading', { name: 'Manually selected period' });
    await act(async () => { oldReport.resolve({ data: { student_name: 'Obsolete period' } }); });
    expect(screen.getByRole('heading', { name: 'Manually selected period' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Obsolete period' })).not.toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Report Year' })).toHaveValue('2025/2026');
    expect(screen.getByRole('combobox', { name: 'Report Term' })).toHaveValue('Term 3');
  });

  it('keeps manual year and term choices when switching classes and viewing reports', async () => {
    mockReportApi();
    render(<TerminalReportPrinter />);
    await screen.findByRole('heading', { name: 'School A report' });
    fireEvent.change(screen.getByRole('textbox', { name: 'Report Year' }), { target: { value: '2025/2026' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Report Term' }), { target: { value: 'Term 3' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Report Class' }), { target: { value: 'School B' } });
    await screen.findByRole('heading', { name: 'School B report' });
    expect(screen.getByRole('textbox', { name: 'Report Year' })).toHaveValue('2025/2026');
    expect(screen.getByRole('combobox', { name: 'Report Term' })).toHaveValue('Term 3');
    expect(axios.get).toHaveBeenLastCalledWith('/api/students/School B/reports', expect.any(Object));
    expect(axios.get).toHaveBeenCalledWith('/api/students/School B/terminal-report', expect.objectContaining({ params: { term: 'Term 3', year: '2025/2026' } }));
    expect(axios.post).not.toHaveBeenCalled();
  });
});