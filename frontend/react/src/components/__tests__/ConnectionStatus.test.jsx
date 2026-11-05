import { fireEvent, render, screen, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ConnectionStatus from '../ConnectionStatus';

describe('ConnectionStatus', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('warns that live information may be out of date while offline', () => {
    render(<ConnectionStatus />);

    fireEvent.offline(window);

    expect(screen.getByRole('status')).toHaveTextContent('Connection lost');
    expect(screen.getByRole('status')).toHaveTextContent('Some information may be out of date');
  });

  it('briefly asks staff to refresh after connectivity returns', () => {
    render(<ConnectionStatus />);
    fireEvent.offline(window);

    fireEvent.online(window);
    expect(screen.getByRole('status')).toHaveTextContent('Refresh dashboards to get the latest school information');

    act(() => {
      vi.advanceTimersByTime(6000);
    });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
