import React from 'react';

/**
 * EduPulse Logo Component - Neural Learn Design
 * Reusable logo with configurable size and color scheme
 */

export const Logo = ({ 
  size = 'md', 
  variant = 'default',
  showText = false,
  className = '',
  ariaLabel = 'EduPulse Logo'
}) => {
  const sizes = {
    xs: 24,
    sm: 32,
    md: 48,
    lg: 64,
    xl: 96,
    '2xl': 128
  };

  const colorSchemes = {
    default: {
      brain: '#667eea',
      pulse: '#ff6b6b',
      indicator: '#00d4ff'
    },
    dark: {
      brain: '#7986cb',
      pulse: '#ff5252',
      indicator: '#4dd0e1'
    },
    light: {
      brain: '#5e58c2',
      pulse: '#f44336',
      indicator: '#00d4ff'
    },
    monochrome: {
      brain: '#333333',
      pulse: '#666666',
      indicator: '#999999'
    },
    gradient: {
      brain: 'url(#gradientBrain)',
      pulse: 'url(#gradientPulse)',
      indicator: '#00d4ff'
    }
  };

  const colors = colorSchemes[variant] || colorSchemes.default;
  const viewSize = sizes[size] || sizes.md;

  return (
    <div 
      className={`inline-flex items-center gap-2 ${className}`}
      role="img"
      aria-label={ariaLabel}
    >
      <svg
        viewBox="0 0 200 200"
        width={viewSize}
        height={viewSize}
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0"
      >
        {variant === 'gradient' && (
          <defs>
            <linearGradient id="gradientBrain" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#667eea" />
              <stop offset="100%" stopColor="#764ba2" />
            </linearGradient>
            <linearGradient id="gradientPulse" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#ff6b6b" />
              <stop offset="100%" stopColor="#ff1744" />
            </linearGradient>
          </defs>
        )}

        {/* Brain outline - left hemisphere */}
        <circle
          cx="70"
          cy="80"
          r="20"
          stroke={colors.brain}
          strokeWidth="2.5"
          fill="none"
        />

        {/* Brain outline - right hemisphere */}
        <circle
          cx="130"
          cy="80"
          r="20"
          stroke={colors.brain}
          strokeWidth="2.5"
          fill="none"
        />

        {/* Brain outline - connector */}
        <path
          d="M 75 95 Q 100 120 125 95"
          stroke={colors.brain}
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
        />

        {/* Pulse/circuit lines */}
        <path
          d="M 70 65 L 70 50 L 130 50 L 130 65"
          stroke={colors.pulse}
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
        />

        {/* Pulse circuit endpoints */}
        <circle cx="70" cy="50" r="3" fill={colors.pulse} />
        <circle cx="130" cy="50" r="3" fill={colors.pulse} />

        {/* Learning indicator arrow */}
        <path
          d="M 100 130 L 100 150 L 90 140 M 100 150 L 110 140"
          stroke={colors.indicator}
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      {showText && (
        <span className="font-bold text-lg tracking-wider">
          EduPulse
        </span>
      )}
    </div>
  );
};

/**
 * Logo with Text - for headers and branding
 */
export const LogoWithText = ({ size = 'md', variant = 'default' }) => {
  return <Logo size={size} variant={variant} showText ariaLabel="EduPulse - Smart Learning Platform" />;
};

/**
 * Icon-only logo - for favicons and compact displays
 */
export const LogoIcon = ({ size = 'sm', variant = 'default' }) => {
  return <Logo size={size} variant={variant} />;
};

/**
 * Static SVG export - for use in non-React environments
 */
export const getLogoSVG = (variant = 'default', width = 200, height = 200) => {
  const colorSchemes = {
    default: { brain: '#667eea', pulse: '#ff6b6b', indicator: '#00d4ff' },
    dark: { brain: '#7986cb', pulse: '#ff5252', indicator: '#4dd0e1' },
    light: { brain: '#5e58c2', pulse: '#f44336', indicator: '#00d4ff' },
    monochrome: { brain: '#333333', pulse: '#666666', indicator: '#999999' }
  };

  const colors = colorSchemes[variant] || colorSchemes.default;

  return `<svg viewBox="0 0 200 200" width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
    <circle cx="70" cy="80" r="20" stroke="${colors.brain}" stroke-width="2.5" fill="none"/>
    <circle cx="130" cy="80" r="20" stroke="${colors.brain}" stroke-width="2.5" fill="none"/>
    <path d="M 75 95 Q 100 120 125 95" stroke="${colors.brain}" stroke-width="2.5" fill="none" stroke-linecap="round"/>
    <path d="M 70 65 L 70 50 L 130 50 L 130 65" stroke="${colors.pulse}" stroke-width="2.5" fill="none" stroke-linecap="round"/>
    <circle cx="70" cy="50" r="3" fill="${colors.pulse}"/>
    <circle cx="130" cy="50" r="3" fill="${colors.pulse}"/>
    <path d="M 100 130 L 100 150 L 90 140 M 100 150 L 110 140" stroke="${colors.indicator}" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;
};

export default Logo;
