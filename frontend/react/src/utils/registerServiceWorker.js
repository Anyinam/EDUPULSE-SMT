if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js')
      .catch((error) => {
        console.error('EduPulse offline app shell could not be registered:', error);
      });
  });
}
