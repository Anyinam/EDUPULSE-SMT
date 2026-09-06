import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import StudentPaymentTracker from '../StudentPaymentTracker';

vi.mock('axios');
vi.mock('../../hooks/useBranding', () => ({
  useBranding: () => ({ branding: {} }),
}));

describe('StudentPaymentTracker', () => {
  beforeEach(() => {
    vi.stubGlobal('alert', vi.fn());
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');

    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
              parent_name: 'Kojo Mensah',
              parent_phone: '0240000000',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 120,
            terminal_report_fee: 10,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.reject({
          response: {
            data: {
              error: 'payment_collection_blocked',
              message: 'Parent payment collection is paused because this school is on Free Tier with 54 active students, above the 50-student limit.',
              effective_plan: 'Free Tier',
              active_students: 54,
              plan_limit: 50,
            },
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it('shows a blocked collection banner instead of payment references', async () => {
    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Ama Mensah'));

    await waitFor(() => {
      expect(screen.getByText(/parent payment references are currently blocked/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/upgrade the school subscription or reduce active enrollment/i)).toBeInTheDocument();
    expect(screen.getByText('54')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
  });

  it('shows the verification gate before payment instructions are available', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
              parent_name: 'Kojo Mensah',
              parent_phone: '0240000000',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 120,
            terminal_report_fee: 10,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments') {
        return Promise.reject({
          response: {
            data: {
              error: 'school_verification_required',
              message: 'School verification is required before payment instructions, collection, or payment records are available.',
            },
          },
        });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.reject({
          response: {
            data: {
              error: 'school_verification_required',
              message: 'School verification is required before payment instructions, collection, or payment records are available.',
            },
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Ama Mensah'));

    await waitFor(() => {
      expect(screen.getByText(/submit and complete school verification before sharing payment instructions/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/verification sits above subscription access for payment operations/i)).toBeInTheDocument();
  });

  it('filters the student list by class before selection', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
              parent_name: 'Kojo Mensah',
              parent_phone: '0240000000',
            },
            {
              id: 2,
              name: 'Yaw Owusu',
              student_code: 'S002',
              current_class: 'JHS 2',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 120,
            terminal_report_fee: 10,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments' || url === '/api/students/2/payments') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/api/students/1/payment-codes' || url === '/api/students/2/payment-codes') {
        return Promise.resolve({
          data: {
            student_name: 'Ama Mensah',
            student_code: 'S001',
            payment_codes: [],
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
      expect(screen.getByText('Yaw Owusu')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByDisplayValue('All Classes'), {
      target: { value: 'JHS 2' },
    });

    expect(screen.queryByText('Ama Mensah')).not.toBeInTheDocument();
    expect(screen.getByText('Yaw Owusu')).toBeInTheDocument();
    expect(screen.getByText(/1 student found in JHS 2/i)).toBeInTheDocument();
  });

  it('generates and shows a tracked transfer account for a payment reference', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
              parent_name: 'Kojo Mensah',
              parent_phone: '0240000000',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 100,
            terminal_report_fee: 0,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.resolve({
          data: {
            student_name: 'Ama Mensah',
            student_code: 'S001',
            payment_identity: {
              supports_fee_route_dvas: true,
            },
            payment_codes: [
              {
                fee_type: 'Tuition',
                code: 'S001-T1',
                reference_code: 'S001-T1',
                base_amount: 100,
                preferred_payment_model: 'reference_first',
                has_virtual_route: false,
                virtual_route: null,
              },
            ],
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    axios.post.mockImplementation((url) => {
      if (url === '/api/students/1/payment-codes/S001-T1/virtual-account') {
        return Promise.resolve({
          data: {
            message: 'Tracked transfer account generated successfully.',
            payment_code: {
              fee_type: 'Tuition',
              code: 'S001-T1',
              reference_code: 'S001-T1',
              base_amount: 100,
              preferred_payment_model: 'virtual_account_ready',
              has_virtual_route: true,
              virtual_route: {
                bank_name: 'Paystack-Titan',
                account_number: '0192837465',
                account_name: 'EDUPULSE / AMA MENSAH',
                base_amount: 100,
                convenience_fee_amount: 6,
                total_amount: 106,
              },
            },
            virtual_route: {
              bank_name: 'Paystack-Titan',
              account_number: '0192837465',
              account_name: 'EDUPULSE / AMA MENSAH',
              base_amount: 100,
              convenience_fee_amount: 6,
              total_amount: 106,
            },
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Ama Mensah'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Tracked Transfer' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Tracked Transfer' }));

    await waitFor(() => {
      expect(screen.getByText(/tracked transfer account ready/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Paystack-Titan/i)).toBeInTheDocument();
    expect(screen.getByText(/0192837465/i)).toBeInTheDocument();
    expect(screen.getByText(/Transfer total: GH₵ 106.00/i)).toBeInTheDocument();
    expect(axios.post).toHaveBeenCalledWith(
      '/api/students/1/payment-codes/S001-T1/virtual-account',
      {},
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer token-1',
          'X-School-ID': 'TEST-001',
        }),
      })
    );
  });

  it('prints payment instructions for the filtered students in one batch', async () => {
    const printWindow = {
      document: {
        write: vi.fn(),
        close: vi.fn(),
      },
      focus: vi.fn(),
      print: vi.fn(),
    };
    vi.stubGlobal('open', vi.fn(() => printWindow));

    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
            },
            {
              id: 2,
              name: 'Yaw Owusu',
              student_code: 'S002',
              current_class: 'JHS 1',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 120,
            terminal_report_fee: 10,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments' || url === '/api/students/2/payments') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.resolve({
          data: {
            student_name: 'Ama Mensah',
            student_code: 'S001',
            class: 'JHS 1',
            payment_codes: [
              {
                fee_type: 'Tuition',
                code: 'S001-T1',
                reference_code: 'S001-T1',
                base_amount: 120,
              },
            ],
          },
        });
      }

      if (url === '/api/students/2/payment-codes') {
        return Promise.resolve({
          data: {
            student_name: 'Yaw Owusu',
            student_code: 'S002',
            class: 'JHS 1',
            payment_codes: [
              {
                fee_type: 'Tuition',
                code: 'S002-T1',
                reference_code: 'S002-T1',
                base_amount: 120,
              },
            ],
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
      expect(screen.getByText('Yaw Owusu')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /print 2 filtered instructions/i }));

    await waitFor(() => {
      expect(window.open).toHaveBeenCalled();
    });

    expect(axios.get).toHaveBeenCalledWith(
      '/api/students/1/payment-codes',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer token-1',
          'X-School-ID': 'TEST-001',
        }),
      })
    );
    expect(axios.get).toHaveBeenCalledWith(
      '/api/students/2/payment-codes',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer token-1',
          'X-School-ID': 'TEST-001',
        }),
      })
    );
    expect(printWindow.document.write).toHaveBeenCalled();
    expect(printWindow.document.write.mock.calls[0][0]).toContain('Ama Mensah');
    expect(printWindow.document.write.mock.calls[0][0]).toContain('Yaw Owusu');
  });
});