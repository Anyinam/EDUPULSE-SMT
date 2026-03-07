import React, { useState } from 'react';
import axios from 'axios';
import BulkStatusUpdate from '../components/BulkStatusUpdate';
import PromotionThresholdManager from '../components/PromotionThresholdManager';

export default function AdmissionsPanel() {
  const [formData, setFormData] = useState({
    first_name: '',
    surname: '',
    gender: 'Male',
    date_of_birth: '',
    student_code: '',
    guardian_name: '',
    parent_email: '',
    class_assigned: 'JHS 1',
    scholarship_type: 'none',
    scholarship_notes: '',
    score: 0 // Default for manual admission
  });
  const [csvFile, setCsvFile] = useState(null);

  // Promotion state
  const [promotionData, setPromotionData] = useState({
    student_id: '',
    new_class: 'JHS 2',
    remarks: ''
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  const validGrades = [
    "Nursery", "KG", 
    "Class 1", "Class 2", "Class 3", "Class 4", "Class 5", "Class 6",
    "JHS 1", "JHS 2", "JHS 3"
  ];

  const genderOptions = ['Male', 'Female', 'Other'];

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handlePromotionChange = (e) => {
    setPromotionData({ ...promotionData, [e.target.name]: e.target.value });
  };

  const handleSearchStudent = async (query) => {
    setSearchQuery(query);
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get(`/api/students/search?q=${encodeURIComponent(query)}`, { headers });
      setSearchResults(res.data.students || []);
    } catch (err) {
      console.error('Search error:', err);
    }
  };

  const selectStudent = (student) => {
    setPromotionData({
      ...promotionData,
      student_id: student.id
    });
    setSearchQuery(student.name);
    setSearchResults([]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      await axios.post('/api/admissions/admit', formData, { headers });
      const fullName = `${formData.first_name} ${formData.surname}`;
      alert(`Student ${fullName} admitted successfully!`);
      setFormData({
        first_name: '',
        surname: '',
        gender: 'Male',
        date_of_birth: '',
        student_code: '',
        guardian_name: '',
        parent_email: '',
        class_assigned: 'JHS 1',
        scholarship_type: 'none',
        scholarship_notes: '',
        score: 0
      });
    } catch (err) {
      alert(err.response?.data?.message || "Admission failed.");
    }
  };

  const handleBulkUpload = async () => {
    if (!csvFile) return alert("Please select a CSV file.");
    
    const uploadData = new FormData();
    uploadData.append('file', csvFile);

    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id'),
        'Content-Type': 'multipart/form-data'
      };
      const res = await axios.post('/api/admissions/bulk-upload', uploadData, { headers });
      
      let msg = res.data.message;
      if (res.data.warnings && res.data.warnings.length > 0) {
        msg += "\n\n⚠️ WARNINGS:\n" + res.data.warnings.join("\n");
      }
      if (res.data.errors && res.data.errors.length > 0) {
        msg += "\n\n❌ ERRORS:\n" + res.data.errors.join("\n");
      }
      alert(msg);
      setCsvFile(null);
    } catch (err) {
      alert(err.response?.data?.message || "Bulk upload failed.");
    }
  };

  const handlePromoteStudent = async (e) => {
    e.preventDefault();
    if (!promotionData.student_id) {
      alert("Please select a student");
      return;
    }

    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.post('/api/admissions/promote-student', promotionData, { headers });
      alert(res.data.message);
      setPromotionData({
        student_id: '',
        new_class: 'JHS 2',
        remarks: ''
      });
      setSearchQuery('');
    } catch (err) {
      alert(err.response?.data?.message || "Promotion failed.");
    }
  };

  return (
    <div className="space-y-8">
      {/* Bulk Status Update - End of Year Operations */}
      <div className="bg-linear-to-r from-blue-500 to-blue-600 p-6 rounded-3xl shadow-lg text-white">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-2xl font-black mb-2">⚡ Bulk Status Update</h3>
            <p className="text-blue-100">Update all students in a class (e.g., mark JHS 3 as Graduated after BECE)</p>
          </div>
          <BulkStatusUpdate trigger="modal" />
        </div>
      </div>

      {/* Promotion Configuration */}
      <div className="bg-linear-to-r from-indigo-500 to-purple-600 p-6 rounded-3xl shadow-lg text-white">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-2xl font-black mb-2">⚙️ Promotion Configuration</h3>
            <p className="text-indigo-100">Set performance requirements, then use manual override below when needed</p>
          </div>
          <PromotionThresholdManager />
        </div>
      </div>

      {/* Manual Admission Form */}
      <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
        <h2 className="text-2xl font-bold text-slate-800 mb-6">Manual Admission</h2>
        <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">First Name</label>
            <input name="first_name" value={formData.first_name} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50" required placeholder="e.g. Kofi" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Surname</label>
            <input name="surname" value={formData.surname} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50" required placeholder="e.g. Mensah" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Gender</label>
            <select name="gender" value={formData.gender} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50">
              {genderOptions.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Date of Birth</label>
            <input name="date_of_birth" type="date" value={formData.date_of_birth} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Class Assigned</label>
            <select name="class_assigned" value={formData.class_assigned} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50">
              {validGrades.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Guardian Name</label>
            <input name="guardian_name" value={formData.guardian_name} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50" placeholder="Parent/Guardian Name" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Parent Email</label>
            <input name="parent_email" type="email" value={formData.parent_email} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50" placeholder="For notifications" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Scholarship</label>
            <select name="scholarship_type" value={formData.scholarship_type} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50">
              <option value="none">No Scholarship</option>
              <option value="tuition">Tuition Free</option>
              <option value="tuition_feeding">Tuition + Feeding Free</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Scholarship Notes</label>
            <input name="scholarship_notes" value={formData.scholarship_notes} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50" placeholder="Optional notes" />
          </div>
          <div className="md:col-span-2 pt-4">
              <button type="submit" className="bg-blue-900 text-white px-8 py-3 rounded-xl font-bold hover:bg-blue-800 w-full md:w-auto shadow-lg shadow-blue-200">Admit Student</button>
          </div>
        </form>
      </div>

      {/* Bulk Upload Section */}
      <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
        <h2 className="text-2xl font-bold text-slate-800 mb-6">Bulk Upload via CSV</h2>
        <div className="flex flex-col md:flex-row gap-4 items-start md:items-center">
          <input type="file" accept=".csv" onChange={(e) => setCsvFile(e.target.files[0])} className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
          <button onClick={handleBulkUpload} className="bg-green-600 text-white px-6 py-2 rounded-xl font-bold hover:bg-green-700 shadow-lg shadow-green-200 whitespace-nowrap">
            Upload CSV
          </button>
        </div>
        <p className="text-xs text-slate-400 mt-4">
          <strong>Required Columns:</strong> first_name, surname, gender, class_assigned<br/>
          <strong>Optional:</strong> student_code (auto-generated if blank), guardian_name, parent_email
        </p>
      </div>

      {/* Class Promotion Override Section */}
      <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
        <h2 className="text-2xl font-bold text-slate-800 mb-2">📚 Promotion Override (Headmaster / Proprietor)</h2>
        <p className="text-sm text-slate-500 mb-6">Use this to override repetition and manually promote an individual student when necessary.</p>
        <form onSubmit={handlePromoteStudent} className="space-y-6">
          <div className="relative">
            <label className="block text-sm font-bold text-slate-700 mb-2">Search Student</label>
            <input 
              type="text"
              placeholder="Type student name to search..."
              value={searchQuery}
              onChange={(e) => handleSearchStudent(e.target.value)}
              className="w-full p-3 border rounded-lg bg-slate-50"
            />
            {searchResults.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-10 max-h-48 overflow-y-auto">
                {searchResults.map(student => (
                  <button
                    key={student.id}
                    type="button"
                    onClick={() => selectStudent(student)}
                    className="w-full text-left px-4 py-2 hover:bg-slate-100 border-b border-slate-100 last:border-b-0"
                  >
                    <div className="font-semibold text-slate-800">{student.name}</div>
                    <div className="text-xs text-slate-500">Current Class: {student.current_class} | ID: {student.student_code}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">New Class</label>
              <select name="new_class" value={promotionData.new_class} onChange={handlePromotionChange} className="w-full p-3 border rounded-lg bg-slate-50">
                {validGrades.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Remarks (Optional)</label>
              <input 
                type="text"
                name="remarks"
                value={promotionData.remarks}
                onChange={handlePromotionChange}
                placeholder="e.g., Promoted based on Term 3 performance"
                className="w-full p-3 border rounded-lg bg-slate-50"
              />
            </div>
          </div>

          <button type="submit" className="bg-indigo-600 text-white px-8 py-3 rounded-xl font-bold hover:bg-indigo-700 shadow-lg shadow-indigo-200 w-full md:w-auto">
            Promote Student
          </button>
        </form>
      </div>
    </div>
  );
}