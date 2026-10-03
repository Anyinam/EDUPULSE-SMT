import React from 'react';

const logoSource = '/images/edupulse-smt-logo.jpg';
const sizes = { xs: 24, sm: 32, md: 48, lg: 64, xl: 96, '2xl': 128 };

export const Logo = ({
  size = 'md',
  showText = false,
  className = '',
  ariaLabel = 'EduPulse Logo'
}) => {
  const viewSize = sizes[size] || sizes.md;

  return (
    <div
      className={`inline-flex items-center gap-2 ${className}`}
      role="img"
      aria-label={ariaLabel}
    >
      <span
        aria-hidden="true"
        style={{
          display: 'inline-block',
          position: 'relative',
          width: viewSize,
          height: viewSize,
          flexShrink: 0,
          overflow: 'hidden',
          borderRadius: '50%',
          backgroundColor: '#fff'
        }}
      >
        <img
          src={logoSource}
          alt=""
          aria-hidden="true"
          loading="eager"
          width={1280}
          height={1280}
          style={{
            position: 'absolute',
            width: '150%',
            height: '150%',
            maxWidth: 'none',
            left: '-25%',
            top: '-25%'
          }}
        />
      </span>
      {showText && (
        <span className="font-bold text-lg tracking-wider">EduPulse</span>
      )}
    </div>
  );
};

export const LogoWithText = ({ size = 'md', variant = 'default' }) => (
  <Logo size={size} variant={variant} showText ariaLabel="EduPulse - Smart Learning Platform" />
);

export const LogoIcon = ({ size = 'sm', variant = 'default' }) => (
  <Logo size={size} variant={variant} />
);

export const getLogoSVG = (...args) => {
  const [, width = 200, height = 200] = args;
  return `<svg viewBox="0 0 1280 1280" width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
    <image href="${logoSource}" x="-320" y="-320" width="1920" height="1920" />
  </svg>`;
};

export default Logo;
