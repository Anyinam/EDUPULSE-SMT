// src/features/GradeEntry.jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function GradeEntry() {
  const [students, setStudents] = useState([]);
  const [subject, setSubject] = useState('Mathematics');

  useEffect(() => {
    // Fetch students for the teacher's school
    axios.get('/api/teacher/students').then(res => setStudents(res.data));
  }, []);

  const handleUpdate = async (studentId, type, val) => {
    // Update local state first for speed
    const updated = students.map(s => s.id === studentId ? { ...s, [type]: val } : s);
    setStudents(updated);
  };

  const saveAll = async () => {
    await axios.post('/api/teacher/save-marks-bulk', { students, subject });
    alert("Marks synced to cloud!");
  };

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Grade Entry: {subject}</h1>
        <button onClick={saveAll} className="bg-green-600 text-white px-6 py-2 rounded-lg font-bold">Save Changes</button>
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full text-left">
          <thead className="bg-blue-900 text-white">
            <tr>
              <th className="p-4">Student Name</th>
              <th className="p-4">Class</th>
              <th className="p-4">Class Score (30%)</th>
              <th className="p-4">Exam Score (70%)</th>
              <th className="p-4">Total</th>
            </tr>
          </thead>
          <tbody>
            {students.map(s => (
              <tr key={s.id} className="border-b">
                <td className="p-4 font-medium">{s.name}</td>
                <td className="p-4">{s.current_class || s.class || 'N/A'}</td>
                <td className="p-4">
                  <input type="number" className="w-20 border p-1 rounded" value={s.class_score} 
                    onChange={(e) => handleUpdate(s.id, 'class_score', e.target.value)} />
                </td>
                <td className="p-4">
                  <input type="number" className="w-20 border p-1 rounded" value={s.exam_score} 
                    onChange={(e) => handleUpdate(s.id, 'exam_score', e.target.value)} />
                </td>
                <td className="p-4 font-bold text-blue-900">
                  {Math.round((s.class_score || 0) + (s.exam_score || 0))}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}