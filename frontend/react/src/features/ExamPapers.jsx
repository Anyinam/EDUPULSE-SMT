import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useBranding } from '../hooks/useBranding';

/**
 * Exam Paper Editor - For teachers to create and manage exam question papers
 * Features:
 * - Create exam papers with multiple question types
 * - AI-assisted question generation
 * - Print-friendly format
 * - Save as draft or finalize
 */
export default function ExamPapers() {
  const { branding } = useBranding({ refreshOnMount: true });
  const MAX_IMAGE_UPLOAD_BYTES = 8 * 1024 * 1024;
  const MAX_COMPRESSED_IMAGE_BYTES = 2 * 1024 * 1024;
  const currentPlan = localStorage.getItem('subscription_plan') || 'Free Tier';
  const isPremiumPlan = currentPlan === 'Premium';
  
  // State management
  const [papers, setPapers] = useState([]);
  const [selectedPaper, setSelectedPaper] = useState(null);
  const [isEditor, setIsEditor] = useState(false);
  const [loading, setLoading] = useState(false);
  
  // Form state for new/edit paper
  const [paperData, setPaperData] = useState({
    title: '',
    class_name: '',
    subject_name: '',
    academic_term: 'Term 1',
    academic_year: '2025/2026',
    exam_type: 'Mid-Term',
    instructions: 'Read all instructions carefully before answering.',
    total_marks: 100,
    duration_minutes: 120,
    questions: [],
    status: 'draft'
  });
  
  // Question template
  const [newQuestion, setNewQuestion] = useState({
    type: 'mcq',
    question: '',
    options: ['', '', '', ''],
    correct_answer: '',
    marks: 2,
    section: 'A',
    image_url: ''
  });
  
  // AI Assistant state
  const [aiPrompt, setAiPrompt] = useState({
    topic: '',
    difficulty: 'medium',
    question_type: 'mcq',
    count: 5,
    teacher_instructions: ''
  });
  const [aiGeneratedPrompt, setAiGeneratedPrompt] = useState('');
  const [showAiDialog, setShowAiDialog] = useState(false);
  const [assignedClasses, setAssignedClasses] = useState([]);
  const [assignedSubjects, setAssignedSubjects] = useState([]);
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  const [hasLocalDraft, setHasLocalDraft] = useState(false);
  const [localDraftMeta, setLocalDraftMeta] = useState(null);
  const [saveState, setSaveState] = useState('idle');
  const [imageProcessing, setImageProcessing] = useState(false);
  const [imageDropActive, setImageDropActive] = useState(false);
  
  // Auth headers
  const getAuthHeaders = () => ({
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  const getLocalDraftKey = () => {
    const schoolId = localStorage.getItem('school_id') || 'school';
    const userKey = localStorage.getItem('user_id') || localStorage.getItem('username') || 'user';
    return `exam_paper_draft_${schoolId}_${userKey}`;
  };

  const clearLocalDraft = () => {
    localStorage.removeItem(getLocalDraftKey());
    setHasLocalDraft(false);
    setLocalDraftMeta(null);
  };

  const hydrateLocalDraftState = () => {
    try {
      const raw = localStorage.getItem(getLocalDraftKey());
      if (!raw) {
        setHasLocalDraft(false);
        setLocalDraftMeta(null);
        return null;
      }
      const parsed = JSON.parse(raw);
      setHasLocalDraft(true);
      setLocalDraftMeta(parsed?.savedAt || null);
      return parsed;
    } catch (error) {
      console.error('Failed to read local exam draft', error);
      setHasLocalDraft(false);
      setLocalDraftMeta(null);
      return null;
    }
  };
  
  // Fetch exam papers
  useEffect(() => {
    fetchPapers();
    fetchAssignments();
    hydrateLocalDraftState();

    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    if (!isEditor) return;

    const hasUsefulContent = Boolean(
      (paperData.title || '').trim() ||
      (paperData.instructions || '').trim() ||
      (paperData.questions || []).length > 0
    );

    if (!hasUsefulContent) return;

    const timer = setTimeout(() => {
      const payload = {
        paperData,
        selectedPaperId: selectedPaper?.id || null,
        savedAt: new Date().toISOString(),
      };
      localStorage.setItem(getLocalDraftKey(), JSON.stringify(payload));
      setHasLocalDraft(true);
      setLocalDraftMeta(payload.savedAt);
      setSaveState('local');
    }, 800);

    return () => clearTimeout(timer);
  }, [isEditor, paperData, selectedPaper]);

  const fetchAssignments = async () => {
    try {
      const res = await axios.get('/api/teacher/assignments', getAuthHeaders());
      const classes = Array.isArray(res.data?.assigned_classes) ? res.data.assigned_classes : [];
      const subjects = Array.isArray(res.data?.assigned_subjects) ? res.data.assigned_subjects : [];
      setAssignedClasses(classes);
      setAssignedSubjects(subjects);

      setPaperData((prev) => ({
        ...prev,
        class_name: prev.class_name || (classes[0] || ''),
        subject_name: prev.subject_name || (subjects[0] || '')
      }));
    } catch (err) {
      console.error('Failed to load teacher assignments for exam papers', err);
      setAssignedClasses([]);
      setAssignedSubjects([]);
    }
  };
  
  const fetchPapers = async () => {
    try {
      setLoading(true);
      const res = await axios.get('/api/exams/papers', getAuthHeaders());
      setPapers(res.data);
    } catch (err) {
      console.error('Failed to fetch exam papers:', err);
      alert('Error loading exam papers');
    } finally {
      setLoading(false);
    }
  };
  
  const createNewPaper = () => {
    setPaperData({
      title: '',
      class_name: '',
      subject_name: '',
      academic_term: 'Term 1',
      academic_year: '2025/2026',
      exam_type: 'Mid-Term',
      instructions: 'Read all instructions carefully before answering.',
      total_marks: 100,
      duration_minutes: 120,
      questions: [],
      status: 'draft'
    });
    setSelectedPaper(null);
    setIsEditor(true);
    setSaveState('idle');
  };

  const restoreLocalDraft = () => {
    const draft = hydrateLocalDraftState();
    if (!draft?.paperData) {
      alert('No local draft found.');
      return;
    }

    setPaperData({
      ...draft.paperData,
      status: draft.paperData?.status || 'draft',
    });
    if (draft.selectedPaperId) {
      setSelectedPaper({ id: draft.selectedPaperId });
    } else {
      setSelectedPaper(null);
    }
    setIsEditor(true);
    setSaveState('local');
  };
  
  const loadPaper = async (paperId) => {
    try {
      const res = await axios.get(`/api/exams/papers/${paperId}`, getAuthHeaders());
      setPaperData(res.data);
      setSelectedPaper(res.data);
      setIsEditor(true);
    } catch (err) {
      console.error('Failed to load paper:', err);
      alert('Error loading exam paper');
    }
  };
  
  const savePaper = async (statusOverride = null, silent = false) => {
    try {
      if (isOffline) {
        setSaveState('local');
        if (!silent) {
          alert('You are offline. Draft is saved locally and will remain available when you return.');
        }
        return selectedPaper?.id || paperData?.id || null;
      }

      if (!paperData.title || !paperData.class_name || !paperData.subject_name) {
        if (!silent) alert('Please fill in title, class, and subject');
        return null;
      }
      
      setLoading(true);
      setSaveState('saving');
      const payload = {
        ...paperData,
        status: statusOverride || paperData.status || 'draft'
      };
      
      if (selectedPaper?.id) {
        // Update existing
        await axios.put(`/api/exams/papers/${selectedPaper.id}`, payload, getAuthHeaders());
        setPaperData((prev) => ({ ...prev, status: payload.status }));
        if (!silent) alert('Exam paper saved successfully!');
        setSaveState('saved');
        fetchPapers();
        return selectedPaper.id;
      } else {
        // Create new
        const res = await axios.post('/api/exams/papers', payload, getAuthHeaders());
        const paperId = res.data.paper_id;
        const selected = { id: paperId };
        setSelectedPaper(selected);
        setPaperData((prev) => ({ ...prev, id: paperId, status: payload.status }));
        if (!silent) alert('Exam paper saved successfully!');
        setSaveState('saved');
        fetchPapers();
        return paperId;
      }
    } catch (err) {
      console.error('Failed to save paper:', err);
      setSaveState('error');
      if (!silent) alert('Error saving exam paper: ' + (err.response?.data?.message || err.message));
      return null;
    } finally {
      setLoading(false);
    }
  };

  const submitPaper = async (submitTo) => {
    try {
      let paperId = selectedPaper?.id || paperData?.id;
      if (!paperId) {
        paperId = await savePaper('draft', true);
      }

      if (!paperId) {
        alert('Please save draft first before submitting.');
        return;
      }

      const res = await axios.post(
        `/api/exams/papers/${paperId}/submit`,
        { submit_to: submitTo },
        getAuthHeaders()
      );

      setPaperData((prev) => ({ ...prev, status: res.data?.paper_status || `submitted_${submitTo}` }));
      clearLocalDraft();
      setSaveState('submitted');
      alert(res.data?.message || `Submitted to ${submitTo}.`);
      fetchPapers();
    } catch (err) {
      console.error('Failed to submit paper', err);
      alert('Submit failed: ' + (err.response?.data?.message || err.message));
    }
  };
  
  const deletePaper = async (paperId) => {
    if (!confirm('Are you sure you want to delete this exam paper?')) return;
    
    try {
      await axios.delete(`/api/exams/papers/${paperId}`, getAuthHeaders());
      alert('Exam paper deleted successfully!');
      fetchPapers();
      if (selectedPaper?.id === paperId) {
        setIsEditor(false);
        setSelectedPaper(null);
      }
    } catch (err) {
      console.error('Failed to delete paper:', err);
      alert('Error deleting exam paper');
    }
  };
  
  const addQuestion = () => {
    if (!newQuestion.question) {
      alert('Please enter a question');
      return;
    }
    
    setPaperData({
      ...paperData,
      questions: [...paperData.questions, { ...newQuestion, id: Date.now() }],
      total_marks: paperData.total_marks + (parseInt(newQuestion.marks) || 0)
    });
    
    // Reset question form
    setNewQuestion({
      type: 'mcq',
      question: '',
      options: ['', '', '', ''],
      correct_answer: '',
      marks: 2,
      section: 'A',
      image_url: ''
    });
  };

  const compressImageFile = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const maxWidth = 1200;
        const scale = img.width > maxWidth ? maxWidth / img.width : 1;
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          reject(new Error('Could not initialize image canvas.'));
          return;
        }
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/jpeg', 0.82));
      };
      img.onerror = () => reject(new Error('Failed to load image for compression.'));
      img.src = String(reader.result || '');
    };
    reader.onerror = () => reject(new Error('Failed to read image file.'));
    reader.readAsDataURL(file);
  });

  const estimateDataUrlSizeBytes = (dataUrl) => {
    const parts = String(dataUrl || '').split(',');
    if (parts.length < 2) return 0;
    const base64 = parts[1];
    return Math.floor((base64.length * 3) / 4);
  };

  const setQuestionImageFromFile = async (file) => {
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      alert('Please select a valid image file.');
      return;
    }

    if (file.size > MAX_IMAGE_UPLOAD_BYTES) {
      alert('Image is too large. Please choose an image under 8MB.');
      return;
    }

    try {
      setImageProcessing(true);
      const compressedImage = await compressImageFile(file);
      const compressedBytes = estimateDataUrlSizeBytes(compressedImage);
      if (compressedBytes > MAX_COMPRESSED_IMAGE_BYTES) {
        alert('Compressed image is still too large. Please use a smaller image (ideally under 2MB).');
        return;
      }
      setNewQuestion((prev) => ({
        ...prev,
        image_url: String(compressedImage || '')
      }));
    } catch (error) {
      console.error('Failed to process image', error);
      alert('Could not process the image. Please try another file.');
    } finally {
      setImageProcessing(false);
      setImageDropActive(false);
    }
  };

  const handleQuestionImageFile = (event) => {
    const file = event.target.files?.[0];
    setQuestionImageFromFile(file);
    event.target.value = '';
  };

  const handleImageDrop = (event) => {
    event.preventDefault();
    event.stopPropagation();
    const file = event.dataTransfer?.files?.[0];
    setQuestionImageFromFile(file);
  };

  const handleQuestionTextPaste = (event) => {
    const files = event.clipboardData?.files;
    if (!files || files.length === 0) return;
    const file = files[0];
    if (!file.type.startsWith('image/')) return;
    event.preventDefault();
    setQuestionImageFromFile(file);
  };
  
  const removeQuestion = (questionId) => {
    const question = paperData.questions.find(q => q.id === questionId);
    setPaperData({
      ...paperData,
      questions: paperData.questions.filter(q => q.id !== questionId),
      total_marks: paperData.total_marks - (parseInt(question?.marks) || 0)
    });
  };
  
  const printPaper = () => {
    const printWindow = window.open('', '_blank');
    const questionsHtml = paperData.questions.map((q, idx) => {
      let questionHtml = `<div style="margin-bottom: 20px;">
        <p><strong>Question ${idx + 1} (${q.marks} marks)</strong></p>
        <p>${q.question}</p>`;

      if (q.image_url) {
        questionHtml += `<div style="margin: 10px 0;"><img src="${q.image_url}" alt="Question diagram" style="max-width: 100%; max-height: 260px; border: 1px solid #ddd; border-radius: 6px;" /></div>`;
      }
      
      if (q.type === 'mcq' && q.options) {
        questionHtml += '<div style="margin-left: 20px;">';
        q.options.forEach((opt, i) => {
          if (opt) questionHtml += `<p>${String.fromCharCode(65 + i)}. ${opt}</p>`;
        });
        questionHtml += '</div>';
      } else if (q.type === 'short' || q.type === 'essay') {
        questionHtml += '<div style="border-bottom: 1px dotted #ccc; margin: 10px 0 20px 0; height: 100px;"></div>';
      }
      
      questionHtml += '</div>';
      return questionHtml;
    }).join('');
    
    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>${paperData.title}</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 40px; line-height: 1.6; }
          .header { text-align: center; margin-bottom: 30px; border-bottom: 2px solid #000; padding-bottom: 20px; }
          .header h1 { margin: 0; font-size: 24px; }
          .header h2 { margin: 10px 0; font-size: 18px; }
          .instructions { background: #f5f5f5; padding: 15px; margin: 20px 0; border-left: 4px solid #3b82f6; }
          @media print { body { padding: 20px; } }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>${branding.name || 'EduPulse SMT'}</h1>
          <h2>${paperData.title}</h2>
          <p><strong>Class:</strong> ${paperData.class_name} | <strong>Subject:</strong> ${paperData.subject_name}</p>
          <p><strong>Term:</strong> ${paperData.academic_term} ${paperData.academic_year} | <strong>Duration:</strong> ${paperData.duration_minutes} minutes | <strong>Total Marks:</strong> ${paperData.total_marks}</p>
          <div style="margin-top: 16px; text-align: left; display: grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; font-size: 14px;">
            <p><strong>Name:</strong> ____________________________</p>
            <p><strong>Student ID:</strong> _____________________</p>
            <p><strong>Date:</strong> ____________________________</p>
            <p><strong>Signature:</strong> ______________________</p>
          </div>
        </div>
        
        <div class="instructions">
          <strong>Instructions:</strong><br/>
          ${paperData.instructions}
        </div>
        
        <div class="questions">
          ${questionsHtml}
        </div>
        
        <div style="margin-top: 50px; text-align: center; font-size: 12px; color: #666;">
          ${branding.motto || ''}
        </div>
        
        <button onclick="window.print()" style="display: block; margin: 20px auto; padding: 10px 30px; background: #3b82f6; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">
          Print Exam Paper
        </button>
      </body>
      </html>
    `);
    printWindow.document.close();
  };
  
  const generateAiQuestions = async () => {
    if (!isPremiumPlan) {
      alert('AI Exam Assistant is available on Premium plan only.');
      return;
    }

    const promptText = `You are an experienced ${paperData.subject_name || 'school subject'} teacher. Create ${aiPrompt.count} ${aiPrompt.question_type.toUpperCase()} exam questions for ${paperData.class_name || 'the selected class'} on the topic: ${aiPrompt.topic || 'general revision'}.

Requirements:
- Difficulty level: ${aiPrompt.difficulty}
- Exam type: ${paperData.exam_type || 'Class Test'}
- Academic term/year: ${paperData.academic_term || 'Term 1'} ${paperData.academic_year || ''}
- Match curriculum level for ${paperData.class_name || 'the class'}
- Include clear marking guide per question
- Use concise, student-friendly language

Output format:
1) Question
2) Options A-D (for MCQ only)
3) Correct answer / marking scheme
4) Recommended marks

