import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import TransactionHistory from '../TransactionHistory';

vi.mock('axios');
vi.mock('../../hooks/useSubscription', () => ({ default: () => ({ plan: 'Free Tier', hasFeature: () => false }) }));

describe('TransactionHistory', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');
    axios.get.mockResolvedValue({
      data: [
        {
          id: 1,
          date: '2026-09-19',
          student_name: 'Ama Mensah',
          type: 'Tuition',
          method: 'Paystack_Payment',
          display_amount: 21.0,
          applied_amount: 20.19,
          amount: 20.19,
          status: 'Confirmed',
          payment_category: {
            collection_channel: 'dedicated_virtual_account',
            reference_code: 'S001-TUIT-I1',
            split_code: 'SPLIT_school001_2000',
            settlement_mode: 'paystack_flat_split',
            transfer_total_amount: 21.0,
            applied_school_fee_amount: 20.19,
            collected_convenience_fee_amount: 0.4,
            actual_provider_fee_amount: 0.41,
            school_settlement_amount: 20.0,
            platform_settlement_amount: 0.4,
            provider_account_number: '7003000477792',
            payment_collection_intent_id: 77,
          },
        },
      ],
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('marks denied history as unavailable instead of empty', async () => {
    axios.get.mockRejectedValue({ response: { status: 403, data: { message: 'History temporarily denied' } } });
    render(<TransactionHistory />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Transaction history unavailable: History temporarily denied');
    expect(screen.queryByText('No transaction history recorded yet.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /export csv/i })).toBeDisabled();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('shows the tracked transfer amount breakdown for net school-fee payments', async () => {
    render(<TransactionHistory />);

    await waitFor(() => {
      expect(screen.getByText('Financial Ledger')).toBeInTheDocument();
    });

    expect(screen.getByText('Gross paid:')).toBeInTheDocument();
    expect(screen.getAllByText('GH₵ 21.00').length).toBeGreaterThan(0);
    expect(screen.getByText('Convenience deducted:')).toBeInTheDocument();
    expect(screen.getAllByText('GH₵ 0.40').length).toBeGreaterThan(0);
    expect(screen.getByText('Paystack fee deducted:')).toBeInTheDocument();
    expect(screen.getAllByText('GH₵ 0.41').length).toBeGreaterThan(0);
    expect(screen.getByText('Applied to school fee:')).toBeInTheDocument();
    expect(screen.getAllByText('GH₵ 20.19').length).toBeGreaterThan(0);
  });

  it('exports the tracked transfer breakdown in the CSV', async () => {
    let capturedCsv = '';
    const originalCreateElement = document.createElement.bind(document);
    const createObjectURL = vi.fn(() => 'blob:transactions');
    const click = vi.fn();
    const createElement = vi.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'a') {
        const anchor = originalCreateElement('a');
        anchor.click = click;
        return anchor;
      }
      return originalCreateElement(tagName);
    });
    vi.stubGlobal('URL', { createObjectURL });
    vi.stubGlobal('Blob', class MockBlob {
      constructor(parts) {
        capturedCsv = parts.join('');
      }
    });

    render(<TransactionHistory />);

    await waitFor(() => {
      expect(screen.getByText('Financial Ledger')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /export csv/i }));

    expect(capturedCsv).toContain('Gross Paid,Convenience Deducted,Paystack Fee Deducted,Applied School Fee');
    expect(capturedCsv).toContain('2026-09-19,"Ama Mensah",Tuition,"-",Paystack_Payment,21,20.19,Confirmed,S001-TUIT-I1,SPLIT_school001_2000,paystack_flat_split,21,0.4,0.41,20.19,20,0.4,0.4,77');
    expect(createObjectURL).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();

    createElement.mockRestore();
  });
});