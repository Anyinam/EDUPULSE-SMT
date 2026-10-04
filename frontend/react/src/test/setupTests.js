import '@testing-library/jest-dom/vitest';

// Subscription entitlements are cached in sessionStorage; isolate each test.
beforeEach(() => {
  sessionStorage.clear();
  globalThis.__edupulseSubscriptionRequests?.clear();
});
