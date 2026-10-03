import React from 'react';
import { render, screen } from '@testing-library/react';
import Logo, { Logo as NamedLogo, LogoIcon, LogoWithText, getLogoSVG } from './Logo';

const logoSource = '/images/edupulse-smt-logo.jpg';

describe('supplied EduPulse logo', () => {
  it('uses the exact bitmap with one accessible label and no vector redraw', () => {
    const { container } = render(<Logo ariaLabel="EduPulse SMT" className="brand-logo" />);
    expect(Logo).toBe(NamedLogo);
    expect(screen.getByRole('img', { name: 'EduPulse SMT' })).toHaveClass('brand-logo');
    expect(screen.getAllByRole('img')).toHaveLength(1);
    const image = container.querySelector('img');
    expect(image).toHaveAttribute('src', logoSource);
    expect(image).toHaveAttribute('alt', '');
    expect(image).toHaveAttribute('aria-hidden', 'true');
    expect(image).toHaveAttribute('loading', 'eager');
    expect(image).toHaveAttribute('width', '1280');
    expect(image).toHaveAttribute('height', '1280');
    expect(container.querySelector('svg')).toBeNull();
    expect(screen.queryByText('EduPulse')).not.toBeInTheDocument();
  });

  it.each([['xs', 24], ['sm', 32], ['md', 48], ['lg', 64], ['xl', 96], ['2xl', 128], ['unknown', 48]])(
    'keeps size %s fixed at %ipx with a padded circular crop',
    (size, pixels) => {
      const { container } = render(<Logo size={size} />);
      const image = container.querySelector('img');
      expect(image.parentElement).toHaveStyle({
        width: `${pixels}px`, height: `${pixels}px`, flexShrink: 0,
        overflow: 'hidden', borderRadius: '50%', backgroundColor: '#fff', position: 'relative'
      });
      expect(image).toHaveStyle({
        width: '150%', height: '150%', maxWidth: 'none',
        position: 'absolute', left: '-25%', top: '-25%'
      });
      const ringStart = (222 / 1280) * 1.5 - 0.25;
      const ringEnd = (1058 / 1280) * 1.5 - 0.25;
      expect(ringStart).toBeGreaterThan(0);
      expect(ringEnd).toBeLessThan(1);
    }
  );

  it.each(['default', 'dark', 'light', 'monochrome', 'gradient'])('accepts %s without recoloring', (variant) => {
    const { container } = render(<Logo variant={variant} />);
    const image = container.querySelector('img');
    expect(image).toHaveAttribute('src', logoSource);
    expect(image.style.filter).toBe('');
    expect(container.querySelector('[filter], svg')).toBeNull();
  });

  it('preserves the text and icon exports and their defaults', () => {
    const { container, rerender } = render(<LogoWithText variant="dark" />);
    expect(screen.getByText('EduPulse')).toBeInTheDocument();
    expect(screen.getByRole('img')).toHaveAttribute('aria-label', 'EduPulse - Smart Learning Platform');
    expect(container.querySelector('img').parentElement).toHaveStyle({ width: '48px', height: '48px' });
    rerender(<LogoIcon variant="light" />);
    expect(screen.queryByText('EduPulse')).not.toBeInTheDocument();
    expect(container.querySelector('img').parentElement).toHaveStyle({ width: '32px', height: '32px' });
  });

  it('keeps the legacy SVG helper as a bitmap reference with requested dimensions', () => {
    for (const variant of ['default', 'dark', 'monochrome', 'gradient']) {
      const svg = new DOMParser().parseFromString(getLogoSVG(variant, 64, 48), 'image/svg+xml');
      expect(svg.querySelector('parsererror')).toBeNull();
      expect(svg.documentElement.getAttribute('width')).toBe('64');
      expect(svg.documentElement.getAttribute('height')).toBe('48');
      expect(svg.querySelector('image').getAttribute('href')).toBe(logoSource);
      expect(svg.querySelector('path, circle, filter, linearGradient')).toBeNull();
    }
    expect(getLogoSVG()).toContain('width="200" height="200"');
  });
});