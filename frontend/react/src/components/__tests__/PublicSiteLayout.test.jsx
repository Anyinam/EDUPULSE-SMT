import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PublicSiteLayout from '../PublicSiteLayout';

describe('public homepage finishing details', () => {
  const showLayout = () => render(<MemoryRouter><PublicSiteLayout><h1>EduPulse SMT</h1></PublicSiteLayout></MemoryRouter>);

  it('closes mobile navigation with Escape and restores focus', () => {
    showLayout();
    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.getByRole('button', { name: 'Open menu' })).toHaveFocus();
    expect(screen.getByRole('button', { name: 'Open menu' })).toHaveAttribute('aria-expanded', 'false');
  });

  it.each(['Terms of Service', 'Privacy Policy', 'Data Retention Policy'])('opens %s from the homepage footer and closes with Escape', label => {
    showLayout();
    const trigger = within(screen.getByRole('contentinfo')).getByRole('button', { name: label });
    fireEvent.click(trigger);
    expect(screen.getByRole('dialog', { name: label })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});