Teacher custom instructions:
${aiPrompt.teacher_instructions || 'None'}`;

    setAiGeneratedPrompt(promptText);

    try {
      const payload = {
        topic: aiPrompt.topic,
        difficulty: aiPrompt.difficulty,
        question_type: aiPrompt.question_type,
        count: aiPrompt.count,
        teacher_instructions: aiPrompt.teacher_instructions,
        class_name: paperData.class_name,
        subject_name: paperData.subject_name,
        exam_type: paperData.exam_type
      };

      const res = await axios.post('/api/exams/generate-questions', payload, getAuthHeaders());
      const generated = Array.isArray(res.data?.questions) ? res.data.questions : [];

      if (generated.length > 0) {
        const prepared = generated.map((q, idx) => ({
          id: Date.now() + idx,
          type: q.type || aiPrompt.question_type,
          question: q.question || '',
          options: Array.isArray(q.options) ? q.options : ['', '', '', ''],
          correct_answer: q.correct_answer || '',
          marks: Number(q.marks || (aiPrompt.question_type === 'mcq' ? 2 : 5)),
          section: q.section || 'A'
        }));

        setPaperData((prev) => ({
          ...prev,
          questions: [...prev.questions, ...prepared],
          total_marks: (prev.total_marks || 0) + prepared.reduce((sum, q) => sum + (Number(q.marks) || 0), 0)
        }));

        alert(`✅ Added ${prepared.length} AI-generated question(s). Provider: ${res.data?.provider || 'unknown'}`);
      } else {
        alert('AI did not return usable questions. You can still use the generated prompt manually.');
      }
    } catch (err) {
      console.error('AI generation failed', err);
      alert('AI generation failed. You can still use the generated prompt manually.');
    }
  };

  const copyAiPrompt = async () => {
    if (!aiGeneratedPrompt) return;
    try {
      await navigator.clipboard.writeText(aiGeneratedPrompt);
      alert('AI prompt copied. Paste it into your AI tool to generate questions quickly.');
    } catch (err) {
      console.error('Failed to copy prompt', err);
      alert('Could not copy automatically. Please select and copy manually.');
    }
  };
  
  if (!isEditor) {
    // List view
    return (
      <div className="p-8 bg-gray-50 min-h-screen">
        <header className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-blue-900">📝 Exam Question Papers</h1>
            <p className="text-gray-600">{branding.name || 'EduPulse SMT'} - Create & Manage Exams</p>
          </div>
          <button
            onClick={createNewPaper}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold"
          >
            + Create New Exam Paper
          </button>
        </header>

        {hasLocalDraft && (
          <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-amber-900">Unsynced local draft found</p>
              <p className="text-xs text-amber-800">Last saved: {localDraftMeta ? new Date(localDraftMeta).toLocaleString() : 'unknown time'}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={restoreLocalDraft}
                className="px-3 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 text-sm font-semibold"
              >
                Resume Draft
              </button>
              <button
                onClick={clearLocalDraft}
                className="px-3 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 text-sm font-semibold"
              >
                Discard
              </button>
            </div>
          </div>
        )}
        
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="mt-4 text-gray-600">Loading exam papers...</p>
          </div>
        ) : papers.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border p-12 text-center">
            <p className="text-gray-500 text-lg">No exam papers yet. Click "Create New Exam Paper" to get started!</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {papers.map(paper => (
              <div key={paper.id} className="bg-white rounded-xl shadow-sm border hover:shadow-md transition-shadow p-6">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-bold text-lg text-blue-900">{paper.title}</h3>
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    paper.status === 'finalized'
                      ? 'bg-green-100 text-green-800'
                      : String(paper.status || '').startsWith('submitted_')
                      ? 'bg-indigo-100 text-indigo-800'
                      : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    {paper.status === 'submitted_headmaster'
                      ? 'Submitted to Headmaster'
                      : paper.status === 'submitted_proprietor'
                      ? 'Submitted to Proprietor'
                      : paper.status}
                  </span>
                </div>
                
                <p className="text-sm text-gray-600 mb-2">
                  <strong>{paper.class_name}</strong> • {paper.subject_name}
                </p>
                
                <p className="text-sm text-gray-500 mb-4">
                  {paper.exam_type} • {paper.academic_term} {paper.academic_year}
                </p>
                
                <div className="flex items-center gap-2 text-sm text-gray-600 mb-4">
                  <span>📄 {paper.question_count} questions</span>
                  <span>•</span>
                  <span>⏱️ {paper.duration_minutes} min</span>
                  <span>•</span>
                  <span>💯 {paper.total_marks} marks</span>
                </div>
                
                <div className="flex gap-2">
                  <button
                    onClick={() => loadPaper(paper.id)}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-semibold"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => deletePaper(paper.id)}
                    className="px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors text-sm font-semibold"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }
  
  // Editor view
  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <header className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-blue-900">
            {selectedPaper ? 'Edit Exam Paper' : 'Create New Exam Paper'}
          </h1>
          <p className="text-gray-600">{branding.name || 'EduPulse SMT'}</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setIsEditor(false)}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
          >
            ← Back to List
          </button>
          <button
            onClick={() => savePaper('draft')}
            disabled={loading}
            className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-semibold"
          >
            {loading ? 'Saving...' : '💾 Save Draft'}
          </button>
          <button
            onClick={() => savePaper('finalized')}
            disabled={loading}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold"
          >
            ✅ Finalize
          </button>
          <button
            onClick={() => submitPaper('headmaster')}
            disabled={loading}
            className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-semibold"
          >
            📤 Submit to Headmaster
          </button>
          <button
            onClick={() => submitPaper('proprietor')}
            disabled={loading}
            className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-semibold"
          >
            📤 Submit to Proprietor
          </button>
          {paperData.questions.length > 0 && (
            <button
              onClick={printPaper}
              className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-semibold"
            >
              🖨️ Print Preview
            </button>
          )}
        </div>
      </header>

      <div className="mb-4 p-3 rounded-lg border bg-white text-sm text-slate-700 flex flex-wrap items-center gap-3">
        <span className="font-semibold">Status:</span>
        <span className="px-2 py-1 rounded bg-slate-100 text-slate-700">{paperData.status || 'draft'}</span>
        {isOffline && <span className="px-2 py-1 rounded bg-red-100 text-red-700 font-semibold">Offline: Local draft only</span>}
        {!isOffline && <span className="px-2 py-1 rounded bg-emerald-100 text-emerald-700">Online</span>}
        <span className="text-xs text-slate-500">Draft autosave: {saveState}</span>
      </div>
      
      {/* Paper Metadata Form */}
      <div className="bg-white rounded-xl shadow-sm border p-6 mb-6">
        <h2 className="text-xl font-bold text-blue-900 mb-4">Exam Details</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">Exam Title *</label>
            <input
              type="text"
              value={paperData.title}
              onChange={(e) => setPaperData({ ...paperData, title: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="e.g., Mathematics Mid-Term Exam"
            />
          </div>
          
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">Exam Type</label>
            <select
              value={paperData.exam_type}
              onChange={(e) => setPaperData({ ...paperData, exam_type: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="Mid-Term">Mid-Term Exam</option>
              <option value="End of Term">End of Term Exam</option>
              <option value="Mock Exam">Mock Exam</option>
              <option value="Class Test">Class Test</option>
              <option value="Quiz">Quiz</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">Class *</label>
            {assignedClasses.length > 0 ? (
              <select
                value={paperData.class_name}
                onChange={(e) => setPaperData({ ...paperData, class_name: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                {assignedClasses.map((className) => (
                  <option key={className} value={className}>{className}</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={paperData.class_name}
                onChange={(e) => setPaperData({ ...paperData, class_name: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., JHS 1"
              />
            )}
          </div>
          
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">Subject *</label>
            {assignedSubjects.length > 0 ? (
              <select
                value={paperData.subject_name}
                onChange={(e) => setPaperData({ ...paperData, subject_name: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                {assignedSubjects.map((subjectName) => (
                  <option key={subjectName} value={subjectName}>{subjectName}</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={paperData.subject_name}
                onChange={(e) => setPaperData({ ...paperData, subject_name: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., Mathematics"
              />
            )}
          </div>
          
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">Academic Term</label>
            <select
              value={paperData.academic_term}
              onChange={(e) => setPaperData({ ...paperData, academic_term: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="Term 1">Term 1</option>
              <option value="Term 2">Term 2</option>
              <option value="Term 3">Term 3</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">Academic Year</label>
            <input
              type="text"
              value={paperData.academic_year}
              onChange={(e) => setPaperData({ ...paperData, academic_year: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="e.g., 2025/2026"
            />
          </div>
          
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">Duration (minutes)</label>
            <input
              type="number"
              value={paperData.duration_minutes}
              onChange={(e) => setPaperData({ ...paperData, duration_minutes: parseInt(e.target.value) || 0 })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">Total Marks</label>
            <input
              type="number"
              value={paperData.total_marks}
              onChange={(e) => setPaperData({ ...paperData, total_marks: parseInt(e.target.value) || 0 })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">Instructions for Students</label>
          <textarea
            value={paperData.instructions}
            onChange={(e) => setPaperData({ ...paperData, instructions: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            rows="3"
            placeholder="Enter general instructions for the exam..."
          />
        </div>
      </div>
      
      {/* Questions Section */}
      <div className="bg-white rounded-xl shadow-sm border p-6 mb-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-blue-900">Questions ({paperData.questions.length})</h2>
          <button
            onClick={() => {
              if (!isPremiumPlan) {
                alert('AI Exam Assistant is available on Premium plan only.');
                return;
              }
              setShowAiDialog(true);
            }}
            className={`px-4 py-2 rounded-lg transition-colors font-semibold ${isPremiumPlan ? 'bg-purple-600 text-white hover:bg-purple-700' : 'bg-slate-300 text-slate-600 cursor-not-allowed'}`}
          >
            🤖 AI Exam Assistant {isPremiumPlan ? '' : '(Premium)'}
          </button>
        </div>

        {!isPremiumPlan && (
          <div className="mb-4 p-3 rounded-lg border border-amber-300 bg-amber-50 text-amber-900 text-sm">
            AI Exam Assistant is a Premium-only feature. Upgrade your plan to generate exam questions with AI guidance.
          </div>
        )}
        
        {/* Add New Question Form */}
        <div className="bg-blue-50 p-4 rounded-lg mb-4">
          <h3 className="font-semibold text-blue-900 mb-3">Add New Question</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Question Type</label>
              <select
                value={newQuestion.type}
                onChange={(e) => setNewQuestion({ ...newQuestion, type: e.target.value })}
                className="w-full px-2 py-2 border rounded text-sm"
              >
                <option value="mcq">Multiple Choice (MCQ)</option>
                <option value="short">Short Answer</option>
                <option value="essay">Essay</option>
                <option value="fill">Fill in the Blank</option>
              </select>
            </div>
            
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Marks</label>
              <input
                type="number"
                value={newQuestion.marks}
                onChange={(e) => setNewQuestion({ ...newQuestion, marks: parseInt(e.target.value) || 0 })}
                className="w-full px-2 py-2 border rounded text-sm"
              />
            </div>
            
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Section</label>
              <select
                value={newQuestion.section}
                onChange={(e) => setNewQuestion({ ...newQuestion, section: e.target.value })}
                className="w-full px-2 py-2 border rounded text-sm"
              >
                <option value="A">Section A</option>
                <option value="B">Section B</option>
                <option value="C">Section C</option>
              </select>
            </div>
          </div>
          
          <div className="mb-3">
            <label className="block text-xs font-semibold text-gray-700 mb-1">Question Text</label>
            <textarea
              value={newQuestion.question}
              onChange={(e) => setNewQuestion({ ...newQuestion, question: e.target.value })}
              onPaste={handleQuestionTextPaste}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              rows="2"
              placeholder="Enter the question..."
            />
            <p className="text-[11px] text-slate-500 mt-1">Tip: You can paste an image directly here (Ctrl+V) after screenshot copy.</p>
          </div>

          <div className="mb-3">
            <label className="block text-xs font-semibold text-gray-700 mb-1">Diagram/Image (Optional)</label>
            <input
              type="text"
              value={newQuestion.image_url || ''}
              onChange={(e) => setNewQuestion({ ...newQuestion, image_url: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 text-sm mb-2"
              placeholder="Paste image URL or base64 data URL"
            />
            <div
              onDragEnter={(e) => {
                e.preventDefault();
                setImageDropActive(true);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setImageDropActive(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                setImageDropActive(false);
              }}
              onDrop={handleImageDrop}
              className={`p-3 border-2 border-dashed rounded text-xs text-center mb-2 ${imageDropActive ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-white'}`}
            >
              Drag and drop image here, or choose file below
            </div>
            <input
              type="file"
              accept="image/*"
              onChange={handleQuestionImageFile}
              className="w-full px-2 py-2 border rounded text-xs bg-white"
            />
            {imageProcessing && (
              <p className="text-xs text-blue-700 mt-2">Processing and compressing image...</p>
            )}
            {newQuestion.image_url && (
              <img
                src={newQuestion.image_url}
                alt="Question diagram preview"
                className="mt-2 max-h-36 border rounded"
              />
            )}
          </div>
          
          {newQuestion.type === 'mcq' && (
            <div className="mb-3">
              <label className="block text-xs font-semibold text-gray-700 mb-1">Options (A, B, C, D)</label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {newQuestion.options.map((opt, idx) => (
                  <input
                    key={idx}
                    type="text"
                    value={opt}
                    onChange={(e) => {
                      const newOptions = [...newQuestion.options];
                      newOptions[idx] = e.target.value;
                      setNewQuestion({ ...newQuestion, options: newOptions });
                    }}
                    className="px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 text-sm"
                    placeholder={`Option ${String.fromCharCode(65 + idx)}`}
                  />
                ))}
              </div>
            </div>
          )}
          
          <button
            onClick={addQuestion}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold"
          >
            + Add Question
          </button>
        </div>
        
        {/* Questions List */}
        <div className="space-y-3">
          {paperData.questions.length === 0 ? (
            <p className="text-center text-gray-500 py-8">No questions added yet. Use the form above to add questions.</p>
          ) : (
            paperData.questions.map((q, idx) => (
              <div key={q.id} className="border rounded-lg p-4 hover:bg-gray-50">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex-1">
                    <span className="font-bold text-blue-900">Q{idx + 1}.</span>
                    <span className="ml-2 text-gray-700">{q.question}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-semibold">
                      {q.marks} marks
                    </span>
                    <button
                      onClick={() => removeQuestion(q.id)}
                      className="text-red-600 hover:text-red-800 font-semibold text-sm"
                    >
                      ✕ Remove
                    </button>
                  </div>
                </div>
                
                {q.type === 'mcq' && q.options && (
                  <div className="ml-6 mt-2 space-y-1">
                    {q.options.map((opt, i) => (
                      opt && <div key={i} className="text-sm text-gray-600">
                        {String.fromCharCode(65 + i)}. {opt}
                      </div>
                    ))}
                  </div>
                )}

                {q.image_url && (
                  <div className="ml-6 mt-3">
                    <img
                      src={q.image_url}
                      alt="Question diagram"
                      className="max-h-48 border rounded"
                    />
                  </div>
                )}
                
                <div className="ml-6 mt-2 text-xs text-gray-500">
                  Type: {q.type.toUpperCase()} • Section: {q.section}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
      
      {/* AI Dialog */}
      {showAiDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-xl font-bold text-blue-900 mb-4">🤖 AI Exam Assistant</h3>
            
            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">Topic/Chapter</label>
                <input
                  type="text"
                  value={aiPrompt.topic}
                  onChange={(e) => setAiPrompt({ ...aiPrompt, topic: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Algebra, Fractions"
                />
              </div>
              
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">Difficulty Level</label>
                <select
                  value={aiPrompt.difficulty}
                  onChange={(e) => setAiPrompt({ ...aiPrompt, difficulty: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">Question Type</label>
                <select
                  value={aiPrompt.question_type}
                  onChange={(e) => setAiPrompt({ ...aiPrompt, question_type: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="mcq">Multiple Choice</option>
                  <option value="short">Short Answer</option>
                  <option value="essay">Essay</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">Teacher Instructions (Optional)</label>
                <textarea
                  value={aiPrompt.teacher_instructions}
                  onChange={(e) => setAiPrompt({ ...aiPrompt, teacher_instructions: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  rows="3"
                  placeholder="Example: Include 2 word problems, avoid fractions, use Ghana context, add one diagram-based question..."
                />
              </div>
              
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">Number of Questions</label>
                <input
                  type="number"
                  value={aiPrompt.count}
                  onChange={(e) => setAiPrompt({ ...aiPrompt, count: parseInt(e.target.value) || 1 })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  min="1"
                  max="20"
                />
              </div>

              {aiGeneratedPrompt && (
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1">Generated AI Prompt</label>
                  <textarea
                    value={aiGeneratedPrompt}
                    readOnly
                    rows="10"
                    className="w-full px-3 py-2 border rounded-lg bg-gray-50 text-sm"
                  />
                  <button
                    onClick={copyAiPrompt}
                    className="mt-2 px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-semibold"
                  >
                    Copy Prompt
                  </button>
                </div>
              )}
            </div>
            
            <div className="flex gap-3">
              <button
                onClick={() => setShowAiDialog(false)}
                className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={generateAiQuestions}
                className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-semibold"
              >
                Generate Questions
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
