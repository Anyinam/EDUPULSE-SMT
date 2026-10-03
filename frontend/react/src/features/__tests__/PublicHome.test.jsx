import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PublicHome from '../PublicHome';

describe('EduPulse public homepage', () => {
  const showHome = () => render(<MemoryRouter><PublicHome /></MemoryRouter>);

  it('presents the brand and school operations without a signed-in session', () => {
    showHome();
    expect(screen.getByRole('heading', { level: 1, name: 'EduPulse SMT' })).toBeInTheDocument();
    expect(screen.getByText('Receipts on every plan')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Ghanaian students reading together/ })).toHaveAttribute('src', '/images/ghana-classroom.jpg');
  });

  it('provides working public account and pricing links', () => {
    showHome();
    const navigation = within(screen.getByRole('navigation', { name: 'Main navigation' }));
    expect(navigation.getByRole('link', { name: 'Why EduPulse SMT' })).toHaveAttribute('href', '/#why-edupulse');
    expect(navigation.getByRole('link', { name: 'Pricing' })).toHaveAttribute('href', '/pricing');
    expect(navigation.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login');
    expect(navigation.getByRole('link', { name: /Create free account/ })).toHaveAttribute('href', '/register');
  });

  it('preserves word spacing when responsive line breaks disappear', () => {
    showHome();
    for (const text of [
      'Make the next school day a little simpler.',
      'From the first admission to the final report.',
      'A school runs on people. Give them a better system.',
      'The essentials. Working together.',
    ]) {
      expect(screen.getByRole('heading', { name: text }).textContent.replace(/\s+/g, ' ')).toBe(text);
    }
  });

  it('opens and closes the mobile navigation after selecting a destination', () => {
    showHome();
    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }));
    expect(screen.getByRole('button', { name: 'Close menu' })).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Main navigation' })).getByRole('link', { name: 'Pricing' }));
    expect(screen.getByRole('button', { name: 'Open menu' })).toHaveAttribute('aria-expanded', 'false');
  });
});