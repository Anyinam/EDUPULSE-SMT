import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import PaymentReceipts from '../PaymentReceipts';

vi.mock('axios');
vi.mock('../../hooks/useSubscription', () => ({ default: () => { throw new Error('Receipts must not read subscriptions'); } }));
vi.mock('../../hooks/useBranding', () => ({ useBranding: () => { throw new Error('Receipts must not require branding'); } }));

const receipt = {
  id: 1, receipt_number: 'R001', student_name: 'Ama <img src=x onerror=alert(1)>',
  student_code: 'S001', class_name: 'JHS 1', payment_type: 'Tuition', method: 'Cash',
  status: 'Pending', date_paid: null, reference_id: '<script>alert("x")</script>',
  display_amount: 0, applied_amount: 0, convenience_fee_amount: 2, provider_fee_amount: 3,
};
const response = { receipts: [receipt], total: 51, limit: 50, offset: 0, school_name: 'School <Test> & "Friends"', currency: 'GHS' };

describe('PaymentReceipts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');
    localStorage.setItem('plan', 'Free Tier');
    axios.get.mockResolvedValue({ data: response });
  });
  afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

  it('loads on Free using only the receipt archive, without collection or subscription reads', async () => {
    render(<PaymentReceipts />);
    expect(await screen.findByText(receipt.student_name)).toBeInTheDocument();
    expect(axios.get).toHaveBeenCalledTimes(1);
    expect(axios.get).toHaveBeenCalledWith('/api/finance/receipts', {
      params: { q: '', offset: 0, limit: 50 },
      headers: { Authorization: 'Bearer token-1', 'X-School-ID': 'TEST-001' },
    });
    expect(axios.post).not.toHaveBeenCalled();
    expect(screen.getByText('GHS 0.00')).toBeInTheDocument();
  });

  it.each(['Pending', 'Rejected'])('prints escaped content and the actual %s status after load', async (status) => {
    axios.get.mockResolvedValue({ data: { ...response, receipts: [{ ...receipt, status }] } });
    const popup = { document: { open: vi.fn(), write: vi.fn(), close: vi.fn() }, addEventListener: vi.fn(), focus: vi.fn(), print: vi.fn() };
    vi.spyOn(window, 'open').mockReturnValue(popup);
    render(<PaymentReceipts />);
    fireEvent.click(await screen.findByRole('button', { name: 'Print receipt R001' }));
    const html = popup.document.write.mock.calls[0][0];
    const parsed = new DOMParser().parseFromString(html, 'text/html');
    expect(parsed.querySelector('script, img')).toBeNull();
    expect(parsed.body.textContent).toContain(response.school_name);
    expect(parsed.body.textContent).toContain(receipt.student_name);
    expect(parsed.body.textContent).toContain(receipt.reference_id);
    expect(parsed.body.textContent).toContain(status);
    expect(parsed.body.textContent).not.toContain('Confirmed');
    expect(parsed.body.textContent).toContain('Gross amountGHS 0.00');
    expect(parsed.body.textContent).toContain('Applied amountGHS 0.00');
    expect(parsed.body.textContent).toContain('Convenience feeGHS 2.00');
    expect(parsed.body.textContent).toContain('Provider feeGHS 3.00');
    expect(popup.print).not.toHaveBeenCalled();
    expect(popup.document.close).toHaveBeenCalled();
    popup.addEventListener.mock.calls[0][1]();
    expect(popup.focus).toHaveBeenCalledTimes(1);
    expect(popup.print).toHaveBeenCalledTimes(1);
  });

  it('explains a blocked popup without throwing', async () => {
    vi.spyOn(window, 'open').mockReturnValue(null);
    render(<PaymentReceipts />);
    fireEvent.click(await screen.findByRole('button', { name: 'Print receipt R001' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Allow popups');
  });

  it('prints once when the popup is already loaded after closing the document', async () => {
    const popup = { document: { open: vi.fn(), write: vi.fn(), close: vi.fn(), readyState: 'complete' }, addEventListener: vi.fn(), focus: vi.fn(), print: vi.fn() };
    vi.spyOn(window, 'open').mockReturnValue(popup);
    render(<PaymentReceipts />);
    fireEvent.click(await screen.findByRole('button', { name: 'Print receipt R001' }));
    expect(popup.print).toHaveBeenCalledTimes(1);
    popup.addEventListener.mock.calls[0][1]();
    expect(popup.print).toHaveBeenCalledTimes(1);
  });

  it('paginates and resets the offset when searching', async () => {
    render(<PaymentReceipts />);
    await screen.findByText(receipt.student_name);
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    await waitFor(() => expect(axios.get).toHaveBeenLastCalledWith('/api/finance/receipts', expect.objectContaining({ params: { q: '', offset: 50, limit: 50 } })));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Previous page' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Previous page' }));
    await waitFor(() => expect(axios.get).toHaveBeenLastCalledWith('/api/finance/receipts', expect.objectContaining({ params: { q: '', offset: 0, limit: 50 } })));
    fireEvent.change(screen.getByRole('textbox', { name: 'Search receipts' }), { target: { value: ' Ama ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(axios.get).toHaveBeenLastCalledWith('/api/finance/receipts', expect.objectContaining({ params: { q: 'Ama', offset: 0, limit: 50 } })));
  });

  it('shows request errors and allows retry', async () => {
    axios.get.mockRejectedValueOnce(new Error('Offline'));
    render(<PaymentReceipts />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText(receipt.student_name)).toBeInTheDocument();
  });
});