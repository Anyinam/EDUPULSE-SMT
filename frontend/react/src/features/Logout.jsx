import React, { useEffect } from 'react';

export default function Logout() {
  useEffect(() => {
    localStorage.clear();
    window.location.href = '/login';
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <p className="text-xl font-bold text-gray-600">Logging out...</p>
    </div>
  );
}