import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import AdmissionsPanel from '../AdmissionsPanel';
import useSubscription from '../../hooks/useSubscription';

vi.mock('axios');
vi.mock('../../components/BulkStatusUpdate', () => ({ default: () => <div /> }));
vi.mock('../../components/PromotionThresholdManager', () => ({ default: () => <div /> }));
vi.mock('../../hooks/useSubscription', () => ({
  default: vi.fn(),
}));
vi.mock('../../hooks/useSchoolClasses', () => ({
  default: () => ({ classes: ['JHS 3'] }),
}));

describe('AdmissionsPanel', () => {
  beforeEach(() => {
    vi.stubGlobal('alert', vi.fn());
    vi.stubGlobal('URL', class extends URL {
      static createObjectURL = vi.fn(() => 'blob:passport-preview');
      static revokeObjectURL = vi.fn();
    });
    useSubscription.mockReturnValue({ plan: 'Basic', hasFeature: () => true });
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');
    axios.get.mockResolvedValue({
      data: {
        applications: [{
          id: 1,
          first_name: 'Daniel',
          surname: 'Asare',
          application_code: 'ADM-001',
          preferred_class: 'JHS 3',
          status: 'ReviewReady',
          ai_readiness_score: 95,
          ai_summary: 'Ready for review.',
          ai_recommendation: 'manual_review',
          document_manifest: [],
        }],
        archived_applications: [{
          id: 2,
          first_name: 'Ama',
          surname: 'Mensah',
          application_code: 'ADM-002',
          preferred_class: 'JHS 3',
          status: 'Approved',
          reviewed_at: '2026-09-20T12:00:00Z',
          reviewer_notes: 'Approved after document review.',
          document_manifest: [{
            document_id: 'doc-1',
            original_filename: 'report.pdf',
            download_available: false,
          }],
        }],
        summary: { ReviewReady: 1, Approved: 1 },
        archive_summary: { Approved: 1 },
      },
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it.each([true, false])('submits the passport photo and resets it only after successful admission (%s)', async (succeeds) => {
    if (succeeds) axios.post.mockResolvedValue({ data: {} });
    else axios.post.mockRejectedValue({ response: { data: { message: 'Admission failed.' } } });
    render(<AdmissionsPanel />);
    fireEvent.change(screen.getByPlaceholderText('e.g. Kofi'), { target: { value: 'Kofi' } });
    fireEvent.change(screen.getByPlaceholderText('e.g. Mensah'), { target: { value: 'Mensah' } });
    const input = screen.getByLabelText('Passport Photo');
    const photo = new File(['photo'], 'learner.png', { type: 'image/png' });
    fireEvent.change(input, { target: { files: [photo] } });
    expect(await screen.findByAltText('Student passport photo preview')).toBeInTheDocument();
    fireEvent.submit(screen.getByRole('button', { name: 'Admit Student' }).closest('form'));
    await waitFor(() => expect(axios.post).toHaveBeenCalledWith('/api/admissions/admit', expect.objectContaining({
      first_name: 'Kofi', surname: 'Mensah', profile_picture: 'data:image/png;base64,cGhvdG8=',
    }), expect.any(Object)));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Admit Student' })).toBeEnabled());
    if (succeeds) expect(screen.queryByAltText('Student passport photo preview')).not.toBeInTheDocument();
    else expect(screen.getByAltText('Student passport photo preview')).toBeInTheDocument();
  });

  it('rejects non-photo files before admission', async () => {
    render(<AdmissionsPanel />);
    await screen.findByText('Daniel Asare');
    fireEvent.change(screen.getByLabelText('Passport Photo'), {
      target: { files: [new File(['pdf'], 'report.pdf', { type: 'application/pdf' })] },
    });
    expect(screen.getByRole('alert')).toHaveTextContent('Choose a JPG, PNG, or WebP photo no larger than 5 MB.');
    expect(screen.getByRole('button', { name: 'Admit Student' })).toBeDisabled();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('keeps core admissions and CSV upload available on Free Tier', async () => {
    useSubscription.mockReturnValue({ plan: 'Free Tier', hasFeature: () => false });
    render(<AdmissionsPanel />);
    await waitFor(() => expect(screen.getByText('Daniel Asare')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Upload CSV' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Admit Student/i })).toBeInTheDocument();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('keeps review and archive details collapsed until selected', async () => {
    render(<AdmissionsPanel />);

    await waitFor(() => expect(screen.getByText('Daniel Asare')).toBeInTheDocument());
    expect(screen.queryByText('Guardian Contact')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /open review/i }));
    expect(screen.getByText('Guardian Contact')).toBeInTheDocument();

    expect(screen.queryByText('Approved after document review.')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /ama mensah/i }));
    expect(screen.getByText('Approved after document review.')).toBeInTheDocument();
    expect(screen.getByText('File missing')).toBeInTheDocument();
  });
});