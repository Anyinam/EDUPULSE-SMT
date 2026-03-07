import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function ProfileSettings() {
  const [profile, setProfile] = useState({ username: '', email: '', role: '', profile_picture: '' });
  const [form, setForm] = useState({ email: '', password: '', profile_picture: '' });
  const [devMode, setDevMode] = useState(localStorage.getItem('dev_mode') === 'true');
  const [uploadMessage, setUploadMessage] = useState('');
  const [uploading, setUploading] = useState(false);
  
  const isDeveloper = (
    window.location.hostname === 'localhost' || 
    window.location.hostname === '127.0.0.1' ||
    profile.role === 'super-admin'
  );

  const getAuthHeaders = () => ({
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await axios.get('/api/profile', getAuthHeaders());
        setProfile(res.data);
        setForm(prev => ({ ...prev, email: res.data.email || '' }));
      } catch (err) {
        console.error("Failed to load profile");
      }
    };
    fetchProfile();
  }, []);

  const handleProfilePictureChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    setUploadMessage('');
    const isAllowed = ['image/png', 'image/jpeg', 'image/jpg'].includes(file.type);
    if (!isAllowed) {
      setUploadMessage('❌ Only PNG or JPG images allowed');
      return;
    }

    const maxBytes = 5 * 1024 * 1024;
    if (file.size > maxBytes) {
      setUploadMessage('❌ Image must be 5MB or smaller');
      return;
    }

    setUploading(true);
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const maxDimension = 300; // Profile pic size
        let width = img.width;
        let height = img.height;

        if (width > height) {
          if (width > maxDimension) {
            height = Math.round((height * maxDimension) / width);
            width = maxDimension;
          }
        } else {
          if (height > maxDimension) {
            width = Math.round((width * maxDimension) / height);
            height = maxDimension;
          }
        }

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);

        const compressed = canvas.toDataURL('image/jpeg', 0.85);
        setForm(prev => ({ ...prev, profile_picture: compressed }));
        setProfile(prev => ({ ...prev, profile_picture: compressed }));
        setUploadMessage('✅ Image ready to save');
        setUploading(false);
      };
      img.onerror = () => {
        setUploadMessage('❌ Failed to process image');
        setUploading(false);
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    try {
      const updateData = { email: form.email };
      if (form.password) updateData.password = form.password;
      if (form.profile_picture) updateData.profile_picture = form.profile_picture;
      
      await axios.post('/api/profile/update', updateData, getAuthHeaders());
      alert("Profile updated successfully!");
      setForm(prev => ({ ...prev, password: '' })); // Clear password field
      setUploadMessage('');
    } catch (err) {
      alert("Failed to update profile.");
    }
  };

  const toggleDevMode = () => {
    const newDevMode = !devMode;
    setDevMode(newDevMode);
    if (newDevMode) {
      localStorage.setItem('dev_mode', 'true');
    } else {
      localStorage.removeItem('dev_mode');
    }
    // Reload to apply changes
    window.location.reload();
  };

  return (
    <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100 max-w-2xl">
      <h2 className="text-2xl font-bold text-slate-800 mb-6">My Profile Settings</h2>
      
      <div className="mb-8 p-4 bg-slate-50 rounded-xl border border-slate-200 flex items-center gap-4">
        <div className="relative">
          {profile.profile_picture ? (
            <img 
              src={profile.profile_picture} 
              alt="Profile" 
              className="w-16 h-16 rounded-full object-cover border-2 border-blue-500"
            />
          ) : (
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center text-2xl">👤</div>
          )}
          <label className="absolute bottom-0 right-0 bg-blue-600 text-white rounded-full p-1 cursor-pointer hover:bg-blue-700 shadow-lg">
            <input 
              type="file" 
              accept="image/png,image/jpeg,image/jpg" 
              onChange={handleProfilePictureChange}
              className="hidden"
            />
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </label>
        </div>
        <div className="flex-1">
          <p className="font-bold text-slate-800">{profile.username}</p>
          <p className="text-xs text-slate-500 uppercase font-bold">{profile.role}</p>
          {uploadMessage && (
            <p className={`text-xs mt-1 ${uploadMessage.includes('✅') ? 'text-green-600' : 'text-red-600'}`}>
              {uploadMessage}
            </p>
          )}
        </div>
      </div>

      <form onSubmit={handleUpdate} className="space-y-6">
        <div>
          <label className="block text-sm font-bold text-slate-700 mb-2">Email Address</label>
          <input 
            type="email" 
            value={form.email} 
            onChange={e => setForm({...form, email: e.target.value})} 
            className="w-full p-3 border rounded-lg bg-white focus:ring-2 focus:ring-blue-500 outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-bold text-slate-700 mb-2">New Password (Optional)</label>
          <input 
            type="password" 
            value={form.password} 
            onChange={e => setForm({...form, password: e.target.value})} 
            placeholder="Leave blank to keep current password"
            className="w-full p-3 border rounded-lg bg-white focus:ring-2 focus:ring-blue-500 outline-none"
          />
        </div>
        <button className="bg-blue-900 text-white px-8 py-3 rounded-xl font-bold hover:bg-blue-800 shadow-lg">
          Update Profile
        </button>
      </form>

    </div>
  );
}