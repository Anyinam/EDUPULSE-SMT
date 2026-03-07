import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function KitchenDashboard() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await axios.get('/api/kitchen/dashboard', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'X-School-ID': localStorage.getItem('school_id')
          }
        });
        setStats(res.data);
      } catch (err) {
        console.error("Failed to load kitchen stats");
      }
    };
    fetchStats();
    // Refresh every 5 minutes
    const interval = setInterval(fetchStats, 300000);
    return () => clearInterval(interval);
  }, []);

  if (!stats) return <div className="p-8">Loading Kitchen Data...</div>;

  return (
    <div className="p-8 bg-orange-50 min-h-screen font-sans">
      <header className="mb-8 border-b border-orange-200 pb-4">
        <h1 className="text-4xl font-black text-orange-900">👩‍🍳 Kitchen Dashboard</h1>
        <p className="text-orange-700 font-medium">Daily Feeding Overview</p>
      </header>

      {stats.summary.is_holiday && (
        <div className="mb-6 p-4 rounded-2xl border border-red-200 bg-red-50 text-red-800 font-semibold">
          📅 Holiday Today: {stats.summary.holiday_name || 'National Holiday'} — Meals are not required.
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-blue-500">
          <p className="text-gray-500 text-xs font-bold uppercase">Total Students Present</p>
          <p className="text-3xl font-black text-gray-800">{stats.summary.total_students_present}</p>
        </div>
        <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-purple-500">
          <p className="text-gray-500 text-xs font-bold uppercase">Staff Meals</p>
          <p className="text-3xl font-black text-purple-600">{stats.summary.total_teachers}</p>
        </div>
        <div className="bg-orange-600 text-white p-6 rounded-2xl shadow-lg">
          <p className="text-orange-100 text-xs font-bold uppercase">Total Meals Needed</p>
          <p className="text-4xl font-black">{stats.summary.total_meals_needed}</p>
        </div>
      </div>

      {/* Class Breakdown */}
      <div className="bg-white rounded-2xl shadow-sm overflow-hidden border border-orange-100">
        <table className="w-full text-left">
          <thead className="bg-orange-100 text-orange-900">
            <tr>
              <th className="p-4 font-bold">Class</th>
              <th className="p-4 font-bold text-center">Students Present</th>
              <th className="p-4 font-bold text-center">Meals Needed</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-orange-50">
            {stats.classes.map((cls, idx) => (
              <tr key={idx} className="hover:bg-orange-50/50">
                <td className="p-4 font-bold text-gray-700">{cls.class_name}</td>
                <td className="p-4 text-center font-mono font-bold">{cls.present}</td>
                <td className="p-4 text-center font-mono font-bold">{cls.meals_needed ?? cls.paid ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}