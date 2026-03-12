import React, { useState } from 'react';
import axios from 'axios';
import TermsModal from '../components/TermsModal';
import PrivacyModal from '../components/PrivacyModal';
import DataRetentionModal from '../components/DataRetentionModal';
import { Logo } from '../components/Logo';
import { CheckCircle, ArrowRight, ArrowLeft } from 'lucide-react';

const TERMS_VERSION = '2026-03-07';
const POLICY_VERSION = '2026-03-07';

export default function Register() {
  const [step, setStep] = useState(1); // Step 1: Info, Step 2: Plan Selection, Step 3: Confirmation
  const [form, setForm] = useState({ 
    schoolName: '', 
    schoolCode: '', 
    username: '', 
    email: '', 
    password: '',
    selectedPlan: 'Free' // Default to Free plan
  });
  const [error, setError] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [showRetention, setShowRetention] = useState(false);
  const [studentCount, setStudentCount] = useState(100);

  const plans = [
    {
      name: 'Free',
      price: 0,
      priceLabel: 'Forever Free',
      description: 'Perfect for small schools getting started',
      maxStudents: 50,
      maxClasses: 1,
      color: 'gray',
      features: [
        'Up to 50 students',
        '1 class only',
        'View attendance & feeding',
        'Basic report generation',
        'Grade viewing'
      ],
    },
    {
      name: 'Basic',
      price: 12,
      baseFee: 200,
      includedStudents: 25,
      priceLabel: '₵200 base + ₵12/extra above 25',
      description: 'Full school operations for growing institutions',
      maxStudents: 200,
      maxClasses: 5,
      color: 'blue',
      popular: true,
      features: [
        'Up to 200 students',
        '5 classes',
        'Full attendance & feeding',
        'Grade entry & editing',
        'Payment tracking',
        'Lesson notes creation',
        'Bulk operations',
        'Exam Papers module (Premium only)',
        'AI Exam Assistant (Premium only)'
      ],
    },
    {
      name: 'Premium',
      price: 27,
      baseFee: 450,
      includedStudents: 30,
      priceLabel: '₵450 base + ₵27/extra above 30',
      description: 'Unlimited access with AI-powered insights',
      maxStudents: Infinity,
      maxClasses: Infinity,
      color: 'purple',
      features: [
        'Unlimited students',
        'Unlimited classes',
        'Everything in Basic',
        'Exam Papers module',
        'AI Exam Assistant for exam papers',
        'AI-powered grade narratives',
        'Advanced analytics',
        'Custom HTML templates',
        'Priority support'
      ],
    },
  ];

  const handleNext = (e) => {
    e.preventDefault();
    setError('');
    
    if (step === 1) {
      // Validate step 1 fields
      if (!form.schoolName || !form.schoolCode || !form.username || !form.email || !form.password) {
        setError('Please fill in all fields');
        return;
      }
      if (!agreed) {
        setError('You must agree to the Terms of Service, Privacy Policy, and Data Retention Policy');
        return;
      }
      setStep(2);
    } else if (step === 2) {
      setStep(3);
    }
  };

  const handleBack = () => {
    setError('');
    setStep(step - 1);
  };

  const handleRegister = async () => {
    setError('');

    try {
      const payload = {
        schoolName: form.schoolName.trim(),
        schoolCode: form.schoolCode.trim().toUpperCase(),
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        selectedPlan: form.selectedPlan, // Send selected plan
        studentCount,
        termsAccepted: agreed,
        termsVersion: TERMS_VERSION,
        policyAccepted: agreed,
        policyVersion: POLICY_VERSION
      };

      const res = await axios.post('/api/register', payload);

      if (res.data?.requires_payment && res.data?.payment_url) {
        // Temporary auth context for payment verification callback.
        if (res.data.token) {
          localStorage.setItem('token', res.data.token);
        }
        if (res.data.school_id) {
          localStorage.setItem('school_id', res.data.school_id);
        }
        if (res.data.role) {
          localStorage.setItem('role', res.data.role);
        }
        if (Array.isArray(res.data.roles)) {
          localStorage.setItem('roles', JSON.stringify(res.data.roles));
        }
        if (res.data.subscription_plan) {
          localStorage.setItem('subscription_plan', res.data.subscription_plan);
        }

        alert('Registration saved. Redirecting to payment to activate your selected plan.');
        window.location.href = res.data.payment_url;
        return;
      }

      alert('Registration Successful! You can now login.');
      window.location.href = '/login';
    } catch (err) {
      const errorMsg = err.response?.data?.message || 'Registration failed.';
      const errorDetails = err.response?.data?.errors;
      setError(errorDetails ? `${errorMsg}: ${errorDetails}` : errorMsg);
      setStep(1); // Go back to step 1 if registration fails
    }
  };

  const calculateCost = (plan) => {
    if (plan.name === 'Free') return { term: 0, annual: 0, overage: 0, included: 0, baseFee: 0 };

    const cappedStudents = plan.maxStudents === Infinity
      ? studentCount
      : Math.min(studentCount, plan.maxStudents);
    const baseFee = plan.baseFee || 0;
    const included = plan.includedStudents || 0;
    const overage = Math.max(0, cappedStudents - included);
    const termCost = baseFee + (overage * plan.price);
    const annualCost = termCost * 3;
    return { term: termCost, annual: annualCost, overage, included, baseFee };
  };

  return (
    <div className="min-h-screen flex bg-white font-sans">
      {/* Left Side - Branding */}
      <div className="hidden lg:flex w-1/2 bg-blue-900 items-center justify-center relative overflow-hidden">
        <div className="absolute inset-0 bg-linear-to-br from-blue-900 to-slate-900 opacity-90 z-10"></div>
        <img src="https://images.unsplash.com/photo-1523050854058-8df90110c9f1?ixlib=rb-4.0.3&auto=format&fit=crop&w=1350&q=80" className="absolute inset-0 w-full h-full object-cover" alt="School" />
        <div className="relative z-20 text-white p-12 max-w-xl">
          <div className="w-16 h-16 bg-white/10 backdrop-blur-md rounded-2xl flex items-center justify-center mb-6 border border-white/20 shadow-xl" style={{background: 'rgba(102, 126, 234, 0.2)'}}>
            <Logo size="lg" variant="default" />
          </div>
          <h2 className="text-5xl font-black mb-6 leading-tight">Start Your Journey.</h2>
          <p className="text-blue-200 text-lg leading-relaxed">
            {step === 1 && '"Join hundreds of schools using EduPulse to secure revenue and improve academic outcomes."'}
            {step === 2 && '"Choose the right plan for your school. Basic and Premium continue to secure payment during signup."'}
            {step === 3 && '"You\'re almost there! Review your details and complete registration."'}
          </p>
          
          {/* Progress Indicator */}
          <div className="mt-12 flex items-center gap-3">
            <div className={`h-2 flex-1 rounded-full ${step >= 1 ? 'bg-blue-400' : 'bg-white/20'}`}></div>
            <div className={`h-2 flex-1 rounded-full ${step >= 2 ? 'bg-blue-400' : 'bg-white/20'}`}></div>
            <div className={`h-2 flex-1 rounded-full ${step >= 3 ? 'bg-blue-400' : 'bg-white/20'}`}></div>
          </div>
          <div className="mt-3 text-sm text-blue-200 flex justify-between">
            <span>School Info</span>
            <span>Select Plan</span>
            <span>Confirm</span>
          </div>
        </div>
      </div>

      {/* Right Side - Registration Steps */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 lg:p-12 overflow-y-auto">
        <div className="w-full max-w-2xl">
          <div className="flex items-center gap-2 mb-8">
            <div className="w-10 h-10 bg-blue-900 rounded-lg flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-blue-200">E</div>
            <span className="text-2xl font-black text-blue-900 tracking-tighter">EDUPULSE SMT</span>
          </div>

          {error && <div className="bg-red-50 text-red-600 p-4 rounded-xl mb-6 text-sm font-bold flex items-center gap-2">⚠️ {error}</div>}

          {/* STEP 1: School Information */}
          {step === 1 && (
            <form onSubmit={handleNext}>
              <h1 className="text-3xl font-bold text-slate-800 mb-2">Create Tenant</h1>
              <p className="text-slate-500 mb-8">Register your school organization.</p>

              <div className="space-y-5">
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">School Name</label>
                  <input 
                    className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-all" 
                    placeholder="e.g. CCA Ofankor" 
                    value={form.schoolName}
                    onChange={e => setForm({...form, schoolName: e.target.value})} 
                    required 
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Organization ID</label>
                  <input 
                    className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-all font-mono uppercase" 
                    placeholder="e.g. CCA-OFK" 
                    value={form.schoolCode}
                    onChange={e => setForm({...form, schoolCode: e.target.value})} 
                    required 
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Proprietor Username</label>
                  <input 
                    className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-all" 
                    placeholder="Username" 
                    value={form.username}
                    onChange={e => setForm({...form, username: e.target.value})} 
                    required 
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Email Address</label>
                  <input 
                    className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-all" 
                    type="email" 
                    placeholder="owner@school.com" 
                    value={form.email}
                    onChange={e => setForm({...form, email: e.target.value})} 
                    required 
                  />
                  <p className="text-xs text-slate-500 mt-1 ml-1">Used for welcome email and password recovery</p>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Password</label>
                  <input 
                    className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-all" 
                    type="password" 
                    placeholder="••••••••" 
                    value={form.password}
                    onChange={e => setForm({...form, password: e.target.value})} 
                    required 
                  />
                  <p className="text-xs text-slate-500 mt-1 ml-1">Must be 8+ characters with uppercase, lowercase, and digit</p>
                </div>
                
                <div className="flex items-center gap-2 pt-2">
                  <input 
                    type="checkbox" 
                    id="terms" 
                    checked={agreed} 
                    onChange={(e) => setAgreed(e.target.checked)}
                    className="w-5 h-5 rounded border-slate-300 text-blue-900 focus:ring-blue-500 cursor-pointer"
                  />
                  <label htmlFor="terms" className="text-sm text-slate-600 cursor-pointer select-none">
                    I agree to the <button type="button" onClick={() => setShowTerms(true)} className="text-blue-600 font-bold hover:underline">Terms of Service</button> and
                    <button type="button" onClick={() => setShowPrivacy(true)} className="text-blue-600 font-bold hover:underline ml-1">Privacy Policy</button>
                    <span className="ml-1">and</span>
                    <button type="button" onClick={() => setShowRetention(true)} className="text-blue-600 font-bold hover:underline ml-1">Data Retention Policy</button>
                  </label>
                </div>
              </div>

              <button type="submit" className="w-full bg-blue-600 text-white p-4 rounded-xl font-bold mt-8 hover:bg-blue-700 transition-all shadow-xl shadow-blue-200 flex items-center justify-center gap-2">
                Continue to Plan Selection <ArrowRight size={20} />
              </button>

              <p className="text-center mt-8 text-sm text-slate-400">
                Already have an account? <a href="/login" className="text-blue-600 font-bold hover:underline">Login</a>
              </p>
            </form>
          )}

          {/* STEP 2: Plan Selection */}
          {step === 2 && (
            <div>
              <h1 className="text-3xl font-bold text-slate-800 mb-2">Choose Your Plan</h1>
              <p className="text-slate-500 mb-4">Select the perfect plan for {form.schoolName}</p>

              {/* Important Notice */}
              <div className="bg-blue-50 border-l-4 border-blue-600 p-4 rounded-r-xl mb-6">
                <p className="text-sm text-blue-900 font-semibold">
                  ℹ️ <strong>Free</strong> completes instantly. If you choose <strong>Basic</strong> or <strong>Premium</strong>, you will be redirected to payment immediately to activate that plan.
                </p>
              </div>

              {/* Student Count Adjuster */}
              <div className="bg-slate-50 p-4 rounded-xl mb-6">
                <label className="text-sm font-bold text-slate-700 mb-2 block">Number of Students</label>
                <input
                  type="number"
                  min="1"
                  max="1000"
                  value={studentCount}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === '') {
                      setStudentCount(1); // Allow clearing but set to minimum
                    } else {
                      const num = parseInt(val);
                      if (!isNaN(num) && num > 0) {
                        setStudentCount(Math.min(1000, num));
                      }
                    }
                  }}
                  onBlur={(e) => {
                    // Ensure valid value on blur
                    if (!e.target.value || parseInt(e.target.value) < 1) {
                      setStudentCount(1);
                    }
                  }}
                  className="w-full p-3 border rounded-lg"
                />
                <p className="text-xs text-slate-600 mt-2">Adjust to calculate cost for your school</p>
              </div>

              {/* Plan Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                {plans.map((plan) => {
                  const cost = calculateCost(plan);
                  const isSelected = form.selectedPlan === plan.name;
                  
                  return (
                    <div
                      key={plan.name}
                      onClick={() => setForm({...form, selectedPlan: plan.name})}
                      className={`relative border-2 rounded-2xl p-6 cursor-pointer transition-all ${
                        isSelected 
                          ? 'border-blue-600 bg-blue-50 shadow-xl' 
                          : 'border-slate-200 hover:border-blue-300 hover:shadow-lg'
                      }`}
                    >
                      {plan.popular && (
                        <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-blue-600 text-white text-xs font-bold px-3 py-1 rounded-full">
                          MOST POPULAR
                        </div>
                      )}
                      {isSelected && (
                        <div className="absolute top-4 right-4">
                          <CheckCircle className="text-blue-600" size={24} />
                        </div>
                      )}
                      
                      <h3 className="text-xl font-bold text-slate-800 mb-2">{plan.name}</h3>
                      <p className="text-sm text-slate-600 mb-4">{plan.description}</p>
                      
                      <div className="mb-4">
                        {plan.name === 'Free' ? (
                          <div className="text-3xl font-black text-slate-800">GH₵ 0</div>
                        ) : (
                          <>
                            <div className="text-2xl font-black text-slate-800">GH₵ {cost.term.toLocaleString()}</div>
                            <div className="text-sm text-slate-600">per term ({studentCount} students)</div>
                            <div className="text-xs text-slate-500 mt-1">Base: GH₵ {cost.baseFee} + {cost.included} included</div>
                            {cost.overage > 0 && (
                              <div className="text-xs text-slate-500">Overage: {cost.overage} × GH₵ {plan.price} = GH₵ {(cost.overage * plan.price).toLocaleString()}</div>
                            )}
                            <div className="text-xs text-slate-500 mt-1">GH₵ {cost.annual.toLocaleString()}/year</div>
                          </>
                        )}
                      </div>
                      
                      <ul className="space-y-2 text-sm">
                        {plan.features.map((feature, idx) => (
                          <li key={idx} className="flex items-start gap-2">
                            <CheckCircle className="text-green-600 shrink-0 mt-0.5" size={16} />
                            <span>{feature}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>

              <div className="flex gap-4">
                <button 
                  onClick={handleBack}
                  className="flex-1 bg-slate-200 text-slate-700 p-4 rounded-xl font-bold hover:bg-slate-300 transition-all flex items-center justify-center gap-2"
                >
                  <ArrowLeft size={20} /> Back
                </button>
                <button 
                  onClick={handleNext}
                  className="flex-1 bg-blue-600 text-white p-4 rounded-xl font-bold hover:bg-blue-700 transition-all shadow-xl shadow-blue-200 flex items-center justify-center gap-2"
                >
                  Continue <ArrowRight size={20} />
                </button>
              </div>
            </div>
          )}

          {/* STEP 3: Confirmation */}
          {step === 3 && (
            <div>
              <h1 className="text-3xl font-bold text-slate-800 mb-2">Confirm Registration</h1>
              <p className="text-slate-500 mb-8">
                {form.selectedPlan === 'Free'
                  ? 'Review your details before completing registration'
                  : 'Review your details before continuing to payment'}
              </p>

              <div className="bg-slate-50 rounded-2xl p-6 mb-6 space-y-4">
                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase mb-1">School Name</div>
                  <div className="text-lg font-bold text-slate-800">{form.schoolName}</div>
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase mb-1">Organization ID</div>
                  <div className="text-lg font-mono font-bold text-slate-800">{form.schoolCode.toUpperCase()}</div>
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase mb-1">Proprietor</div>
                  <div className="text-lg font-bold text-slate-800">{form.username}</div>
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase mb-1">Email</div>
                  <div className="text-lg font-bold text-slate-800">{form.email}</div>
                </div>
                <div className="border-t pt-4">
                  <div className="text-xs font-bold text-slate-500 uppercase mb-1">Selected Plan</div>
                  <div className="text-2xl font-black text-blue-600">{form.selectedPlan}</div>
                  {form.selectedPlan !== 'Free' && (
                    <div className="text-sm text-slate-600 mt-1">
                      ~GH₵ {calculateCost(plans.find(p => p.name === form.selectedPlan)).term.toLocaleString()}/term for {studentCount} students
                    </div>
                  )}
                </div>
              </div>

              <div className="flex gap-4">
                <button 
                  onClick={handleBack}
                  className="flex-1 bg-slate-200 text-slate-700 p-4 rounded-xl font-bold hover:bg-slate-300 transition-all flex items-center justify-center gap-2"
                >
                  <ArrowLeft size={20} /> Back
                </button>
                <button 
                  onClick={handleRegister}
                  className="flex-1 bg-green-600 text-white p-4 rounded-xl font-bold hover:bg-green-700 transition-all shadow-xl shadow-green-200 flex items-center justify-center gap-2"
                >
                  {form.selectedPlan === 'Free' ? 'Complete Registration ✓' : 'Proceed to Payment →'}
                </button>
              </div>

              <p className="text-center mt-5 text-xs text-slate-500 leading-relaxed">
                By creating a school account, you accept our{' '}
                <button type="button" onClick={() => setShowTerms(true)} className="text-blue-600 font-semibold hover:underline">Terms of Service</button>,{' '}
                <button type="button" onClick={() => setShowPrivacy(true)} className="text-blue-600 font-semibold hover:underline">Privacy Policy</button>, and{' '}
                <button type="button" onClick={() => setShowRetention(true)} className="text-blue-600 font-semibold hover:underline">Data Retention Policy</button>.
              </p>

              <p className="text-center mt-6 text-xs text-slate-400">
                By completing registration, you confirm all information is accurate.
              </p>
            </div>
          )}

          <TermsModal isOpen={showTerms} onClose={() => setShowTerms(false)} />
          <PrivacyModal isOpen={showPrivacy} onClose={() => setShowPrivacy(false)} />
          <DataRetentionModal isOpen={showRetention} onClose={() => setShowRetention(false)} />
        </div>
      </div>
    </div>
  );
}