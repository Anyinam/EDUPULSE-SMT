import { useEffect, useState } from 'react';

const RESTORED_MESSAGE_DURATION = 6000;

export default function ConnectionStatus() {
  const [status, setStatus] = useState(() => (navigator.onLine ? 'online' : 'offline'));

  useEffect(() => {
    let restoredMessageTimeout;

    const handleOffline = () => {
      window.clearTimeout(restoredMessageTimeout);
      setStatus('offline');
    };

    const handleOnline = () => {
      setStatus('restored');
      window.clearTimeout(restoredMessageTimeout);
      restoredMessageTimeout = window.setTimeout(() => setStatus('online'), RESTORED_MESSAGE_DURATION);
    };

    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);

    return () => {
      window.clearTimeout(restoredMessageTimeout);
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('online', handleOnline);
    };
  }, []);

  if (status === 'online') return null;

  const isOffline = status === 'offline';
  return (
    <div className={`connection-status ${isOffline ? 'connection-status--offline' : 'connection-status--restored'}`} role="status" aria-live="polite">
      <span className="connection-status__label">
        {isOffline ? 'Connection lost' : 'Connection restored'}
      </span>
      <span>
        {isOffline
          ? 'Some information may be out of date. Reconnect to refresh live school data.'
          : 'Refresh dashboards to get the latest school information.'}
      </span>
    </div>
  );
}
