import React from 'react';
import { render, screen } from '@testing-library/react';
import SchoolVerifiedBadge from '../SchoolVerifiedBadge';

describe('SchoolVerifiedBadge', () => {
  it('renders the visible badge for verified schools', () => {
    render(<SchoolVerifiedBadge verified />);
    expect(screen.getByText(/verified school/i)).toBeInTheDocument();
  });

  it('does not render for unverified schools', () => {
    const { container } = render(<SchoolVerifiedBadge verified={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});