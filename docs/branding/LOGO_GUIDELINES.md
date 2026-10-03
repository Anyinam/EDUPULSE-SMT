# EduPulse SMT Logo

## Current Brand Mark

The official platform mark is the owner-supplied black-and-white circular EDUPULSE SMT / GUAN seal, stored at `frontend/react/public/images/edupulse-smt-logo.jpg`. Preserve the original artwork, lettering, proportions, and colors. Do not redraw or recolor it.

The shared React Logo component removes only surrounding blank margins for display and retains a white background for contrast. Public header/footer use the 48px size. The browser favicon and touch icon reference the same original image. School-uploaded branding remains separate.

User dashboards use the same supplied seal at 64px in the shared sidebar for every staff role. The school's name and verification badge remain alongside it; the platform mark is not replaced by the retired colored artwork.

The sections below describe the retired Neural Learn artwork and are retained as historical reference, not current implementation instructions.

## Historical Neural Learn Design

## Overview

The **Neural Learn** logo is the official brand identity for EduPulse SMT. It represents AI-enhanced learning through a visual combination of:
- **Brain imagery** - Representing intelligence, learning, and knowledge
- **Pulse circuitry** - Symbolizing real-time engagement and vitality
- **Directional arrow** - Indicating growth and forward momentum

### Design Philosophy

**Color Scheme:**
- **Purple (#667eea)** - Brain hemispheres (intellect, wisdom, trust)
- **Red (#ff6b6b)** - Pulse/circuit (energy, vitality, urgency)
- **Cyan (#00d4ff)** - Learning indicator (growth, technology, innovation)

**Key Characteristics:**
- ✓ Scalable vector-based design
- ✓ Works on all screen sizes (32px to 512px+)
- ✓ Includes light, dark, and monochrome variations
- ✓ Professional and modern aesthetic
- ✓ Accessible and recognizable

---

## Logo Files

### In Frontend Repository

```
frontend/react/public/
├── logo.svg                    # Main logo (default colors, 200x200)
├── logo-dark.svg              # Dark theme variant
├── logo-monochrome.svg        # Black & white for printing
├── favicon-192.svg            # High-res favicon (192x192)
└── components/
    └── Logo.jsx               # React component (flexible, reusable)
```

### Exported for External Use

These files are ready for:
- 📄 Business cards and letterheads
- 🎨 Marketing materials
- 📱 App icons and favicons
- 📊 Presentations and documents
- 🖨 Print materials (300 DPI ready)

---

## Usage in React

### Basic Logo Component

```jsx
import { Logo, LogoWithText, LogoIcon } from '@/components/Logo';

// Icon only (small)
<LogoIcon size="sm" />

// Icon only (large)
<LogoIcon size="lg" />

// Logo with text
<LogoWithText size="md" variant="default" />

// Full customization
<Logo 
  size="xl" 
  variant="dark"
  showText={true}
  className="my-custom-class"
/>
```

### Sizes Available

- `xs` - 24px (for inline icons)
- `sm` - 32px (sidebar elements)
- `md` - 48px (default headers)
- `lg` - 64px (large headers)
- `xl` - 96px (hero sections)
- `2xl` - 128px (jumbo displays)

### Color Variants

- `default` - Full color (recommended for most use cases)
- `dark` - Dark theme optimized
- `light` - Light theme optimized
- `monochrome` - Black & white (printing)
- `gradient` - Gradient effect (eye-catching)

### Examples

**Navbar Logo:**
```jsx
<nav className="flex items-center gap-4">
  <LogoWithText size="md" variant="default" />
  <span>Navigation Items...</span>
</nav>
```

**Favicon (HTML Head):**
```html
<link rel="icon" href="/favicon-192.svg" type="image/svg+xml" />
```

**Dashboard Header:**
```jsx
<header className="bg-gradient-to-r from-purple-600 to-purple-800 p-4">
  <Logo size="lg" variant="light" showText={true} />
</header>
```

**Loading Spinner with Logo:**
```jsx
<div className="flex flex-col items-center justify-center min-h-screen">
  <div className="animate-spin">
    <Logo size="xl" variant="default" />
  </div>
  <p className="mt-4 text-gray-600">Loading your classroom...</p>
</div>
```

---

## Integration Checklist

- [ ] Add favicon to public folder
- [ ] Update `index.html` with favicon reference
- [ ] Import Logo component in main App/Layout
- [ ] Replace existing graduate hat icon with Logo component
- [ ] Test all size and color variants
- [ ] Update navbar/header with new logo
- [ ] Test responsive behavior on mobile
- [ ] Add logo to authentication pages
- [ ] Update 404/error pages with logo
- [ ] Test in light and dark mode

---

## Export Instructions

### For Print (300 DPI)
1. Use `logo-monochrome.svg`
2. Scale to desired size (e.g., 1x1 inch @ 300 DPI = 300x300px)
3. Export as high-quality PNG or PDF
4. Send to print vendor

### For Web (72 DPI)
1. Use `logo.svg` or `logo-dark.svg`
2. Scale as needed (typically 48px-96px for headers)
3. Embed directly or use as image
4. Component auto-scales with size prop

### For Social Media
1. Use `logo.svg` (default colors)
2. Export sizes: 1200x1200px (header), 400x400px (thumbnail)
3. Add 20px padding on all sides
4. Save as PNG with transparency

### For Apps/Icons
1. Use `favicon-192.svg`
2. Export in sizes: 192x192, 256x256, 512x512
3. Include rounded corner variants if needed
4. Test at small sizes (16px-32px)

---

## Brand Guidelines

### Do's ✓
- ✓ Use consistent color palette
- ✓ Maintain minimum clear space (20px around logo)
- ✓ Scale proportionally
- ✓ Use appropriate variant for background color
- ✓ Ensure minimum 32px display size

### Don'ts ✗
- ✗ Don't rotate or skew the logo
- ✗ Don't change the color scheme arbitrarily
- ✗ Don't add drop shadows or distortions
- ✗ Don't display smaller than 32px without testing
- ✗ Don't use the colored version on colored backgrounds without contrast testing

---

## Color Specifications

### Primary Colors

| Element | Color | Hex | RGB | Usage |
|---------|-------|-----|-----|-------|
| Brain | Purple | #667eea | 102, 126, 234 | Main structure |
| Pulse | Red | #ff6b6b | 255, 107, 107 | Energy/dynamics |
| Indicator | Cyan | #00d4ff | 0, 212, 255 | Growth/innovation |

### Acceptable Backgrounds

| Variant | Light BG | Dark BG | Gradient BG |
|---------|----------|---------|-------------|
| Default | ✓ Use | ✗ Use Dark | ✓ Use |
| Dark | ✗ Use | ✓ Use | ⚠ Test |
| Monochrome | ✓ Use | ✓ Use | ⚠ Test |

---

## Accessibility

The Logo component includes:
- `aria-label` for screen readers
- High contrast ratio (WCAG AA compliant)
- Clear semantic structure
- Scales gracefully without distortion
- Readable at all sizes

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Feb 21, 2026 | Initial release - Neural Learn logo design |
| | | Created component, variants, and documentation |

---

## Support

For logo customization or additional variants:
1. Edit `frontend/react/src/components/Logo.jsx`
2. Add new color scheme to `colorSchemes` object
3. Update documentation
4. Test across all sizes and contexts

---

**Last Updated:** February 21, 2026  
**Status:** Ready for Production Use ✓
