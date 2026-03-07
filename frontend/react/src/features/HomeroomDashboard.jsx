import React, { useState, useEffect } from 'react';
import axios from 'axios';
import PaymentEntry from './PaymentEntry';
import TimetableManager from '../components/TimetableManager';
import { useBranding } from '../hooks/useBranding';

/**
 * Homeroom Module: TRL 6 Interface for Academic Governance.
 * Implements 'Terminal Report' logic as a human-in-the-loop gateway.
 */
export default function Homeroom() {
  const [students, setStudents] = useState([]);
  const [currentClass, setCurrentClass] = useState(localStorage.getItem('assigned_class') || "JHS 1");
  const [attendanceChanges, setAttendanceChanges] = useState({});
  const [savingAttendance, setSavingAttendance] = useState(false);
  const { branding } = useBranding();
  const isHomeroom = Boolean(localStorage.getItem('assigned_class') && localStorage.getItem('assigned_class').length > 0);

  // Helper to get auth headers
  const getAuthHeaders = () => ({
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  // Fetch student list for the specific school tenant
  useEffect(() => {
    const fetchStudents = async () => {
      try {
        const res = await axios.get(`/api/students/by-class/${currentClass}`, getAuthHeaders());
        setStudents(res.data);
      } catch (err) {
        console.error("Failed to load students");
      }
    };
    fetchStudents();
  }, [currentClass]);

  const handleAttendance = (studentId, status) => {
    // Track changes locally without saving immediately
    setAttendanceChanges(prev => ({
      ...prev,
      [studentId]: status
    }));
    
    // Update local UI state
    setStudents(prev => prev.map(s => s.id === studentId ? { ...s, is_present: status } : s));
  };

  const handleSaveAttendance = async () => {
    const changesArray = Object.entries(attendanceChanges).map(([studentId, status]) => ({
      student_id: parseInt(studentId),
      status: status
    }));

    if (changesArray.length === 0) {
      alert("No attendance changes to save.");
      return;
    }

    setSavingAttendance(true);
    try {
      await axios.post('/api/homeroom/attendance/batch', {
        attendance_records: changesArray
      }, getAuthHeaders());
      
      alert(`Successfully saved attendance for ${changesArray.length} student(s).`);
      setAttendanceChanges({});
    } catch (err) {
      alert("Failed to save attendance. Please try again.");
      console.error(err);
    } finally {
      setSavingAttendance(false);
    }
  };

  const handlePayFeeding = async (student) => {
    if (!window.confirm(`Mark daily feeding fee (5.00) as PAID for ${student.name}?`)) return;
    
    try {
      await axios.post('/api/finance/receive-payment', {
        student_id: student.id,
        amount: 5.0,
        type: 'Feeding',
        method: 'Cash'
      }, getAuthHeaders());
      
      // Update local state
      setStudents(prev => prev.map(s => s.id === student.id ? { ...s, feeding_paid: true } : s));
      alert("Feeding payment recorded.");
    } catch (err) {
      alert("Failed to record payment.");
    }
  };






  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="max-w-6xl mx-auto">
        {/* HEADER SECTION */}
        <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100 mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-black text-slate-800">Homeroom Governance</h1>
            <p className="text-slate-500 font-medium italic">Oversight for {currentClass} • {branding.name}</p>
          </div>
          <div className="text-right">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Privilege Level</span>
            <span className="text-purple-600 font-bold flex items-center gap-1 justify-end">
              🛡️ Class Administrator
            </span>
          </div>
        </div>

        <div className="mb-8">
          <TimetableManager title="My Teaching Schedule" scope="mine" canManage={false} />
        </div>
            <div className="mb-8 grid grid-cols-1 lg:grid-cols-2 gap-8">
              {isHomeroom && <PaymentEntry students={students} />}
            </div>

            {/* CLASS LIST TABLE */}
            <div className="bg-white rounded-3xl shadow-xl overflow-hidden border border-slate-100">
              <div className="p-6 border-b border-slate-100 bg-slate-50/50">
                <div className="flex justify-between items-center">
                  <h3 className="font-bold text-slate-700">Class Roster: Attendance & Feeding <span className="ml-2 text-sm font-normal text-slate-500">(Class Size: {students.length})</span></h3>
                  <button
                    onClick={handleSaveAttendance}
                    disabled={savingAttendance || Object.keys(attendanceChanges).length === 0}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                  >
                    {savingAttendance ? 'Saving...' : `Save Attendance ${Object.keys(attendanceChanges).length > 0 ? `(${Object.keys(attendanceChanges).length})` : ''}`}
                  </button>
                </div>
              </div>
              <table className="w-full text-left">
                <thead className="bg-slate-50 border-b">
                  <tr className="text-slate-500 text-[10px] font-black uppercase tracking-wider">
                    <th className="px-8 py-5">Student Information</th>
                    <th className="px-8 py-5">Guardian Contact</th>
                    <th className="px-8 py-5">Attendance</th>
                    {isHomeroom && <th className="px-8 py-5">Feeding Status</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {students.map(student => (
                    <tr key={student.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-8 py-6">
                        <p className="font-black text-slate-800">{student.name}</p>
                        <p className="text-xs text-slate-400 font-mono">{student.student_code}</p>
                      </td>
                      <td className="px-8 py-6">
                        <p className="text-sm font-medium text-slate-600">{student.parent_email || 'N/A'}</p>
                      </td>
                      <td className="px-8 py-6">
                        <label className="flex items-center cursor-pointer">
                          <input 
                            type="checkbox" 
                            checked={student.is_present} 
                            onChange={(e) => handleAttendance(student.id, e.target.checked)}
                            className="w-5 h-5 text-purple-600 rounded focus:ring-purple-500 border-gray-300"
                          />
                          <span className="ml-2 text-sm font-medium text-slate-700">
                            {student.is_present ? 'Present' : 'Absent'}
                            {attendanceChanges[student.id] !== undefined && (
                              <span className="ml-1 text-xs text-yellow-600">●</span>
                            )}
                          </span>
                        </label>
                      </td>
                      {isHomeroom && (
                        <td className="px-8 py-6">
                          {student.feeding_paid ? (
                            <span className="bg-green-100 text-green-700 px-3 py-1 rounded-full text-xs font-bold">Paid ({student.payment_method || 'Cash'})</span>
                          ) : (
                            <button 
                              onClick={() => handlePayFeeding(student)}
                              className="bg-red-100 text-red-700 px-3 py-1 rounded-full text-xs font-bold hover:bg-red-200 transition-colors"
                            >
                              Pay Now (Unpaid)
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>

            </div>
      </div>
    </div>
  );
}