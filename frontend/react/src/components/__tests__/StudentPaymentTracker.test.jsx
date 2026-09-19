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

  it('shows a generic unavailable message without upgrade guidance for non-plan payment-code errors', async () => {
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
              error: 'student_payment_identity_missing',
              message: 'This student does not have a payment identity yet. Add or repair the student ID before sharing parent payment instructions.',
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
      expect(screen.getByText(/unable to load payment references right now/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/add or repair the student id before sharing parent payment instructions/i)).toBeInTheDocument();
    expect(screen.queryByText(/upgrade the school subscription or reduce active enrollment/i)).not.toBeInTheDocument();
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
            tuition_convenience_fee_percentage: 1.95,
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
                convenience_fee_amount: 1.95,
                total_amount: 101.95,
              },
            },
            virtual_route: {
              bank_name: 'Paystack-Titan',
              account_number: '0192837465',
              account_name: 'EDUPULSE / AMA MENSAH',
              base_amount: 100,
              convenience_fee_amount: 1.95,
              total_amount: 101.95,
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
      expect(screen.getByText(/tracked transfer account ready/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Paystack-Titan/i)).toBeInTheDocument();
    expect(screen.getAllByText(/0192837465/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Convenience fee: 1.95% = GH₵ 1.95/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Transfer total: GH₵ 101.95/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /tracked transfer/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /online checkout link/i })).not.toBeInTheDocument();
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
            payment_identity: {
              supports_fee_route_dvas: true,
            },
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
            payment_identity: {
              supports_fee_route_dvas: true,
            },
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

    axios.post.mockImplementation((url) => {
      if (url === '/api/students/1/payment-codes/S001-T1/virtual-account') {
        return Promise.resolve({
          data: {
            payment_code: {
              fee_type: 'Tuition',
              code: 'S001-T1',
              reference_code: 'S001-T1',
              base_amount: 120,
              has_virtual_route: true,
              virtual_route: {
                bank_name: 'Paystack-Titan',
                account_number: '1111111111',
                account_name: 'EDUPULSE / AMA MENSAH',
                total_amount: 126,
              },
            },
            virtual_route: {
              bank_name: 'Paystack-Titan',
              account_number: '1111111111',
              account_name: 'EDUPULSE / AMA MENSAH',
              total_amount: 126,
            },
          },
        });
      }

      if (url === '/api/students/2/payment-codes/S002-T1/virtual-account') {
        return Promise.resolve({
          data: {
            payment_code: {
              fee_type: 'Tuition',
              code: 'S002-T1',
              reference_code: 'S002-T1',
              base_amount: 120,
              has_virtual_route: true,
              virtual_route: {
                bank_name: 'Paystack-Titan',
                account_number: '2222222222',
                account_name: 'EDUPULSE / YAW OWUSU',
                total_amount: 126,
              },
            },
            virtual_route: {
              bank_name: 'Paystack-Titan',
              account_number: '2222222222',
              account_name: 'EDUPULSE / YAW OWUSU',
              total_amount: 126,
            },
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
    expect(printWindow.document.write.mock.calls[0][0]).toContain('1111111111');
    expect(printWindow.document.write.mock.calls[0][0]).toContain('2222222222');
  });

  it('prints the tracked transfer receipt breakdown with net school fee recorded', async () => {
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
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 120,
            terminal_report_fee: 0,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments') {
        return Promise.resolve({
          data: [
            {
              id: 9,
              payment_type: 'Tuition',
              method: 'Paystack_Payment',
              amount: 20.19,
              display_amount: 21.0,
              applied_amount: 20.19,
              reference_id: '6aae84c407261e44077d06d6',
              status: 'Confirmed',
              date_paid: '2026-09-19T09:00:00Z',
              payment_category: {
                collection_channel: 'dedicated_virtual_account',
                transfer_total_amount: 21.0,
                collected_convenience_fee_amount: 0.4,
                actual_provider_fee_amount: 0.41,
                applied_school_fee_amount: 20.19,
              },
            },
          ],
        });
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
                base_amount: 120,
                has_virtual_route: true,
                virtual_route: {
                  bank_name: 'Paystack-Titan',
                  account_number: '1111111111',
                  account_name: 'EDUPULSE / AMA MENSAH',
                  base_amount: 120,
                  convenience_fee_amount: 2.34,
                  total_amount: 122.34,
                },
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
    });

    fireEvent.click(screen.getByText('Ama Mensah'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /print latest receipt/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /print latest receipt/i }));

    await waitFor(() => {
      expect(window.open).toHaveBeenCalled();
    });

    expect(printWindow.document.write).toHaveBeenCalled();
    const printedHtml = printWindow.document.write.mock.calls[0][0];
    expect(printedHtml).toContain('Gross Transfer Received');
    expect(printedHtml).toContain('Convenience Fee Deducted');
    expect(printedHtml).toContain('Paystack Fee Deducted');
    expect(printedHtml).toContain('Net School Fee Recorded');
    expect(printedHtml).toContain('GH₵ 21.00');
    expect(printedHtml).toContain('GH₵ 0.40');
    expect(printedHtml).toContain('GH₵ 0.41');
    expect(printedHtml).toContain('GH₵ 20.19');
  });

  it('does not show the paystack reconciliation card in the tenant tracker', async () => {
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
        return Promise.resolve({
          data: {
            student_name: 'Ama Mensah',
            student_code: 'S001',
            payment_identity: {
              supports_fee_route_dvas: false,
            },
            payment_codes: [],
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    });

    expect(screen.queryByText(/recover a successful tracked transfer by exact reference/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/transaction reference/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /recover paystack payment/i })).not.toBeInTheDocument();
  });

  it('reconciles a successful tracked transfer reference from the payment tracker', async () => {
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
            tuition_convenience_fee_percentage: 1,
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
                preferred_payment_model: 'virtual_account_ready',
                has_virtual_route: true,
                virtual_route: {
                  bank_name: 'Affinity Ghana Savings and Loans',
                  account_number: '7003000477792',
                  account_name: 'EDUPULSE / AMA MENSAH',
                  base_amount: 100,
                  convenience_fee_amount: 1,
                  total_amount: 101,
                },
              },
            ],
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    axios.post.mockImplementation((url, body) => {
      if (url === '/api/finance/paystack/recover-reference') {
        expect(body).toEqual({ reference: '6aae84c407261e44077d06d6' });
        return Promise.resolve({
          data: {
            status: 'recorded',
            reference: '6aae84c407261e44077d06d6',
            message: 'Tracked transfer recovered and attached to the student.',
            gross_amount_paid: 21,
            collected_convenience_fee_amount: 0.4,
            actual_provider_fee_amount: 0.41,
            applied_school_fee_amount: 20.19,
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
      expect(screen.getByText(/recover a successful tracked transfer by exact reference/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/transaction reference/i), {
      target: { value: '6aae84c407261e44077d06d6' },
    });
    fireEvent.click(screen.getByRole('button', { name: /recover paystack payment/i }));

    await waitFor(() => {
      expect(screen.getByText(/tracked transfer recovered and attached to the student/i)).toBeInTheDocument();
    });

    expect(screen.getByText('Gross paid: GH₵ 21.00')).toBeInTheDocument();
    expect(screen.getByText('Convenience deducted: GH₵ 0.40')).toBeInTheDocument();
    expect(screen.getByText('Paystack fee deducted: GH₵ 0.41')).toBeInTheDocument();
    expect(screen.getByText('Applied to school fee: GH₵ 20.19')).toBeInTheDocument();

    expect(axios.post).toHaveBeenCalledWith(
      '/api/finance/paystack/recover-reference',
      { reference: '6aae84c407261e44077d06d6' },
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer token-1',
          'X-School-ID': 'TEST-001',
        }),
      })
    );
  });

  it('shows tuition installments with their own status and deadlines', async () => {
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
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 1000,
            tuition_convenience_fee_percentage: 1.95,
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
              tuition_installments_enabled: true,
            },
            payment_codes: [
              {
                fee_type: 'Tuition',
                code: 'S001-TUIT-I1',
                reference_code: 'S001-TUIT-I1',
                base_amount: 500,
                total_amount: 509.75,
                has_virtual_route: true,
                virtual_route: {
                  bank_name: 'Paystack-Titan',
                  account_number: '1111111111',
                  account_name: 'EDUPULSE / AMA MENSAH',
                  base_amount: 500,
                  convenience_fee_amount: 9.75,
                  total_amount: 509.75,
                },
                payment_category: {
                  fee_type: 'Tuition',
                  installment_number: 1,
                  installment_label: 'Installment 1',
                  installment_status: 'open',
                  installment_start_date: '2026-10-01',
                  installment_due_date: '2026-10-31',
                  installment_paid_amount: 0,
                  installment_outstanding_amount: 500,
                },
              },
              {
                fee_type: 'Tuition',
                code: 'S001-TUIT-I2',
                reference_code: 'S001-TUIT-I2',
                base_amount: 500,
                total_amount: 509.75,
                has_virtual_route: true,
                virtual_route: {
                  bank_name: 'Paystack-Titan',
                  account_number: '2222222222',
                  account_name: 'EDUPULSE / AMA MENSAH',
                  base_amount: 500,
                  convenience_fee_amount: 9.75,
                  total_amount: 509.75,
                },
                payment_category: {
                  fee_type: 'Tuition',
                  installment_number: 2,
                  installment_label: 'Installment 2',
                  installment_status: 'upcoming',
                  installment_start_date: '2026-11-01',
                  installment_due_date: '2026-11-30',
                  installment_paid_amount: 0,
                  installment_outstanding_amount: 500,
                },
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
    });

    fireEvent.click(screen.getByText('Ama Mensah'));

    await waitFor(() => {
      expect(screen.getByText('Installment 1')).toBeInTheDocument();
      expect(screen.getByText('Installment 2')).toBeInTheDocument();
    });

    expect(screen.getByText(/open • opens 2026-10-01 • due 2026-10-31/i)).toBeInTheDocument();
    expect(screen.getByText(/upcoming • opens 2026-11-01 • due 2026-11-30/i)).toBeInTheDocument();
    expect(screen.getAllByText(/paid so far on this installment: gh₵ 0.00 • remaining: gh₵ 500.00/i)).toHaveLength(2);
    expect(screen.queryByText('Required:')).not.toBeInTheDocument();
  });
});