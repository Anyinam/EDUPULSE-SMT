import { isAuthExemptRequest } from '../publicRequests';

describe('public pricing request authentication', () => {
  it.each(['/api/subscription/plans', '/api/subscription/plans?locale=en', 'https://edupulsesmt.com/api/subscription/plans'])('does not reject public plans because of a stale session: %s', (url) => {
    expect(isAuthExemptRequest(url)).toBe(true);
  });

  it.each(['/api/school/subscription', '/api/subscription/plans/private', '/api/finance/dashboard'])('keeps private requests subject to authentication: %s', (url) => {
    expect(isAuthExemptRequest(url)).toBe(false);
  });
});