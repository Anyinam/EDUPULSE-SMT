import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import StudentPaymentTracker from '../StudentPaymentTracker';
import useSubscription from '../../hooks/useSubscription';

vi.mock('axios');
vi.mock('../../hooks/useSubscription', () => ({ default: vi.fn() }));
vi.mock('../../hooks/useBranding', () => ({
  useBranding: () => ({ branding: {} }),
}));

describe('StudentPaymentTracker', () => {
  const deferred = () => {
    let resolve;
    let reject;
    const promise = new Promise((resolvePromise, rejectPromise) => {
      resolve = resolvePromise;
      reject = rejectPromise;
    });
    return { promise, resolve, reject };
  };

  const codesFor = (studentId, virtualRoute = null) => ({
    student_name: studentId === 1 ? 'Ama Mensah' : 'Yaw Owusu',
    student_code: `S00${studentId}`,
    payment_identity: { supports_fee_route_dvas: true },
    payment_codes: [{
      fee_type: 'Tuition',
      code: `S00${studentId}-T1`,
      base_amount: 120,
      virtual_route: virtualRoute,
    }],
  });

  beforeEach(() => {
    useSubscription.mockReturnValue({ plan: 'Basic', hasFeature: () => true });
    vi.stubGlobal('alert', vi.fn());
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');

    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
              parent_name: 'Kojo Mensah',
              parent_phone: '0240000000',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 120,
            terminal_report_fee: 10,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.reject({
          response: {
            data: {
              error: 'payment_collection_blocked',
              message: 'Parent payment collection is paused because this school is on Free Tier with 54 active students, above the 50-student limit.',
              effective_plan: 'Free Tier',
              active_students: 54,
              plan_limit: 50,
            },
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it('shows GET and preparation stages while history and the latest receipt remain available', async () => {
    const codesGet = deferred();
    const routePost = deferred();
    const defaultGet = axios.get.getMockImplementation();
    axios.get.mockImplementation((url) => {
      if (url === '/api/students/1/payment-codes') return codesGet.promise;
      if (url === '/api/students/1/payments') return Promise.resolve({ data: [{
        id: 9, payment_type: 'Tuition', amount: 40, status: 'Confirmed',
        date_paid: '2026-10-01', reference_id: 'HISTORY-AMA', method: 'Cash',
      }] });
      return defaultGet(url);
    });
    axios.post.mockReturnValue(routePost.promise);
    vi.stubGlobal('open', vi.fn());
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true, value: { writeText: vi.fn() },
    });

    render(<StudentPaymentTracker />);
    fireEvent.click(await screen.findByText('Ama Mensah'));
    expect(screen.getByRole('status')).toHaveTextContent('Loading payment instructions...');
    expect(await screen.findByRole('button', { name: /print latest receipt/i })).toBeEnabled();
    expect(screen.getAllByText(/40\.00/).length).toBeGreaterThan(0);

    await act(async () => codesGet.resolve({ data: codesFor(1) }));
    expect(screen.getByRole('status')).toHaveTextContent('Preparing tracked transfer accounts...');
    expect(screen.getByRole('button', { name: /print latest receipt/i })).toBeEnabled();
    expect(screen.queryByRole('button', { name: /print instructions|copy instructions/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/tracked transfer account ready/i)).not.toBeInTheDocument();
    expect(window.open).not.toHaveBeenCalled();
    expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
    expect(axios.post).toHaveBeenCalledTimes(1);

    await act(async () => routePost.resolve({ data: { virtual_route: {
      account_number: '1111111111', bank_name: 'Test bank', base_amount: 120, total_amount: 120,
    } } }));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getByText(/tracked transfer account ready/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /print instructions/i })).toBeEnabled();
    expect(axios.get.mock.calls.filter(([url]) => url.includes('/students/1/'))).toHaveLength(2);
    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(window.open).not.toHaveBeenCalled();
  });

  const readyRoute = { account_number: '2222222222', base_amount: 120, total_amount: 120 };
  const historicalPayment = {
    id: 9, payment_type: 'Tuition', amount: 40, status: 'Confirmed',
    date_paid: '2026-10-01', method: 'Cash',
  };
  const mockStudentReads = (responses, extraStudents = []) => {
    const defaultGet = axios.get.getMockImplementation();
    axios.get.mockImplementation((url) => {
      if (url === '/api/students') return Promise.resolve({ data: [
        { id: 1, name: 'Ama Mensah', student_code: 'S001', current_class: 'JHS 1' },
        { id: 2, name: 'Yaw Owusu', student_code: 'S002', current_class: 'JHS 2' },
        ...extraStudents,
      ] });
      if (responses[url]) return responses[url];
      return defaultGet(url);
    });
  };

  const marginPricing = {
    fee_model: 'gross_up_margin_v1', estimated_provider_fee_rate_pct: 1.95,
    estimated_provider_fee_flat: 0, platform_margin_rate_pct: 1, platform_fee_flat: 0,
    charge_parent_convenience_fee: true, platform_fee_label: 'Processing and EduPulse service fee',
  };
  const marginRoute = {
    fee_model: 'gross_up_margin_v1', bank_name: 'Test bank', account_number: '3333333333',
    base_amount: 25, total_amount: 25.76, convenience_fee_amount: 0.76,
    estimated_provider_fee_amount: 0.50, platform_fee_amount: 0.25, rounding_surplus_amount: 0.01,
  };
  const marginCodes = (route = marginRoute) => ({
    ...codesFor(1), fees_configuration: { tuition_transfer_pricing: marginPricing },
    payment_codes: [{ ...codesFor(1).payment_codes[0], ...marginRoute, virtual_route: route,
      payment_category: { fee_type: 'Tuition', installment_number: 1, installment_label: 'Installment 1' },
    }],
  });

  it.each(['old total', 'missing version', 'missing route', 'config version only'])(
    'refreshes %s before showing a ready gross-up account', async (scenario) => {
      const post = deferred();
      const route = scenario === 'missing route' ? null : {
        ...marginRoute,
        ...(scenario === 'old total' ? { total_amount: 25.49 } : { fee_model: undefined }),
      };
      const codes = marginCodes(route);
      if (scenario === 'config version only') delete codes.payment_codes[0].fee_model;
      mockStudentReads({ '/api/students/1/payment-codes': Promise.resolve({ data: codes }) });
      axios.post.mockReturnValue(post.promise);
      render(<StudentPaymentTracker />);
      fireEvent.click(await screen.findByText('Ama Mensah'));
      expect(await screen.findByText('Preparing tracked transfer accounts...')).toBeInTheDocument();
      expect(screen.queryByText(/25\.49|Account number:|tracked transfer account ready/i)).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /copy instructions|print instructions/i })).not.toBeInTheDocument();
      expect(axios.post).toHaveBeenCalledTimes(1);
      await act(async () => post.resolve({ data: { virtual_route: marginRoute } }));
      expect(screen.getByText('Transfer total: GH₵ 25.76')).toBeInTheDocument();
      expect(screen.getAllByText('Estimated processing fee: GH₵ 0.50').length).toBeGreaterThan(0);
      expect(screen.getAllByText('EduPulse service fee (1.00% of tuition): GH₵ 0.25').length).toBeGreaterThan(0);
      expect(screen.queryByText(/convenience fee: 1.95%/i)).not.toBeInTheDocument();
      expect(axios.post).toHaveBeenCalledTimes(1);
    }
  );

  it.each(['provider error', 'stale response'])(
    'hides a stale account after %s without retrying', async (scenario) => {
      mockStudentReads({ '/api/students/1/payment-codes': Promise.resolve({ data: marginCodes({
        ...marginRoute, total_amount: 25.49,
      }) }) });
      if (scenario === 'provider error') axios.post.mockRejectedValue(new Error('Unavailable'));
      else axios.post.mockResolvedValue({ data: { virtual_route: { ...marginRoute, fee_model: undefined } } });
      render(<StudentPaymentTracker />);
      fireEvent.click(await screen.findByText('Ama Mensah'));
      expect(await screen.findByText('Account preparation failed')).toBeInTheDocument();
      expect(screen.queryByText(/25\.49|3333333333|tracked transfer account ready/i)).not.toBeInTheDocument();
      expect(axios.post).toHaveBeenCalledTimes(1);
    }
  );

  it('waits for school pricing before accepting a legacy route when the codes omit pricing', async () => {
    const fees = deferred();
    const codes = marginCodes({ ...marginRoute, fee_model: undefined });
    delete codes.payment_codes[0].fee_model;
    delete codes.fees_configuration;
    const defaultGet = axios.get.getMockImplementation();
    axios.get.mockImplementation((url) => {
      if (url === '/api/school/fees') return fees.promise;
      if (url === '/api/students/1/payment-codes') return Promise.resolve({ data: codes });
      return defaultGet(url);
    });
    axios.post.mockResolvedValue({ data: { virtual_route: marginRoute } });
    render(<StudentPaymentTracker />);
    fireEvent.click(await screen.findByText('Ama Mensah'));
    expect(await screen.findByText('Preparing tracked transfer accounts...')).toBeInTheDocument();
    expect(screen.queryByText(/tracked transfer account ready/i)).not.toBeInTheDocument();
    expect(axios.post).not.toHaveBeenCalled();
    await act(async () => fees.resolve({ data: { tuition_transfer_pricing: marginPricing } }));
    expect(await screen.findByText('Transfer total: GH₵ 25.76')).toBeInTheDocument();
    expect(axios.post).toHaveBeenCalledTimes(1);
  });

  it('copies and prints exact server quotes with the specific installment account', async () => {
    const codes = marginCodes();
    codes.payment_codes.push({
      ...codes.payment_codes[0], code: 'S001-T2', base_amount: 75, total_amount: 77.26,
      estimated_provider_fee_amount: 1.51, platform_fee_amount: 0.75, rounding_surplus_amount: 0,
      virtual_route: { ...marginRoute, account_number: '4444444444', base_amount: 75, total_amount: 77.26,
        convenience_fee_amount: 2.26, estimated_provider_fee_amount: 1.51,
        platform_fee_amount: 0.75, rounding_surplus_amount: 0 },
      payment_category: { fee_type: 'Tuition', installment_number: 2, installment_label: 'Installment 2' },
    });
    codes.payment_codes.unshift({
      ...codes.payment_codes[1], code: 'S001-TUIT-FULL',
      virtual_route: { ...codes.payment_codes[1].virtual_route, account_number: '5555555555' },
      payment_category: { fee_type: 'Tuition', tuition_payment_option: 'full_remaining', payment_label: 'Full Remaining Tuition' },
    });
    mockStudentReads({ '/api/students/1/payment-codes': Promise.resolve({ data: codes }) });
    const writeText = vi.fn();
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    const printWindow = { document: { write: vi.fn(), close: vi.fn() }, focus: vi.fn(), print: vi.fn() };
    vi.stubGlobal('open', vi.fn(() => printWindow));
    render(<StudentPaymentTracker />);
    fireEvent.click(await screen.findByText('Ama Mensah'));
    fireEvent.click(await screen.findByRole('button', { name: /copy instructions/i }));
    expect(screen.getByText('Full Remaining Tuition')).toBeInTheDocument();
    const copy = writeText.mock.calls[0][0];
    expect(copy).toMatch(/Full Remaining Tuition:.*Account: 5555555555.*total GH₵ 77.26/);
    expect(copy).toMatch(/Installment 1:.*Account: 3333333333.*processing fee: GH₵ 0.50.*service fee \(1.00% of tuition\): GH₵ 0.25.*total GH₵ 25.76/);
    expect(copy).toMatch(/Installment 2:.*Account: 4444444444.*total GH₵ 77.26/);
    expect(copy).toMatch(/total convenience fee: GH₵ 0.76/i);
    expect(copy).not.toMatch(/convenience fee: 1.95%/i);
    fireEvent.click(screen.getByRole('button', { name: /print instructions/i }));
    const html = printWindow.document.write.mock.calls[0][0];
    expect(html).toMatch(/Full Remaining Tuition[\s\S]*Tracked Transfer Account Number:<\/strong> 5555555555[\s\S]*Transfer GH₵ 77.26 exactly/);
    expect(html).toMatch(/Installment 1[\s\S]*Tracked Transfer Account Number:<\/strong> 3333333333[\s\S]*Transfer GH₵ 25.76 exactly/);
    expect(html).toMatch(/Installment 2[\s\S]*Tracked Transfer Account Number:<\/strong> 4444444444[\s\S]*Transfer GH₵ 77.26 exactly/);
    expect(html).toContain('Estimated processing fee: GH₵ 0.50');
    expect(html).toContain('EduPulse service fee (1.00% of tuition): GH₵ 0.25');
    expect(html).toContain('Rounding adjustment: GH₵ 0.01');
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('does not provision for an old selection after delayed school pricing arrives', async () => {
    const fees = deferred();
    const defaultGet = axios.get.getMockImplementation();
    axios.get.mockImplementation((url) => url === '/api/school/fees' ? fees.promise : defaultGet(url));
    mockStudentReads({
      '/api/students/1/payment-codes': Promise.resolve({ data: marginCodes(null) }),
      '/api/students/2/payment-codes': Promise.resolve({ data: { ...codesFor(2), payment_codes: [] } }),
      '/api/students/2/payments': Promise.resolve({ data: [] }),
    });
    render(<StudentPaymentTracker />);
    fireEvent.click(await screen.findByText('Ama Mensah'));
    expect(await screen.findByText('Preparing tracked transfer accounts...')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Yaw Owusu'));
    await act(async () => fees.resolve({ data: { tuition_transfer_pricing: marginPricing } }));
    expect(axios.post).not.toHaveBeenCalled();
    expect(screen.queryByText(/S001-T1|3333333333/)).not.toBeInTheDocument();
  });

  it.each(['GET success', 'GET error', 'POST success', 'POST error'])(
    'ignores stale history and codes on %s without clearing the current loading stage', async (stage) => {
      const oldHistory = deferred();
      const oldCodes = deferred();
      const oldRoute = deferred();
      const newHistory = deferred();
      const newCodes = deferred();
      mockStudentReads({
        '/api/students/1/payments': oldHistory.promise,
        '/api/students/1/payment-codes': oldCodes.promise,
        '/api/students/2/payments': newHistory.promise,
        '/api/students/2/payment-codes': newCodes.promise,
      });
      axios.post.mockReturnValue(oldRoute.promise);
      render(<StudentPaymentTracker />);
      fireEvent.click(await screen.findByText('Ama Mensah'));
      if (stage.startsWith('POST')) {
        await act(async () => oldCodes.resolve({ data: codesFor(1) }));
        expect(screen.getByRole('status')).toHaveTextContent('Preparing tracked transfer accounts...');
      }
      fireEvent.click(screen.getByText('Yaw Owusu'));
      await act(async () => {
        oldHistory.resolve({ data: [historicalPayment] });
        const pending = stage.startsWith('POST') ? oldRoute : oldCodes;
        if (stage.endsWith('error')) {
          pending.reject({ response: { data: { message: 'OLD STUDENT ERROR' } } });
        } else {
          pending.resolve({ data: stage.startsWith('POST')
            ? { virtual_route: { ...readyRoute, account_number: '1111111111' } }
            : codesFor(1, readyRoute) });
        }
      });
      expect(screen.getByRole('status')).toHaveTextContent('Loading payment instructions...');
      expect(screen.queryByRole('button', { name: /print latest receipt/i })).not.toBeInTheDocument();
      expect(screen.queryByText(/S001-T1|1111111111|OLD STUDENT ERROR/)).not.toBeInTheDocument();
      expect(axios.post).toHaveBeenCalledTimes(stage.startsWith('POST') ? 1 : 0);
      await act(async () => {
        newHistory.resolve({ data: [] });
        newCodes.resolve({ data: codesFor(2, readyRoute) });
      });
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
      expect(screen.getByText(/Account number: 2222222222/)).toBeInTheDocument();
      expect(screen.queryByText(/S001-T1|1111111111/)).not.toBeInTheDocument();
    }
  );

  it('clears ready instructions and receipts immediately on selecting another student', async () => {
    const newCodes = deferred();
    mockStudentReads({
      '/api/students/1/payments': Promise.resolve({ data: [historicalPayment] }),
      '/api/students/1/payment-codes': Promise.resolve({ data: codesFor(1, readyRoute) }),
      '/api/students/2/payments': Promise.resolve({ data: [] }),
      '/api/students/2/payment-codes': newCodes.promise,
    });
    render(<StudentPaymentTracker />);
    fireEvent.click(await screen.findByText('Ama Mensah'));
    expect(await screen.findByRole('button', { name: /print instructions/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /print latest receipt/i })).toBeEnabled();
    fireEvent.click(screen.getByText('Yaw Owusu'));
    expect(screen.getByRole('status')).toHaveTextContent('Loading payment instructions...');
    expect(screen.queryByText(/S001-T1|Account number:/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /print instructions|copy instructions|print latest receipt/i })).not.toBeInTheDocument();
    await act(async () => newCodes.resolve({ data: codesFor(2, readyRoute) }));
  });

  it('ignores earlier responses when the same student is selected again', async () => {
    const oldCodes = deferred();
    const oldHistory = deferred();
    const newCodes = deferred();
    const newHistory = deferred();
    const defaultGet = axios.get.getMockImplementation();
    let codesCalls = 0;
    let historyCalls = 0;
    axios.get.mockImplementation((url) => {
      if (url === '/api/students/1/payment-codes') return ++codesCalls === 1 ? oldCodes.promise : newCodes.promise;
      if (url === '/api/students/1/payments') return ++historyCalls === 1 ? oldHistory.promise : newHistory.promise;
      return defaultGet(url);
    });
    render(<StudentPaymentTracker />);
    const studentButton = await screen.findByRole('button', { name: /Ama Mensah/ });
    fireEvent.click(studentButton);
    fireEvent.click(studentButton);
    await act(async () => {
      oldHistory.reject(new Error('Old history failure'));
      oldCodes.resolve({ data: codesFor(1) });
    });
    expect(screen.getByRole('status')).toHaveTextContent('Loading payment instructions...');
    expect(axios.post).not.toHaveBeenCalled();
    await act(async () => {
      newHistory.resolve({ data: [historicalPayment] });
      newCodes.resolve({ data: codesFor(1, readyRoute) });
    });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /print latest receipt/i })).toBeEnabled();
  });

  it('clears preparation status when a route POST fails without retrying', async () => {
    const routePost = deferred();
    mockStudentReads({ '/api/students/1/payment-codes': Promise.resolve({ data: codesFor(1) }) });
    axios.post.mockReturnValue(routePost.promise);
    render(<StudentPaymentTracker />);
    fireEvent.click(await screen.findByText('Ama Mensah'));
    expect(await screen.findByText('Preparing tracked transfer accounts...')).toBeInTheDocument();
    await act(async () => routePost.reject(new Error('Provider unavailable')));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByText(/tracked transfer account ready/i)).not.toBeInTheDocument();
    expect(screen.getByText('Account preparation failed')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Tracked transfer account is not available right now.');
    expect(axios.post).toHaveBeenCalledTimes(1);
  });

  it('keeps history loading independent when instructions finish first', async () => {
    const history = deferred();
    mockStudentReads({
      '/api/students/1/payments': history.promise,
      '/api/students/1/payment-codes': Promise.resolve({ data: codesFor(1, readyRoute) }),
    });
    render(<StudentPaymentTracker />);
    fireEvent.click(await screen.findByText('Ama Mensah'));
    expect(await screen.findByRole('button', { name: /print instructions/i })).toBeEnabled();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getByText('Loading payment data...')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /print latest receipt/i })).not.toBeInTheDocument();
    await act(async () => history.resolve({ data: [historicalPayment] }));
    expect(screen.queryByText('Loading payment data...')).not.toBeInTheDocument();
    expect(screen.getByText('Recent Payments:')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /print latest receipt/i })).toBeEnabled();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('keeps preparation visible until all route POSTs settle', async () => {
    const firstRoute = deferred();
    const secondRoute = deferred();
    const codes = codesFor(1);
    codes.payment_codes.push({ ...codes.payment_codes[0], code: 'S001-T2' });
    mockStudentReads({ '/api/students/1/payment-codes': Promise.resolve({ data: codes }) });
    axios.post.mockImplementation((url) => url.includes('S001-T1') ? firstRoute.promise : secondRoute.promise);
    render(<StudentPaymentTracker />);
    fireEvent.click(await screen.findByText('Ama Mensah'));
    expect(await screen.findByText('Preparing tracked transfer accounts...')).toBeInTheDocument();
    await act(async () => firstRoute.resolve({ data: { virtual_route: readyRoute } }));
    expect(screen.getByRole('status')).toHaveTextContent('Preparing tracked transfer accounts...');
    expect(screen.queryByText(/tracked transfer account ready/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /copy instructions|print instructions/i })).not.toBeInTheDocument();
    await act(async () => secondRoute.resolve({ data: { virtual_route: readyRoute } }));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getAllByText(/tracked transfer account ready/i)).toHaveLength(2);
    expect(screen.getByRole('button', { name: /copy instructions/i })).toBeEnabled();
    expect(axios.post).toHaveBeenCalledTimes(2);
  });

  it('invalidates pending responses when a student has no valid selection ID', async () => {
    const history = deferred();
    const codes = deferred();
    mockStudentReads({
      '/api/students/1/payments': history.promise,
      '/api/students/1/payment-codes': codes.promise,
    }, [{ id: null, name: 'Invalid Student', current_class: 'JHS 1' }]);
    render(<StudentPaymentTracker />);
    fireEvent.click(await screen.findByText('Ama Mensah'));
    fireEvent.click(screen.getByText('Invalid Student'));
    await act(async () => {
      history.resolve({ data: [historicalPayment] });
      codes.resolve({ data: codesFor(1) });
    });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /print latest receipt|print instructions/i })).not.toBeInTheDocument();
    expect(axios.get.mock.calls.some(([url]) => url.includes('/undefined/'))).toBe(false);
    expect(axios.post).not.toHaveBeenCalled();
  });

  it.each(['GET', 'POST'])('safely settles pending %s and history after unmount', async (stage) => {
    const history = deferred();
    const codes = deferred();
    const route = deferred();
    mockStudentReads({
      '/api/students/1/payments': history.promise,
      '/api/students/1/payment-codes': codes.promise,
    });
    axios.post.mockReturnValue(route.promise);
    const { unmount } = render(<StudentPaymentTracker />);
    fireEvent.click(await screen.findByText('Ama Mensah'));
    if (stage === 'POST') await act(async () => codes.resolve({ data: codesFor(1) }));
    unmount();
    await act(async () => {
      history.reject(new Error('History after unmount'));
      if (stage === 'GET') codes.resolve({ data: codesFor(1) });
      else route.resolve({ data: { virtual_route: readyRoute } });
    });
    expect(axios.post).toHaveBeenCalledTimes(stage === 'POST' ? 1 : 0);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('does not refresh an old student when recovery settles after switching students', async () => {
    const recovery = deferred();
    mockStudentReads({
      '/api/students/1/payments': Promise.resolve({ data: [] }),
      '/api/students/1/payment-codes': Promise.resolve({ data: codesFor(1, readyRoute) }),
      '/api/students/2/payments': Promise.resolve({ data: [] }),
      '/api/students/2/payment-codes': Promise.resolve({ data: codesFor(2, readyRoute) }),
    });
    axios.post.mockReturnValue(recovery.promise);
    render(<StudentPaymentTracker />);
    fireEvent.click(await screen.findByText('Ama Mensah'));
    fireEvent.change(await screen.findByLabelText(/transaction reference/i), { target: { value: 'old-reference' } });
    fireEvent.click(screen.getByRole('button', { name: /recover paystack payment/i }));
    fireEvent.click(screen.getByText('Yaw Owusu'));
    await act(async () => recovery.resolve({ data: { status: 'recorded', message: 'OLD RECOVERY' } }));
    expect(screen.queryByText('OLD RECOVERY')).not.toBeInTheDocument();
    expect(axios.get.mock.calls.filter(([url]) => url.includes('/students/1/'))).toHaveLength(2);
    expect(await screen.findByRole('button', { name: /recover paystack payment/i })).toBeDisabled();
    expect(screen.getByText(/Account number: 2222222222/)).toBeInTheDocument();
  });

  it('keeps Free Tier locked without starting payment or provider requests', () => {
    useSubscription.mockReturnValue({ plan: 'Free Tier', hasFeature: () => false });
    render(<StudentPaymentTracker />);
    expect(screen.getByText('Payment Tracking Locked')).toBeInTheDocument();
    expect(axios.get).not.toHaveBeenCalled();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('shows a blocked collection banner instead of payment references', async () => {
    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Ama Mensah'));

    await waitFor(() => {
      expect(screen.getByText(/parent payment references are currently blocked/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/upgrade the school subscription or reduce active enrollment/i)).toBeInTheDocument();
    expect(screen.getByText('54')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('shows the verification gate before payment instructions are available', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
              parent_name: 'Kojo Mensah',
              parent_phone: '0240000000',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 120,
            terminal_report_fee: 10,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments') {
        return Promise.reject({
          response: {
            data: {
              error: 'school_verification_required',
              message: 'School verification is required before payment instructions, collection, or payment records are available.',
            },
          },
        });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.reject({
          response: {
            data: {
              error: 'school_verification_required',
              message: 'School verification is required before payment instructions, collection, or payment records are available.',
            },
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Ama Mensah'));

    await waitFor(() => {
      expect(screen.getByText(/submit and complete school verification before sharing payment instructions/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/verification sits above subscription access for payment operations/i)).toBeInTheDocument();
  });

  it('shows a generic unavailable message without upgrade guidance for non-plan payment-code errors', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
              parent_name: 'Kojo Mensah',
              parent_phone: '0240000000',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 120,
            terminal_report_fee: 10,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.reject({
          response: {
            data: {
              error: 'student_payment_identity_missing',
              message: 'This student does not have a payment identity yet. Add or repair the student ID before sharing parent payment instructions.',
            },
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Ama Mensah'));

    await waitFor(() => {
      expect(screen.getByText(/unable to load payment references right now/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/add or repair the student id before sharing parent payment instructions/i)).toBeInTheDocument();
    expect(screen.queryByText(/upgrade the school subscription or reduce active enrollment/i)).not.toBeInTheDocument();
  });

  it('filters the student list by class before selection', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
              parent_name: 'Kojo Mensah',
              parent_phone: '0240000000',
            },
            {
              id: 2,
              name: 'Yaw Owusu',
              student_code: 'S002',
              current_class: 'JHS 2',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 120,
            terminal_report_fee: 10,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments' || url === '/api/students/2/payments') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/api/students/1/payment-codes' || url === '/api/students/2/payment-codes') {
        return Promise.resolve({
          data: {
            student_name: 'Ama Mensah',
            student_code: 'S001',
            payment_codes: [],
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
      expect(screen.getByText('Yaw Owusu')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByDisplayValue('All Classes'), {
      target: { value: 'JHS 2' },
    });

    expect(screen.queryByText('Ama Mensah')).not.toBeInTheDocument();
    expect(screen.getByText('Yaw Owusu')).toBeInTheDocument();
    expect(screen.getByText(/1 student found in JHS 2/i)).toBeInTheDocument();
  });

  it('generates and shows a tracked transfer account for a payment reference', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
              parent_name: 'Kojo Mensah',
              parent_phone: '0240000000',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 100,
            tuition_convenience_fee_percentage: 1.95,
            terminal_report_fee: 0,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.resolve({
          data: {
            student_name: 'Ama Mensah',
            student_code: 'S001',
            payment_identity: {
              supports_fee_route_dvas: true,
            },
            payment_codes: [
              {
                fee_type: 'Tuition',
                code: 'S001-T1',
                reference_code: 'S001-T1',
                base_amount: 100,
                preferred_payment_model: 'reference_first',
                has_virtual_route: false,
                virtual_route: null,
              },
            ],
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    axios.post.mockImplementation((url) => {
      if (url === '/api/students/1/payment-codes/S001-T1/virtual-account') {
        return Promise.resolve({
          data: {
            message: 'Tracked transfer account generated successfully.',
            payment_code: {
              fee_type: 'Tuition',
              code: 'S001-T1',
              reference_code: 'S001-T1',
              base_amount: 100,
              preferred_payment_model: 'virtual_account_ready',
              has_virtual_route: true,
              virtual_route: {
                bank_name: 'Paystack-Titan',
                account_number: '0192837465',
                account_name: 'EDUPULSE / AMA MENSAH',
                base_amount: 100,
                convenience_fee_amount: 1.95,
                total_amount: 101.95,
              },
            },
            virtual_route: {
              bank_name: 'Paystack-Titan',
              account_number: '0192837465',
              account_name: 'EDUPULSE / AMA MENSAH',
              base_amount: 100,
              convenience_fee_amount: 1.95,
              total_amount: 101.95,
            },
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Ama Mensah'));

    await waitFor(() => {
      expect(screen.getByText(/tracked transfer account ready/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Paystack-Titan/i)).toBeInTheDocument();
    expect(screen.getAllByText(/0192837465/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Convenience fee: 1.95% = GH₵ 1.95/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Transfer total: GH₵ 101.95/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /tracked transfer/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /online checkout link/i })).not.toBeInTheDocument();
    expect(axios.post).toHaveBeenCalledWith(
      '/api/students/1/payment-codes/S001-T1/virtual-account',
      {},
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer token-1',
          'X-School-ID': 'TEST-001',
        }),
      })
    );
  });

  it('prints payment instructions for the filtered students in one batch', async () => {
    const printWindow = {
      document: {
        write: vi.fn(),
        close: vi.fn(),
      },
      focus: vi.fn(),
      print: vi.fn(),
    };
    vi.stubGlobal('open', vi.fn(() => printWindow));

    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
            },
            {
              id: 2,
              name: 'Yaw Owusu',
              student_code: 'S002',
              current_class: 'JHS 1',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 120,
            terminal_report_fee: 10,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments' || url === '/api/students/2/payments') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.resolve({
          data: {
            student_name: 'Ama Mensah',
            student_code: 'S001',
            class: 'JHS 1',
            payment_identity: {
              supports_fee_route_dvas: true,
            },
            payment_codes: [
              {
                fee_type: 'Tuition',
                code: 'S001-T1',
                reference_code: 'S001-T1',
                base_amount: 120,
              },
            ],
          },
        });
      }

      if (url === '/api/students/2/payment-codes') {
        return Promise.resolve({
          data: {
            student_name: 'Yaw Owusu',
            student_code: 'S002',
            class: 'JHS 1',
            payment_identity: {
              supports_fee_route_dvas: true,
            },
            payment_codes: [
              {
                fee_type: 'Tuition',
                code: 'S002-T1',
                reference_code: 'S002-T1',
                base_amount: 120,
              },
            ],
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    axios.post.mockImplementation((url) => {
      if (url === '/api/students/1/payment-codes/S001-T1/virtual-account') {
        return Promise.resolve({
          data: {
            payment_code: {
              fee_type: 'Tuition',
              code: 'S001-T1',
              reference_code: 'S001-T1',
              base_amount: 120,
              has_virtual_route: true,
              virtual_route: {
                bank_name: 'Paystack-Titan',
                account_number: '1111111111',
                account_name: 'EDUPULSE / AMA MENSAH',
                total_amount: 126,
              },
            },
            virtual_route: {
              bank_name: 'Paystack-Titan',
              account_number: '1111111111',
              account_name: 'EDUPULSE / AMA MENSAH',
              total_amount: 126,
            },
          },
        });
      }

      if (url === '/api/students/2/payment-codes/S002-T1/virtual-account') {
        return Promise.resolve({
          data: {
            payment_code: {
              fee_type: 'Tuition',
              code: 'S002-T1',
              reference_code: 'S002-T1',
              base_amount: 120,
              has_virtual_route: true,
              virtual_route: {
                bank_name: 'Paystack-Titan',
                account_number: '2222222222',
                account_name: 'EDUPULSE / YAW OWUSU',
                total_amount: 126,
              },
            },
            virtual_route: {
              bank_name: 'Paystack-Titan',
              account_number: '2222222222',
              account_name: 'EDUPULSE / YAW OWUSU',
              total_amount: 126,
            },
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
      expect(screen.getByText('Yaw Owusu')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /print 2 filtered instructions/i }));

    await waitFor(() => {
      expect(window.open).toHaveBeenCalled();
    });

    expect(axios.get).toHaveBeenCalledWith(
      '/api/students/1/payment-codes',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer token-1',
          'X-School-ID': 'TEST-001',
        }),
      })
    );
    expect(axios.get).toHaveBeenCalledWith(
      '/api/students/2/payment-codes',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer token-1',
          'X-School-ID': 'TEST-001',
        }),
      })
    );
    expect(printWindow.document.write).toHaveBeenCalled();
    expect(printWindow.document.write.mock.calls[0][0]).toContain('Ama Mensah');
    expect(printWindow.document.write.mock.calls[0][0]).toContain('Yaw Owusu');
    expect(printWindow.document.write.mock.calls[0][0]).toContain('1111111111');
    expect(printWindow.document.write.mock.calls[0][0]).toContain('2222222222');
  });

  it('prints the tracked transfer receipt breakdown with net school fee recorded', async () => {
    const printWindow = {
      document: {
        write: vi.fn(),
        close: vi.fn(),
      },
      focus: vi.fn(),
      print: vi.fn(),
    };
    vi.stubGlobal('open', vi.fn(() => printWindow));

    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 120,
            tuition_transfer_pricing: marginPricing,
            terminal_report_fee: 0,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments') {
        return Promise.resolve({
          data: [
            {
              id: 9,
              payment_type: 'Tuition',
              method: 'Paystack_Payment',
              amount: 20.19,
              display_amount: 21.0,
              applied_amount: 20.19,
              reference_id: '6aae84c407261e44077d06d6',
              status: 'Confirmed',
              date_paid: '2026-09-19T09:00:00Z',
              payment_category: {
                collection_channel: 'dedicated_virtual_account',
                transfer_total_amount: 21.0,
                collected_convenience_fee_amount: 0.4,
                actual_provider_fee_amount: 0.41,
                applied_school_fee_amount: 20.19,
              },
            },
          ],
        });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.resolve({
          data: {
            student_name: 'Ama Mensah',
            student_code: 'S001',
            payment_identity: {
              supports_fee_route_dvas: true,
            },
            payment_codes: [
              {
                fee_type: 'Tuition',
                code: 'S001-T1',
                reference_code: 'S001-T1',
                base_amount: 120,
                has_virtual_route: true,
                virtual_route: {
                  bank_name: 'Paystack-Titan',
                  account_number: '1111111111',
                  account_name: 'EDUPULSE / AMA MENSAH',
                  base_amount: 120,
                  convenience_fee_amount: 2.34,
                  total_amount: 122.34,
                },
              },
            ],
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Ama Mensah'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /print latest receipt/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /print latest receipt/i }));

    await waitFor(() => {
      expect(window.open).toHaveBeenCalled();
    });

    expect(printWindow.document.write).toHaveBeenCalled();
    const printedHtml = printWindow.document.write.mock.calls[0][0];
    expect(printedHtml).toContain('Gross Transfer Received');
    expect(printedHtml).toContain('Convenience Fee Deducted');
    expect(printedHtml).toContain('Paystack Fee Deducted');
    expect(printedHtml).toContain('Net School Fee Recorded');
    expect(printedHtml).toContain('GH₵ 21.00');
    expect(printedHtml).toContain('GH₵ 0.40');
    expect(printedHtml).toContain('GH₵ 0.41');
    expect(printedHtml).toContain('GH₵ 20.19');
  });

  it('does not show the paystack reconciliation card in the tenant tracker', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
              parent_name: 'Kojo Mensah',
              parent_phone: '0240000000',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 120,
            terminal_report_fee: 10,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.resolve({
          data: {
            student_name: 'Ama Mensah',
            student_code: 'S001',
            payment_identity: {
              supports_fee_route_dvas: false,
            },
            payment_codes: [],
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    });

    expect(screen.queryByText(/recover a successful tracked transfer by exact reference/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/transaction reference/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /recover paystack payment/i })).not.toBeInTheDocument();
  });

  it('reconciles a successful tracked transfer reference from the payment tracker', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
              parent_name: 'Kojo Mensah',
              parent_phone: '0240000000',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 100,
            tuition_convenience_fee_percentage: 1,
            terminal_report_fee: 0,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.resolve({
          data: {
            student_name: 'Ama Mensah',
            student_code: 'S001',
            payment_identity: {
              supports_fee_route_dvas: true,
            },
            payment_codes: [
              {
                fee_type: 'Tuition',
                code: 'S001-T1',
                reference_code: 'S001-T1',
                base_amount: 100,
                preferred_payment_model: 'virtual_account_ready',
                has_virtual_route: true,
                virtual_route: {
                  bank_name: 'Affinity Ghana Savings and Loans',
                  account_number: '7003000477792',
                  account_name: 'EDUPULSE / AMA MENSAH',
                  base_amount: 100,
                  convenience_fee_amount: 1,
                  total_amount: 101,
                },
              },
            ],
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    axios.post.mockImplementation((url, body) => {
      if (url === '/api/finance/paystack/recover-reference') {
        expect(body).toEqual({ reference: '6aae84c407261e44077d06d6' });
        return Promise.resolve({
          data: {
            status: 'recorded',
            reference: '6aae84c407261e44077d06d6',
            message: 'Tracked transfer recovered and attached to the student.',
            gross_amount_paid: 21,
            collected_convenience_fee_amount: 0.4,
            actual_provider_fee_amount: 0.41,
            applied_school_fee_amount: 20.19,
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Ama Mensah'));

    await waitFor(() => {
      expect(screen.getByText(/recover a successful tracked transfer by exact reference/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/transaction reference/i), {
      target: { value: '6aae84c407261e44077d06d6' },
    });
    fireEvent.click(screen.getByRole('button', { name: /recover paystack payment/i }));

    await waitFor(() => {
      expect(screen.getByText(/tracked transfer recovered and attached to the student/i)).toBeInTheDocument();
    });

    expect(screen.getByText('Gross paid: GH₵ 21.00')).toBeInTheDocument();
    expect(screen.getByText('Convenience deducted: GH₵ 0.40')).toBeInTheDocument();
    expect(screen.getByText('Paystack fee deducted: GH₵ 0.41')).toBeInTheDocument();
    expect(screen.getByText('Applied to school fee: GH₵ 20.19')).toBeInTheDocument();

    await waitFor(() => {
      expect(axios.get.mock.calls.filter(([url]) => url === '/api/students/1/payments')).toHaveLength(2);
      expect(axios.get.mock.calls.filter(([url]) => url === '/api/students/1/payment-codes')).toHaveLength(2);
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });

    expect(axios.post).toHaveBeenCalledWith(
      '/api/finance/paystack/recover-reference',
      { reference: '6aae84c407261e44077d06d6' },
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer token-1',
          'X-School-ID': 'TEST-001',
        }),
      })
    );
  });

  it('shows tuition installments with their own status and deadlines', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/students') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              name: 'Ama Mensah',
              student_code: 'S001',
              current_class: 'JHS 1',
            },
          ],
        });
      }

      if (url === '/api/school/fees') {
        return Promise.resolve({
          data: {
            tuition_fee: 1000,
            tuition_convenience_fee_percentage: 1.95,
            terminal_report_fee: 0,
            feeding_fee: 0,
            uniform_fee: 0,
            transport_fee: 0,
          },
        });
      }

      if (url === '/api/students/1/payments') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/api/students/1/payment-codes') {
        return Promise.resolve({
          data: {
            student_name: 'Ama Mensah',
            student_code: 'S001',
            payment_identity: {
              supports_fee_route_dvas: true,
              tuition_installments_enabled: true,
            },
            payment_codes: [
              {
                fee_type: 'Tuition',
                code: 'S001-TUIT-I1',
                reference_code: 'S001-TUIT-I1',
                base_amount: 500,
                total_amount: 509.75,
                has_virtual_route: true,
                virtual_route: {
                  bank_name: 'Paystack-Titan',
                  account_number: '1111111111',
                  account_name: 'EDUPULSE / AMA MENSAH',
                  base_amount: 500,
                  convenience_fee_amount: 9.75,
                  total_amount: 509.75,
                },
                payment_category: {
                  fee_type: 'Tuition',
                  installment_number: 1,
                  installment_label: 'Installment 1',
                  installment_status: 'open',
                  installment_start_date: '2026-10-01',
                  installment_due_date: '2026-10-31',
                  installment_paid_amount: 0,
                  installment_outstanding_amount: 500,
                },
              },
              {
                fee_type: 'Tuition',
                code: 'S001-TUIT-I2',
                reference_code: 'S001-TUIT-I2',
                base_amount: 500,
                total_amount: 509.75,
                has_virtual_route: true,
                virtual_route: {
                  bank_name: 'Paystack-Titan',
                  account_number: '2222222222',
                  account_name: 'EDUPULSE / AMA MENSAH',
                  base_amount: 500,
                  convenience_fee_amount: 9.75,
                  total_amount: 509.75,
                },
                payment_category: {
                  fee_type: 'Tuition',
                  installment_number: 2,
                  installment_label: 'Installment 2',
                  installment_status: 'upcoming',
                  installment_start_date: '2026-11-01',
                  installment_due_date: '2026-11-30',
                  installment_paid_amount: 0,
                  installment_outstanding_amount: 500,
                },
              },
            ],
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<StudentPaymentTracker />);

    await waitFor(() => {
      expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Ama Mensah'));

    await waitFor(() => {
      expect(screen.getByText('Installment 1')).toBeInTheDocument();
      expect(screen.getByText('Installment 2')).toBeInTheDocument();
    });

    expect(screen.getByText(/open • opens 2026-10-01 • due 2026-10-31/i)).toBeInTheDocument();
    expect(screen.getByText(/upcoming • opens 2026-11-01 • due 2026-11-30/i)).toBeInTheDocument();
    expect(screen.getAllByText(/paid so far on this installment: gh₵ 0.00 • remaining: gh₵ 500.00/i)).toHaveLength(2);
    expect(screen.queryByText('Required:')).not.toBeInTheDocument();
  });

  it('filters the student list by each learner\'s own tuition balance', async () => {
    const defaultGet = axios.get.getMockImplementation();
    axios.get.mockImplementation((url) => (url === '/api/students'
      ? Promise.resolve({ data: [
        { id: 1, name: 'Ama Mensah', student_code: 'S001', current_class: 'JHS 1', tuition_paid_amount: 120, tuition_outstanding_amount: 0 },
        { id: 2, name: 'Yaw Owusu', student_code: 'S002', current_class: 'JHS 1', tuition_paid_amount: 40, tuition_outstanding_amount: 80 },
        { id: 3, name: 'Esi Boateng', student_code: 'S003', current_class: 'JHS 1', tuition_paid_amount: 0, tuition_outstanding_amount: 120 },
      ] })
      : defaultGet(url)));
    render(<StudentPaymentTracker />);
    await screen.findByText('Esi Boateng');
    const statusSelect = screen.getByDisplayValue('All Status');

    fireEvent.change(statusSelect, { target: { value: 'paid' } });
    expect(screen.getByText('Ama Mensah')).toBeInTheDocument();
    expect(screen.queryByText('Yaw Owusu')).not.toBeInTheDocument();
    expect(screen.queryByText('Esi Boateng')).not.toBeInTheDocument();

    fireEvent.change(statusSelect, { target: { value: 'pending' } });
    expect(screen.getByText('Yaw Owusu')).toBeInTheDocument();
    expect(screen.queryByText('Ama Mensah')).not.toBeInTheDocument();
    expect(screen.queryByText('Esi Boateng')).not.toBeInTheDocument();
  });

  it('picks up automatically tracked payments without reselecting the learner', async () => {
    let paymentsCalls = 0;
    const route = { account_number: '1111111111', bank_name: 'Test bank', base_amount: 120, total_amount: 120, status: 'assigned' };
    const defaultGet = axios.get.getMockImplementation();
    axios.get.mockImplementation((url) => {
      if (url === '/api/students/1/payments') {
        paymentsCalls += 1;
        return Promise.resolve({ data: paymentsCalls === 1 ? [] : [{
          id: 77, payment_type: 'Tuition', amount: 120, status: 'Confirmed',
          date_paid: '2026-10-04 09:00', reference_id: 'PSTK-AUTO-1', method: 'Paystack Transfer',
        }] });
      }
      if (url === '/api/students/1/payment-codes') {
        return Promise.resolve({ data: paymentsCalls <= 1
          ? codesFor(1, route)
          : { ...codesFor(1), payment_codes: [{ ...codesFor(1).payment_codes[0], base_amount: 0, payment_category: { fee_type: 'Tuition', tuition_status: 'paid' } }] } });
      }
      return defaultGet(url);
    });

    render(<StudentPaymentTracker />);
    fireEvent.click(await screen.findByText('Ama Mensah'));
    expect(await screen.findByText(/tracked transfer account ready/i)).toBeInTheDocument();
    expect(screen.queryByText('PSTK-AUTO-1')).not.toBeInTheDocument();

    await act(async () => { window.dispatchEvent(new Event('focus')); });
    expect(await screen.findByText(/PSTK-AUTO-1/)).toBeInTheDocument();
    expect(screen.getAllByText('✅ Paid').length).toBeGreaterThan(0);
    expect(axios.post).not.toHaveBeenCalled();
  });
});