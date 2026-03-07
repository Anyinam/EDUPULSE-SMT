# 🚀 Neural Learn Logo Integration Guide

## Quick Start (5 minutes)

### Step 1: Logo Files Created ✓

The following files are ready in your repo:

```
✓ frontend/react/src/components/Logo.jsx       (React component)
✓ frontend/react/public/logo.svg               (Main logo)
✓ frontend/react/public/logo-dark.svg          (Dark variant)
✓ frontend/react/public/logo-monochrome.svg    (Print version)
✓ frontend/react/public/favicon-192.svg        (Favicon)
✓ LOGO_GUIDELINES.md                            (Full documentation)
```

### Step 2: Update HTML Favicon

Edit `frontend/react/public/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <!-- Add this line for favicon -->
    <link rel="icon" href="%PUBLIC_URL%/favicon-192.svg" type="image/svg+xml" />
    
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#667eea" />
    <title>EduPulse - Smart Learning Platform</title>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
```

### Step 3: Update App Navigation

In your main App or Navigation component:

**Before (with graduate hat):**
```jsx
// Old code
<img src="/graduate-hat.png" alt="EduPulse" className="h-8" />
```

**After (with new Neural Learn logo):**
```jsx
import { Logo } from '@/components/Logo';

// In your navbar/header
<div className="flex items-center gap-3">
  <Logo size="md" variant="default" />
  <h1 className="text-xl font-bold">EduPulse</h1>
</div>
```

### Step 4: Test Across Layouts

**Navbar (High contrast dark background):**
```jsx
<nav className="bg-gradient-to-r from-indigo-600 to-purple-700">
  <div className="flex items-center gap-4 px-6 py-4">
    <Logo size="md" variant="default" showText={true} />
    {/* Navigation items */}
  </div>
</nav>
```

**Hero Section (Full size):**
```jsx
<section className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-blue-50 to-purple-50">
  <Logo size="2xl" variant="default" />
  <h1 className="mt-6 text-4xl font-bold text-gray-900">
    Welcome to EduPulse
  </h1>
  <p className="mt-2 text-lg text-gray-600">
    Intelligent Lesson Planning & Progress Tracking
  </p>
</section>
```

**Footer (Smaller size):**
```jsx
<footer className="bg-gray-900 text-white py-8">
  <div className="flex items-center gap-2 mb-4">
    <Logo size="sm" variant="light" />
    <span className="text-sm">© 2026 EduPulse. All rights reserved.</span>
  </div>
</footer>
```

---

## Color Variants Guide

### Use Case Reference

| Where | Size | Variant | Reason |
|-------|------|---------|--------|
| Navbar on dark | md | default | High contrast |
| Light background | md-lg | light | Vibrant on light |
| Dark background | md-lg | dark | Readable on dark |
| Print materials | lg-xl | monochrome | Professional B&W |
| Favicon | xs-sm | default | Recognizable small |
| Mobile header | xs | default | Space-saving |
| Desktop banner | 2xl | gradient | Eye-catching |

---

## Component Usage Examples

### 1. **Sidebar Logo**
```jsx
<aside className="w-64 bg-white shadow-lg">
  <div className="p-4 border-b">
    <Logo size="md" variant="default" showText={true} />
  </div>
</aside>
```

### 2. **Loading Indicator**
```jsx
export const LoadingScreen = () => (
  <div className="flex flex-col items-center justify-center min-h-screen gap-4">
    <div className="animate-spin duration-3000">
      <Logo size="xl" variant="default" />
    </div>
    <p>Loading your platform...</p>
  </div>
);
```

### 3. **Login Page**
```jsx
export const LoginPage = () => (
  <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-500 to-purple-600">
    <div className="bg-white rounded-lg shadow-xl p-8 w-96">
      <div className="flex justify-center mb-6">
        <Logo size="lg" variant="default" />
      </div>
      <h2 className="text-2xl font-bold text-center mb-6">Welcome Back</h2>
      {/* Login form */}
    </div>
  </div>
);
```

### 4. **Error Page**
```jsx
export const NotFound = () => (
  <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-gray-50 to-gray-100">
    <Logo size="xl" variant="light" />
    <h1 className="mt-6 text-4xl font-bold">404</h1>
    <p className="mt-2 text-xl text-gray-600">Page not found</p>
    <Link to="/" className="mt-6 px-6 py-2 bg-purple-600 text-white rounded-lg">
      Go Home
    </Link>
  </div>
);
```

---

## Testing Checklist

- [ ] Favicon displays in browser tab
- [ ] Logo renders at all sizes (xs, sm, md, lg, xl, 2xl)
- [ ] All color variants display correctly
- [ ] Text variant works with showText prop
- [ ] Logo scales responsively on mobile
- [ ] No console errors when importing
- [ ] Works in light mode
- [ ] Works in dark mode
- [ ] Accessible to screen readers (aria-label present)
- [ ] No distortion at extreme sizes

---

## Dark Mode Implementation

If using Tailwind dark mode, update your component:

```jsx
export const ResponsiveLogo = () => {
  const isDark = useTheme().isDark; // or use Tailwind's dark: class
  
  return (
    <Logo 
      size="md" 
      variant={isDark ? "dark" : "default"} 
    />
  );
};
```

Or in JSX directly:
```jsx
<div className="dark:bg-gray-900 bg-white">
  <Logo variant="default" className="dark:hidden" />
  <Logo variant="dark" className="hidden dark:block" />
</div>
```

---

## Export For External Use

### Generate PNG files:
```bash
# Convert SVG to PNG (requires Inkscape or similar)
inkscape frontend/react/public/logo.svg -o logo-default.png -h 512
inkscape frontend/react/public/logo-dark.svg -o logo-dark.png -h 512
inkscape frontend/react/public/logo-monochrome.svg -o logo-monochrome.png -h 512
```

### Or use online converters:
- **Convertio.co** - SVG to PNG converter
- **Zamzar** - Batch conversion tool
- **CloudConvert** - Professional conversions

---

## Next Steps

1. ✓ Files created and ready
2. → **Update index.html favicon** (5 min)
3. → **Import Logo in main App** (2 min)
4. → **Replace old logo usage** (10 min)
5. → **Test all pages** (15 min)
6. → **Deploy to production** (1 min)

**Total time: ~30 minutes**

---

## Support Resources

- Full guidelines: [LOGO_GUIDELINES.md](LOGO_GUIDELINES.md)
- Component code: [frontend/react/src/components/Logo.jsx](frontend/react/src/components/Logo.jsx)
- SVG files: [frontend/react/public/](frontend/react/public/)

---

**Logo Status:** ✅ Ready for Integration  
**Last Updated:** February 21, 2026
