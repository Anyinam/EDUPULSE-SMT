import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import PerformanceAnalytics from '../PerformanceAnalytics';
import * as htmlToImage from 'html-to-image';

vi.mock('axios');
vi.mock('html-to-image', () => ({ toPng: vi.fn(() => Promise.resolve('data:image/png;base64,mock')) }));

describe('PerformanceAnalytics', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');
    localStorage.setItem('subscription_plan', 'Premium');

    const schoolClasses = [
      { class_name: 'JHS 1' },
      { class_name: 'JHS 2' },
    ];

    const boardViewPreset = {
      name: 'Board View',
      filters: {
        academicTerm: 'Term 1',
        academicYear: '2025/2026',
        cohortFromClass: '',
        cohortToClass: '',
        analysisMode: 'multi-year',
        activeView: 'visualization',
      },
    };

    const overviewQuickCheckPreset = {
      name: 'Overview Quick Check',
      filters: {
        academicTerm: 'Term 2',
        academicYear: '2026/2027',
        cohortFromClass: 'JHS 1',
        cohortToClass: 'JHS 2',
        analysisMode: 'multi-year',
        activeView: 'visualization',
      },
    };

    axios.get.mockImplementation((url) => {
      if (url === '/api/school/subscription/effective-plan') {
        return Promise.resolve({ data: { plan: 'Premium', features: { advanced_analytics: true } } });
      }
      if (url === '/api/school/classes') {
        return Promise.resolve({ data: schoolClasses });
      }

      if (url === '/api/analytics/presets') {
        return Promise.resolve({
          data: {
            presets: [boardViewPreset],
            default_preset_name: 'Board View',
          },
        });
      }

      if (url === '/api/analytics/presets/history') {
        return Promise.resolve({
          data: {
            history: [
              {
                snapshot_id: 'aps-current',
                action: 'save',
                focus_preset_name: 'Board View',
                default_preset_name: 'Board View',
                preset_count: 1,
                preset_names: ['Board View'],
                analytics_config: {
                  presets: [boardViewPreset],
                  default_preset_name: 'Board View',
                },
                actor_name: 'headmaster',
                created_at: '2026-01-03T10:00:00Z',
                is_current: true,
              },
              {
                snapshot_id: 'aps-older',
                action: 'save',
                focus_preset_name: 'Overview Quick Check',
                default_preset_name: '',
                preset_count: 1,
                preset_names: ['Overview Quick Check'],
                analytics_config: {
                  presets: [overviewQuickCheckPreset],
                  default_preset_name: '',
                },
                actor_name: 'headmaster',
                created_at: '2025-12-01T10:00:00Z',
                is_current: false,
              },
            ],
          },
        });
      }

      return Promise.resolve({
        data: {
          academic_term: 'Term 1',
          academic_year: '2025/2026',
          compare_term: 'Term 3',
          compare_year: '2024/2025',
          same_term_previous_year: '2024/2025',
          classes: [
            {
              class_name: 'JHS 2',
              average: 74,
              count: 18,
              prev_average: 70,
              delta: 4,
              gender_breakdown: {
                Male: { average: 72, count: 9 },
                Female: { average: 76, count: 9 },
              },
            },
          ],
          year_over_year_classes: [
            { class_name: 'JHS 2', current_average: 74, previous_year_average: 68, delta: 6 },
          ],
          score_bands: { '80-100': 5, '70-79': 4, '65-69': 3, '50-64': 4, '0-49': 2 },
          subject_trends: [
            { subject: 'Mathematics', current_average: 78, previous_average: 69, delta: 9, count: 18 },
          ],
          cohort_migration_comparisons: [
            {
              from_class: 'JHS 1',
              to_class: 'JHS 2',
              from_year: '2024/2025',
              to_year: '2025/2026',
              matched_students: 12,
              previous_average: 68,
              current_average: 74,
              delta: 6,
            },
          ],
          available_academic_years: ['2023/2024', '2024/2025', '2025/2026'],
          multi_year_trends: [
            {
              class_name: 'JHS 2',
              points: [
                { academic_year: '2023/2024', average: 65, count: 16 },
                { academic_year: '2024/2025', average: 68, count: 17 },
                { academic_year: '2025/2026', average: 74, count: 18 },
              ],
            },
          ],
          subject_multi_year_trends: [
            {
              subject: 'Mathematics',
              latest_average: 78,
              delta: 10,
              points: [
                { academic_year: '2023/2024', average: 68, count: 16 },
                { academic_year: '2024/2025', average: 71, count: 17 },
                { academic_year: '2025/2026', average: 78, count: 18 },
              ],
            },
          ],
        },
      });
    });

    axios.post.mockImplementation((url, payload) => {
      if (url === '/api/analytics/presets/history/aps-older/restore') {
        return Promise.resolve({
          data: {
            presets: [overviewQuickCheckPreset],
            default_preset_name: '',
          },
        });
      }

      return Promise.resolve({
        data: {
          presets: [
            {
              name: payload.name,
              filters: payload.filters,
            },
          ],
          default_preset_name: payload.is_default ? payload.name : 'Board View',
        },
      });
    });

    axios.put.mockImplementation((url) => Promise.resolve({
      data: {
        presets: [
          {
            name: 'Board View',
            filters: {
              academicTerm: 'Term 1',
              academicYear: '2025/2026',
              cohortFromClass: '',
              cohortToClass: '',
              analysisMode: 'multi-year',
              activeView: 'visualization',
            },
          },
          {
            name: 'Overview Quick Check',
            filters: {
              academicTerm: 'Term 2',
              academicYear: '2026/2027',
              cohortFromClass: 'JHS 1',
              cohortToClass: 'JHS 2',
              analysisMode: 'multi-year',
              activeView: 'visualization',
            },
          },
        ],
        default_preset_name: decodeURIComponent(url.split('/')[4]),
      },
    }));

    axios.delete.mockResolvedValue({
      data: {
        presets: [],
        default_preset_name: '',
      },
    });

    global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    global.URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders cohort migration content and sends cohort filter params on refresh', async () => {
    render(<PerformanceAnalytics defaultView="visualization" />);

    await waitFor(() => {
      expect(screen.getByText(/Per-Subject Multi-Year Trends/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Single-Year' }));

    await waitFor(() => {
      expect(screen.getByText(/Cohort Migration Comparison/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByDisplayValue('Cohort From Class'), { target: { value: 'JHS 1' } });
    fireEvent.change(screen.getByDisplayValue('Cohort To Class'), { target: { value: 'JHS 2' } });
    fireEvent.click(screen.getByRole('button', { name: 'View' }));

    await waitFor(() => {
      expect(axios.get).toHaveBeenLastCalledWith('/api/analytics/class-performance', expect.objectContaining({
        params: expect.objectContaining({
          cohort_from_class: 'JHS 1',
          cohort_to_class: 'JHS 2',
        }),
      }));
    });
  });

  it('shows export actions and default preset state', async () => {
    render(<PerformanceAnalytics defaultView="visualization" />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Export CSV/i })).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /Export PDF/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Export PNG/i })).toBeInTheDocument();
    expect(screen.getByText(/Analytics Guide/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Board View is default preset/i })).toBeInTheDocument();
  });

  it('shows multi-year mode content and can export png', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    render(<PerformanceAnalytics defaultView="visualization" />);

    await waitFor(() => {
      expect(screen.getByText(/Per-Subject Multi-Year Trends/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Multi-Year Class Trend Lines/i)).toBeInTheDocument();
    expect(screen.getByText(/Per-Subject Multi-Year Trends/i)).toBeInTheDocument();
    expect(screen.getByText(/2023\/2024, 2024\/2025, 2025\/2026/i)).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Trend for JHS 2/i })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Trend for Mathematics/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Export PNG/i }));

    await waitFor(() => {
      expect(htmlToImage.toPng).toHaveBeenCalled();
    });

    clickSpy.mockRestore();
  });

  it('saves, reloads, and defaults analytics presets through the api', async () => {
    render(<PerformanceAnalytics defaultView="visualization" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('Term 1')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByDisplayValue('Term 1'), { target: { value: 'Term 2' } });
    fireEvent.change(screen.getByPlaceholderText(/Year/i), { target: { value: '2026/2027' } });
    fireEvent.change(screen.getByDisplayValue('Cohort From Class'), { target: { value: 'JHS 1' } });
    fireEvent.change(screen.getByDisplayValue('Cohort To Class'), { target: { value: 'JHS 2' } });
    fireEvent.change(screen.getByPlaceholderText('Preset name'), { target: { value: 'Overview Quick Check' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Preset' }));

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith('/api/analytics/presets', expect.objectContaining({
        name: 'Overview Quick Check',
        is_default: false,
      }), expect.any(Object));
    });

    fireEvent.change(screen.getByDisplayValue('Term 2'), { target: { value: 'Term 1' } });
    fireEvent.change(screen.getByDisplayValue('2026/2027'), { target: { value: '2025/2026' } });
    fireEvent.click(screen.getByRole('button', { name: 'Single-Year' }));
    fireEvent.click(screen.getByRole('button', { name: 'Overview Quick Check' }));

    await waitFor(() => {
      expect(axios.get).toHaveBeenLastCalledWith('/api/analytics/class-performance', expect.objectContaining({
        params: expect.objectContaining({
          academic_term: 'Term 2',
          academic_year: '2026/2027',
          cohort_from_class: 'JHS 1',
          cohort_to_class: 'JHS 2',
        }),
      }));
    });

    expect(screen.getByRole('button', { name: 'Multi-Year' })).toHaveClass('bg-slate-800');

    fireEvent.click(screen.getByRole('button', { name: /Set Overview Quick Check as default preset/i }));

    await waitFor(() => {
      expect(axios.put).toHaveBeenCalledWith('/api/analytics/presets/Overview%20Quick%20Check/default', {}, expect.any(Object));
    });
  });

  it('shows preset history diffs and restores an older snapshot', async () => {
    render(<PerformanceAnalytics defaultView="visualization" />);

    await waitFor(() => {
      expect(screen.getByText(/Preset History/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Snapshot includes Overview Quick Check/i)).toBeInTheDocument();
    expect(screen.getByText(/Current shelf includes Board View that would be removed/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Restore Snapshot/i }));

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith('/api/analytics/presets/history/aps-older/restore', {}, expect.any(Object));
    });
  });
});
