import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import axios from 'axios';
import Layout from '../Layout';

vi.mock('axios');
vi.mock('../../hooks/useBranding', () => ({ useBranding: () => ({ branding: { name: 'Test School', is_verified: true } }) }));
vi.mock('../../hooks/useSubscription', () => ({ default: () => ({ hasFeature: () => true, subscription: { plan: 'Basic' }, loading: false, error: null, plan: 'Basic' }) }));

describe('dashboard official logo', () => {
  beforeEach(() => {
    axios.get.mockResolvedValue({ data: {} });
    localStorage.setItem('school_id', 'TEST-LOGO');
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it.each(['proprietor', 'headmaster', 'teacher', 'homeroom', 'finance', 'inventory_manager', 'kitchen'])('uses the supplied seal in the %s dashboard', role => {
    localStorage.setItem('role', role);
    localStorage.setItem('roles', JSON.stringify([role]));
    render(<MemoryRouter initialEntries={[`/${role}`]}><Layout /></MemoryRouter>);
    const logo = screen.getByRole('img', { name: 'EduPulse SMT logo' });
    const image = logo.querySelector('img');
    expect(image).toHaveAttribute('src', '/images/edupulse-smt-logo.jpg');
    expect(image.parentElement).toHaveStyle({ width: '64px', height: '64px', backgroundColor: '#fff' });
    expect(logo.querySelector('svg')).toBeNull();
    expect(screen.getByRole('heading', { name: 'Test School' })).toBeInTheDocument();
  });
});