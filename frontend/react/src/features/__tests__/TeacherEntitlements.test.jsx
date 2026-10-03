import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import TeacherDashboard from '../TeacherDashboard';

vi.mock('axios');
vi.mock('../../hooks/useBranding', () => ({ useBranding: () => ({ branding: {} }) }));
vi.mock('../../hooks/useSchoolClasses', () => ({ default: () => ({ classes: ['JHS 1'] }) }));
vi.mock('../../components/TimetableManager', () => ({ default: () => null }));
vi.mock('../../components/TeacherAlerts', () => ({ default: () => null }));
vi.mock('../../components/AcademicGuidancePanel', () => ({ default: () => null }));

describe('teacher grade entitlements', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token');
  });
  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it.each(['free', 'loading', 'error', 'paid'])('gates grade controls when access is %s', async (accessState) => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/school/subscription/effective-plan') {
        if (accessState === 'loading') return new Promise(() => {});
        if (accessState === 'error') return Promise.reject(new Error('offline'));
        return Promise.resolve({ data: {
          effective_plan: accessState === 'paid' ? 'Basic' : 'Free Tier',
          features: { grade_entry: accessState === 'paid' },
        } });
      }
      if (url === '/api/teacher/assignments') {
        return Promise.resolve({ data: { assigned_classes: ['JHS 1'], assigned_subjects: ['Mathematics'] } });
      }
      if (url === '/api/school/grading-scheme') {
        return Promise.resolve({ data: { class_score_max: 30, exam_score_max: 70 } });
      }
      if (url === '/api/staff/check-headmaster') return Promise.resolve({ data: { has_headmaster: true } });
      if (url.startsWith('/api/students/by-class/')) return Promise.resolve({ data: [{ id: 1, name: 'Ama Mensah' }] });
      return Promise.resolve({ data: [] });
    });
    render(<TeacherDashboard />);
    await screen.findByText('Ama Mensah', { selector: 'p' });
    const submit = screen.getByRole('button', { name: 'Submit Grades to Homeroom' });
    const classScore = screen.getByTitle('Max: 30');
    const examScore = screen.getByTitle('Max: 70');
    if (accessState === 'paid') {
      await waitFor(() => expect(submit).toBeEnabled());
      expect(classScore).toBeEnabled();
      expect(examScore).toBeEnabled();
    } else {
      expect(submit).toBeDisabled();
      expect(classScore).toBeDisabled();
      expect(examScore).toBeDisabled();
      expect(screen.getByRole('button', { name: /Add Diagnostic/ })).toBeDisabled();
      expect(screen.getByText('Grade Entry Locked')).toBeInTheDocument();
      fireEvent.click(submit);
      expect(axios.post).not.toHaveBeenCalled();
    }
  });
});