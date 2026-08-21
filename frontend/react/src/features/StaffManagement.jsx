import React, { useState, useEffect } from 'react';
import axios from 'axios';

const DEFAULT_CLASSES = [
  'Nursery',
  'KG',
  'Class 1',
  'Class 2',
  'Class 3',
  'Class 4',
  'Class 5',
  'Class 6',
  'JHS 1',
  'JHS 2',
  'JHS 3',
  'SHS 1',
  'SHS 2',
  'SHS 3'
];

const DEFAULT_SUBJECTS = [
  'Mathematics',
  'English Language',
  'Science',
  'Social Studies',
  'Religious and Moral Education',
  'Ghanaian Language',
  'French',
  'ICT',
  'Creative Arts',
  'Physical Education',
  'History',
  'Geography',
  'Economics',
  'Physics',
  'Chemistry',
  'Biology',
  'Elective Mathematics'
];

export default function StaffManagement() {
  const [staffList, setStaffList] = useState([]);
  const [editingStaffId, setEditingStaffId] = useState(null);
  const [resendingInviteId, setResendingInviteId] = useState(null);
  const [availableClasses, setAvailableClasses] = useState(DEFAULT_CLASSES);
  const [availableSubjects, setAvailableSubjects] = useState(DEFAULT_SUBJECTS);
  const [customSubject, setCustomSubject] = useState('');
  const [customSubjectEdit, setCustomSubjectEdit] = useState('');
  const [csvFile, setCsvFile] = useState(null);
  const [editForm, setEditForm] = useState({ 
    roles: ['teacher'], 
    assigned_class: '',
    assigned_classes: [],
    assigned_subjects: []
  });
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    roles: ['teacher'],
    assigned_class: '',
    assigned_classes: [],
    assigned_subjects: []
  });

  const roleOptions = [
    { value: 'teacher', label: 'Subject Teacher' },
    { value: 'homeroom', label: 'Homeroom Teacher' },
    { value: 'headmaster', label: 'Headmaster' },
    { value: 'finance', label: 'Finance Officer' },
    { value: 'inventory_manager', label: 'Store Manager' }
  ];

  const roleLabelMap = Object.fromEntries(roleOptions.map((option) => [option.value, option.label]));

  const formatRoleLabels = (roles) => roles.map((role) => roleLabelMap[role] || role).join(', ');

  const renderHomeroomClassPicker = (selectedClass, onSelect, inputName) => (
    <div>
      <label className="text-xs font-bold text-slate-600 block mb-2">Homeroom Class Assignment</label>
      <div className="border rounded-lg p-3 bg-white max-h-40 overflow-y-auto">
        {availableClasses.length > 0 ? (
          availableClasses.map((cls) => (
            <label key={cls} className="flex items-center gap-2 text-sm mb-2">
              <input
                type="radio"
                name={inputName}
                checked={selectedClass === cls}
                onChange={() => onSelect(cls)}
                required
              />
              {cls}
            </label>
          ))
        ) : (
          <p className="text-xs text-slate-500 italic">No classes available</p>
        )}
      </div>
    </div>
  );

  const normalizeRoleSelection = (roles, toggledRole) => {
    const nextRoles = roles.includes(toggledRole)
      ? roles.filter((role) => role !== toggledRole)
      : [...roles, toggledRole];

    if (toggledRole === 'teacher' && !roles.includes('teacher')) {
      return nextRoles.filter((role) => role !== 'homeroom');
    }

    if (toggledRole === 'homeroom' && !roles.includes('homeroom')) {
      return nextRoles.filter((role) => role !== 'teacher');
    }

    return nextRoles;
  };

  const getAuthHeaders = () => ({
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  useEffect(() => {
    fetchStaff();
    fetchAvailableData();
  }, []);

  const fetchAvailableData = async () => {
    try {
      // Try to get classes from timetable and merge with defaults
      const timetableRes = await axios.get('/api/timetable', getAuthHeaders());
      const timetableClasses = [...new Set(timetableRes.data.map(entry => entry.class_name))].filter(Boolean);
      const timetableSubjects = [...new Set(timetableRes.data.map(entry => entry.subject_name))].filter(Boolean);
      
      // Merge with defaults and sort
      const mergedClasses = [...new Set([...DEFAULT_CLASSES, ...timetableClasses])].sort();
      const mergedSubjects = [...new Set([...DEFAULT_SUBJECTS, ...timetableSubjects])].sort();
      
      setAvailableClasses(mergedClasses);
      setAvailableSubjects(mergedSubjects);
    } catch (err) {
      console.error('Failed to fetch available data, using defaults');
      setAvailableClasses(DEFAULT_CLASSES);
      setAvailableSubjects(DEFAULT_SUBJECTS);
    }
  };

  const fetchStaff = async () => {
    try {
      const res = await axios.get('/api/staff/list', getAuthHeaders());
      setStaffList(res.data);
    } catch (err) {
      console.error("Failed to fetch staff");
    }
  };

  const handleInputChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (formData.roles.includes('homeroom') && !formData.assigned_class.trim()) {
      alert('Homeroom teachers must have an assigned homeroom class.');
      return;
    }
    try {
      await axios.post('/api/staff/add', formData, getAuthHeaders());
      alert("Staff member added successfully!");
      setFormData({ 
        username: '', 
        email: '', 
        roles: ['teacher'], 
        assigned_class: '',
        assigned_classes: [],
        assigned_subjects: []
      });
      fetchStaff();
    } catch (err) {
      alert(err.response?.data?.message || "Failed to add staff.");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to remove this staff member?")) return;
    try {
      await axios.delete(`/api/staff/${id}`, getAuthHeaders());
      fetchStaff();
    } catch (err) {
      alert("Failed to delete staff.");
    }
  };

  const handleResendInvite = async (staff) => {
    if (!staff.email) {
      alert('This staff account does not have an email address on file.');
      return;
    }

    if (!window.confirm(`Resend invite to ${staff.username}? This will issue a fresh temporary password and require a password change on next login.`)) {
      return;
    }

    try {
      setResendingInviteId(staff.id);
      const res = await axios.post(`/api/staff/${staff.id}/resend-invite`, {}, getAuthHeaders());
      alert(res.data?.message || 'Staff invite resent successfully.');
      fetchStaff();
    } catch (err) {
      alert(err.response?.data?.message || 'Failed to resend staff invite.');
    } finally {
      setResendingInviteId(null);
    }
  };



  const openEdit = (staff) => {
    setEditingStaffId(staff.id);
    setEditForm({
      roles: (staff.roles || [staff.role || 'teacher']).filter(
        (role, index, roles) => !(role === 'teacher' && roles.includes('homeroom')) && roles.indexOf(role) === index
      ),
      assigned_class: staff.assigned_class || '',
      assigned_classes: staff.assigned_classes || [],
      assigned_subjects: staff.assigned_subjects || []
    });
  };

  const cancelEdit = () => {
    setEditingStaffId(null);
    setEditForm({ 
      roles: ['teacher'], 
      assigned_class: '',
      assigned_classes: [],
      assigned_subjects: []
    });
  };

  const saveEdit = async (staffId) => {
    if (editForm.roles.includes('homeroom') && !editForm.assigned_class.trim()) {
      alert('Homeroom teachers must have an assigned homeroom class.');
      return;
    }
    try {
      await axios.put(`/api/staff/${staffId}`, editForm, getAuthHeaders());
      alert("Staff member updated successfully!");
      setEditingStaffId(null);
      fetchStaff();
    } catch (err) {
      alert(err.response?.data?.message || "Failed to update staff.");
    }
  };

  return (
    <div className="p-8 bg-white rounded-3xl shadow-sm border border-slate-100">
      <h2 className="text-2xl font-bold text-slate-800 mb-6">Staff Management</h2>
      
      {/* Add Staff Form */}
      <form onSubmit={handleSubmit} className="mb-8 bg-slate-50 p-6 rounded-xl border border-slate-200">
        <h3 className="font-bold text-slate-700 mb-4">Add New Staff Member</h3>
        <p className="text-xs text-slate-500 mb-4">
          A temporary password is auto-generated and sent to the staff email. It expires in 30 days and must be reset after first login.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <input 
            name="username" 
            placeholder="Username / Staff ID" 
            value={formData.username}
            onChange={handleInputChange}
            className="p-3 border rounded-lg"
            required 
          />
          <input 
            name="email" 
            type="email"
            placeholder="Email Address (required)" 
            value={formData.email}
            onChange={handleInputChange}
            className="p-3 border rounded-lg"
            required 
          />
          <div className="col-span-1 md:col-span-2">
            <p className="text-xs font-bold text-slate-600 mb-2">Assign Roles</p>
            <p className="text-xs text-slate-500 mb-3">Homeroom teachers already have subject-teacher access, so those two roles cannot be combined.</p>
            <div className="flex flex-wrap gap-3">
              {roleOptions.map((opt) => (
                <label key={opt.value} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.roles.includes(opt.value)}
                    onChange={() => {
                      const nextRoles = normalizeRoleSelection(formData.roles, opt.value);
                      setFormData({
                        ...formData,
                        roles: nextRoles,
                        assigned_class: nextRoles.includes('homeroom') ? formData.assigned_class : ''
                      });
                    }}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>
          {formData.roles.includes('homeroom') && (
            <div className="col-span-1 md:col-span-2 border-t pt-3">
              {renderHomeroomClassPicker(
                formData.assigned_class,
                (selectedClass) => setFormData({ ...formData, assigned_class: selectedClass }),
                'new-homeroom-class'
              )}
            </div>
          )}
          {(formData.roles.includes('teacher') || formData.roles.includes('homeroom')) && (
            <div className="col-span-1 md:col-span-2 space-y-3 border-t pt-3">
              <div>
                <label className="text-xs font-bold text-slate-600 block mb-2">Classes to Teach</label>
                <div className="border rounded-lg p-3 bg-white max-h-40 overflow-y-auto">
                  {availableClasses.length > 0 ? (
                    availableClasses.map((cls) => (
                      <label key={cls} className="flex items-center gap-2 text-sm mb-2">
                        <input
                          type="checkbox"
                          checked={formData.assigned_classes.includes(cls)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setFormData({
                                ...formData,
                                assigned_classes: [...formData.assigned_classes, cls].sort()
                              });
                            } else {
                              setFormData({
                                ...formData,
                                assigned_classes: formData.assigned_classes.filter(c => c !== cls)
                              });
                            }
                          }}
                        />
                        {cls}
                      </label>
                    ))
                  ) : (
                    <p className="text-xs text-slate-500 italic">No classes available</p>
                  )}
                </div>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-600 block mb-2">Subjects to Teach</label>
                <div className="border rounded-lg p-3 bg-white max-h-40 overflow-y-auto">
                  {availableSubjects.length > 0 ? (
                    availableSubjects.map((subj) => (
                      <label key={subj} className="flex items-center gap-2 text-sm mb-2">
                        <input
                          type="checkbox"
                          checked={formData.assigned_subjects.includes(subj)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setFormData({
                                ...formData,
                                assigned_subjects: [...formData.assigned_subjects, subj].sort()
                              });
                            } else {
                              setFormData({
                                ...formData,
                                assigned_subjects: formData.assigned_subjects.filter(s => s !== subj)
                              });
                            }
                          }}
                        />
                        {subj}
                      </label>
                    ))
                  ) : (
                    <p className="text-xs text-slate-500 italic">No subjects available</p>
                  )}
                </div>
                <div className="mt-2 flex gap-2">
                  <input
                    type="text"
                    placeholder="Add custom subject..."
                    value={customSubject}
                    onChange={(e) => setCustomSubject(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter' && customSubject.trim()) {
                        e.preventDefault();
                        const newSubject = customSubject.trim();
                        if (!formData.assigned_subjects.includes(newSubject)) {
                          setFormData({
                            ...formData,
                            assigned_subjects: [...formData.assigned_subjects, newSubject].sort()
                          });
                          if (!availableSubjects.includes(newSubject)) {
                            setAvailableSubjects([...availableSubjects, newSubject].sort());
                          }
                        }
                        setCustomSubject('');
                      }
                    }}
                    className="flex-1 p-2 border rounded-lg text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const newSubject = customSubject.trim();
                      if (newSubject && !formData.assigned_subjects.includes(newSubject)) {
                        setFormData({
                          ...formData,
                          assigned_subjects: [...formData.assigned_subjects, newSubject].sort()
                        });
                        if (!availableSubjects.includes(newSubject)) {
                          setAvailableSubjects([...availableSubjects, newSubject].sort());
                        }
                        setCustomSubject('');
                      }
                    }}
                    className="px-3 py-2 bg-blue-600 text-white rounded-lg text-xs font-bold hover:bg-blue-700"
                  >
                    Add
                  </button>
                </div>
                {formData.assigned_subjects.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs text-slate-600 font-bold mb-1">Selected Subjects:</p>
                    <div className="flex flex-wrap gap-1">
                      {formData.assigned_subjects.map((subj) => (
                        <span
                          key={subj}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs"
                        >
                          {subj}
                          <button
                            type="button"
                            onClick={() => {
                              setFormData({
                                ...formData,
                                assigned_subjects: formData.assigned_subjects.filter(s => s !== subj)
                              });
                            }}
                            className="text-blue-600 hover:text-blue-900 font-bold"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
        <button type="submit" className="bg-blue-900 text-white px-6 py-2 rounded-lg font-bold hover:bg-blue-800">
          Add Staff
        </button>
      </form>



      {/* Staff List */}
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="bg-slate-100 text-slate-600 font-bold uppercase text-xs">
            <tr>
              <th className="p-4">Staff ID</th>
              <th className="p-4">Email</th>
              <th className="p-4">Role</th>
              <th className="p-4">Homeroom</th>
              <th className="p-4">Teaching Classes</th>
              <th className="p-4">Teaching Subjects</th>
              <th className="p-4">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {staffList.map(staff => (
              <tr key={staff.id} className="hover:bg-slate-50">
                <td className="p-4 font-bold text-slate-700">{staff.username}</td>
                <td className="p-4 text-sm text-slate-500">{staff.email || 'N/A'}</td>
                <td className="p-4 capitalize">
                  {editingStaffId === staff.id ? (
                    <div className="flex flex-col gap-1">
                      <p className="text-[11px] text-slate-500 mb-1">Homeroom and Subject Teacher cannot both be selected.</p>
                      {roleOptions.map((opt) => (
                        <label key={opt.value} className="flex items-center gap-2 text-xs">
                          <input
                            type="checkbox"
                            checked={editForm.roles.includes(opt.value)}
                            onChange={() => {
                              const nextRoles = normalizeRoleSelection(editForm.roles, opt.value);
                              setEditForm({
                                ...editForm,
                                roles: nextRoles,
                                assigned_class: nextRoles.includes('homeroom') ? editForm.assigned_class : ''
                              });
                            }}
                          />
                          {opt.label}
                        </label>
                      ))}
                    </div>
                  ) : (
                    formatRoleLabels(staff.roles || [staff.role])
                  )}
                </td>
                <td className="p-4">
                  {editingStaffId === staff.id ? (
                    editForm.roles.includes('homeroom') ? (
                      <div className="min-w-44">
                        {renderHomeroomClassPicker(
                          editForm.assigned_class,
                          (selectedClass) => setEditForm({ ...editForm, assigned_class: selectedClass }),
                          `edit-homeroom-class-${staff.id}`
                        )}
                      </div>
                    ) : (
                      <span className="text-slate-400 text-sm">-</span>
                    )
                  ) : (
                    staff.assigned_class || '-'
                  )}
                </td>
                <td className="p-4 text-sm">
                  {editingStaffId === staff.id ? (
                    (editForm.roles.includes('teacher') || editForm.roles.includes('homeroom')) ? (
                      <div className="border rounded-lg p-2 bg-white max-h-32 overflow-y-auto">
                        {availableClasses.map((cls) => (
                          <label key={cls} className="flex items-center gap-2 text-xs mb-1">
                            <input
                              type="checkbox"
                              checked={editForm.assigned_classes.includes(cls)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setEditForm({
                                    ...editForm,
                                    assigned_classes: [...editForm.assigned_classes, cls].sort()
                                  });
                                } else {
                                  setEditForm({
                                    ...editForm,
                                    assigned_classes: editForm.assigned_classes.filter(c => c !== cls)
                                  });
                                }
                              }}
                            />
                            {cls}
                          </label>
                        ))}
                      </div>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )
                  ) : (
                    (staff.assigned_classes || []).join(', ') || '-'
                  )}
                </td>
                <td className="p-4 text-sm">
                  {editingStaffId === staff.id ? (
                    (editForm.roles.includes('teacher') || editForm.roles.includes('homeroom')) ? (
                      <div>
                        <div className="border rounded-lg p-2 bg-white max-h-24 overflow-y-auto mb-1">
                          {availableSubjects.map((subj) => (
                            <label key={subj} className="flex items-center gap-2 text-xs mb-1">
                              <input
                                type="checkbox"
                                checked={editForm.assigned_subjects.includes(subj)}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setEditForm({
                                      ...editForm,
                                      assigned_subjects: [...editForm.assigned_subjects, subj].sort()
                                    });
                                  } else {
                                    setEditForm({
                                      ...editForm,
                                      assigned_subjects: editForm.assigned_subjects.filter(s => s !== subj)
                                    });
                                  }
                                }}
                              />
                              {subj}
                            </label>
                          ))}
                        </div>
                        <div className="flex gap-1">
                          <input
                            type="text"
                            placeholder="Add custom..."
                            value={customSubjectEdit}
                            onChange={(e) => setCustomSubjectEdit(e.target.value)}
                            onKeyPress={(e) => {
                              if (e.key === 'Enter' && customSubjectEdit.trim()) {
                                e.preventDefault();
                                const newSubject = customSubjectEdit.trim();
                                if (!editForm.assigned_subjects.includes(newSubject)) {
                                  setEditForm({
                                    ...editForm,
                                    assigned_subjects: [...editForm.assigned_subjects, newSubject].sort()
                                  });
                                  if (!availableSubjects.includes(newSubject)) {
                                    setAvailableSubjects([...availableSubjects, newSubject].sort());
                                  }
                                }
                                setCustomSubjectEdit('');
                              }
                            }}
                            className="flex-1 p-1 border rounded text-xs"
                          />
                          <button
                            type="button"
                            onClick={() => {
                              const newSubject = customSubjectEdit.trim();
                              if (newSubject && !editForm.assigned_subjects.includes(newSubject)) {
                                setEditForm({
                                  ...editForm,
                                  assigned_subjects: [...editForm.assigned_subjects, newSubject].sort()
                                });
                                if (!availableSubjects.includes(newSubject)) {
                                  setAvailableSubjects([...availableSubjects, newSubject].sort());
                                }
                                setCustomSubjectEdit('');
                              }
                            }}
                            className="px-2 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700"
                          >
                            +
                          </button>
                        </div>
                      </div>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )
                  ) : (
                    (staff.assigned_subjects || []).join(', ') || '-'
                  )}
                </td>
                <td className="p-4">
                  {editingStaffId === staff.id ? (
                    <div className="flex gap-2">
                      <button
                        onClick={() => saveEdit(staff.id)}
                        className="text-green-700 font-bold hover:underline"
                      >
                        Save
                      </button>
                      <button
                        onClick={cancelEdit}
                        className="text-slate-500 font-bold hover:underline"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="flex gap-4">
                      <button
                        onClick={() => handleResendInvite(staff)}
                        className="text-amber-700 font-bold hover:underline disabled:text-slate-400 disabled:no-underline"
                        disabled={resendingInviteId === staff.id}
                      >
                        {resendingInviteId === staff.id ? 'Sending...' : 'Resend Invite'}
                      </button>
                      <button
                        onClick={() => openEdit(staff)}
                        className="text-blue-600 font-bold hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(staff.id)}
                        className="text-red-500 font-bold hover:underline"
                      >
                        Remove
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}