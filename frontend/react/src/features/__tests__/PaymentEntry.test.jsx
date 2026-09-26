import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import PaymentEntry from '../PaymentEntry';

vi.mock('axios');

describe('PaymentEntry', () => {
  beforeEach(() => {
    localStorage.setItem('role', 'finance');
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');
    axios.post.mockResolvedValue({ data: { message: 'Recorded' } });
    vi.spyOn(window, 'alert').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('supports one-character lookup and keeps daily feeding mode ready', async () => {
    const students = [
      {
        id: 7,
        name: 'Ama Mensah',
        student_code: 'S007',
        current_class: 'Primary 2',
        feeding_daily_fee: 5,
      },
      {
        id: 8,
        name: 'Kwame Asare',
        student_code: 'S008',
        current_class: 'Primary 3',
        feeding_daily_fee: 6,
      },
    ];

    render(<PaymentEntry students={students} />);

    fireEvent.change(screen.getByPlaceholderText(/search name, initials, code, or scan/i), {
      target: { value: 'a' },
    });
    fireEvent.click(screen.getByRole('button', { name: /ama mensah/i }));
    fireEvent.click(screen.getByRole('button', { name: /daily feeding/i }));

    expect(screen.getByDisplayValue('5')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /record feeding/i }));

    await waitFor(() => expect(axios.post).toHaveBeenCalledTimes(1));
    expect(axios.post.mock.calls[0][1]).toMatchObject({
      student_id: 7,
      amount: '5',
      type: 'Feeding',
      method: 'Cash',
      payment_category: { frequency: 'Daily' },
    });
    expect(screen.getByRole('button', { name: /record feeding/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/search name, initials, code, or scan/i)).toHaveValue('');
  });
});