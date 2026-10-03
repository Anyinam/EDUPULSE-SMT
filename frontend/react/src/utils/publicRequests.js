const authExemptPrefixes = [
  '/api/login',
  '/api/register',
  '/api/2fa/',
  '/api/forgot-password',
  '/api/reset-password',
  '/api/public/',
];

export function isAuthExemptRequest(url) {
  const pathname = new URL(String(url || ''), 'http://edupulse.invalid').pathname;
  return pathname === '/api/subscription/plans'
    || authExemptPrefixes.some((prefix) => pathname.startsWith(prefix));
}