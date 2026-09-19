import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import AuditReport from '../AuditReport';

vi.mock('axios');

describe('AuditReport', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');

    axios.get.mockImplementation((url) => {
      if (url.startsWith('/api/finance/audit/summary')) {
        return Promise.resolve({
          data: {
            currency: 'GH₵',
            summary: {
              total_transactions: 1,
              total_value: 20.19,
              verified_count: 1,
              is_chain_valid: true,
              integrity_status: 'Valid',
            },
          },
        });
      }

      if (url.startsWith('/api/finance/audit/ledger')) {
        return Promise.resolve({
          data: {
            ledger: [],
          },
        });
      }

      if (url === '/api/finance/transactions') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              date: '2026-09-19T09:00:00Z',
              student_name: 'Ama Mensah',
              student_code: 'S001',
              amount: 20.19,
              display_amount: 21.0,
              applied_amount: 20.19,
              type: 'Tuition',
              method: 'Paystack_Payment',
              reference_id: '6aae84c407261e44077d06d6',
              status: 'Confirmed',
              payment_category: {
                collection_channel: 'dedicated_virtual_account',
                reference_code: 'S001-TUIT-I1',
                transfer_total_amount: 21.0,
                applied_school_fee_amount: 20.19,
                collected_convenience_fee_amount: 0.4,
                actual_provider_fee_amount: 0.41,
                provider_account_number: '7003000477792',
                settlement_mode: 'paystack_flat_split',
              },
            },
          ],
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('shows the tracked transfer amount breakdown in recorded payment history', async () => {
    render(<AuditReport />);

    await waitFor(() => {
      expect(screen.getByText(/recorded payment history/i)).toBeInTheDocument();
    });

    expect(screen.getByText('Gross paid: GH₵ 21.00')).toBeInTheDocument();
    expect(screen.getByText('Convenience deducted: GH₵ 0.40')).toBeInTheDocument();
    expect(screen.getByText('Paystack fee deducted: GH₵ 0.41')).toBeInTheDocument();
    expect(screen.getByText('Applied to school fee: GH₵ 20.19')).toBeInTheDocument();
    expect(screen.getByText('Acct: 7003000477792')).toBeInTheDocument();
    expect(screen.getByText('Mode: paystack_flat_split')).toBeInTheDocument();
  });
});