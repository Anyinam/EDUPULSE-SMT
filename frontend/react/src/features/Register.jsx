import React, { useEffect, useState } from 'react';
import axios from 'axios';
import TermsModal from '../components/TermsModal';
import PrivacyModal from '../components/PrivacyModal';
import DataRetentionModal from '../components/DataRetentionModal';
import DataProcessingModal from '../components/DataProcessingModal';
import { Logo } from '../components/Logo';
import { CheckCircle, ArrowRight, ArrowLeft, Loader, Info } from 'lucide-react';

const TERMS_VERSION = '2026-03-07';
const POLICY_VERSION = '2026-03-07';

const DEFAULT_PUBLIC_CONTENT = {
  support: {
    email: 'info@edupulsesmt.com',
    phone: '+233 552 141 384',
    response_time: 'within 24 hours on business days',
  },
  auth: {
    register_title: 'Create Tenant',
    register_subtitle: 'Register your school organization.',
    register_support_note: 'Need help choosing a plan or completing registration?',
  },
};

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
  const [plans, setPlans] = useState([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [agreed, setAgreed] = useState(false);
  const [schoolAuthorityConfirmed, setSchoolAuthorityConfirmed] = useState(false);
  const [migrationConsentPlanConfirmed, setMigrationConsentPlanConfirmed] = useState(false);
  const [aggregatedAnalyticsAccepted, setAggregatedAnalyticsAccepted] = useState(false);
  const [showAnalyticsTooltip, setShowAnalyticsTooltip] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [showRetention, setShowRetention] = useState(false);
  const [showDataProcessing, setShowDataProcessing] = useState(false);
  const [publicContent, setPublicContent] = useState(DEFAULT_PUBLIC_CONTENT);

  useEffect(() => {
    const fetchPlans = async () => {
      try {
        const res = await axios.get('/api/subscription/plans');
        const mappedPlans = (res.data?.plans || []).map((plan) => ({
          rawName: plan.name,
          name: plan.name === 'Free Tier' ? 'Free' : plan.name,
          displayName: plan.display_name || plan.name,
          price: Number(plan.price_per_student_per_term || 0),
          baseFee: Number(plan.base_fee_per_term || 0),
          includedStudents: Number(plan.included_students || 0),
          description: plan.description || '',
          maxStudents: plan.max_students === '∞' ? 'Unlimited' : plan.max_students,
          maxClasses: plan.max_classes === '∞' ? 'Unlimited' : plan.max_classes,
          color: plan.ui_color || 'gray',
          popular: Boolean(plan.popular),
          features: plan.marketing_features || [],
          addonOptions: plan.addon_options || [],
          packagingSummary: plan.packaging_summary || '',
        }));
        setPlans(mappedPlans);
      } catch (fetchError) {
        console.error('Failed to load registration plans:', fetchError);
        setError('Unable to load subscription plans right now. Please refresh and try again.');
      } finally {
        setPlansLoading(false);
      }
    };

    fetchPlans();

    const fetchPublicContent = async () => {
      try {
        const res = await axios.get('/api/public/platform-content');
        setPublicContent((prev) => ({ ...prev, ...res.data }));
      } catch {
        setPublicContent(DEFAULT_PUBLIC_CONTENT);
      }
    };

    fetchPublicContent();
  }, []);

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
      if (!aggregatedAnalyticsAccepted) {
        setError('You must agree to the Data Processing Agreement, including anonymized aggregated academic metrics for benchmarking and system optimization.');
        return;
      }
      if (!schoolAuthorityConfirmed) {
        setError('You must confirm that the school has authority to manage student and guardian records in EduPulse SMT.');
        return;
      }
      if (!migrationConsentPlanConfirmed) {
        setError('You must confirm that the school will issue any required notices or consents before migrating legacy records or uploading WAEC/BECE data.');
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
        termsAccepted: agreed,
        termsVersion: TERMS_VERSION,
        policyAccepted: agreed,
        policyVersion: POLICY_VERSION,
        schoolDataAuthorityConfirmed: schoolAuthorityConfirmed,
        legacyAndExamConsentPlanConfirmed: migrationConsentPlanConfirmed,
        aggregatedAnalyticsAccepted,
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
            {step === 2 && '"Choose the right plan for your school. Paid plans charge only the base fee during signup."'}
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
              <h1 className="text-3xl font-bold text-slate-800 mb-2">{publicContent.auth?.register_title || DEFAULT_PUBLIC_CONTENT.auth.register_title}</h1>
              <p className="text-slate-500 mb-8">{publicContent.auth?.register_subtitle || DEFAULT_PUBLIC_CONTENT.auth.register_subtitle}</p>

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
                <div className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    id="aggregated-analytics-acceptance"
                    checked={aggregatedAnalyticsAccepted}
                    onChange={(e) => setAggregatedAnalyticsAccepted(e.target.checked)}
                    className="mt-1 h-5 w-5 rounded border-slate-300 text-blue-900 focus:ring-blue-500 cursor-pointer"
                  />
                  <div className="min-w-0">
                    <div className="flex items-start gap-2">
                      <label htmlFor="aggregated-analytics-acceptance" className="text-sm text-slate-600 cursor-pointer select-none">
                        I agree to the{' '}
                        <button type="button" onClick={() => setShowDataProcessing(true)} className="font-bold text-blue-600 hover:underline">
                          Data Processing Agreement
                        </button>, including the use of anonymized, aggregated academic metrics for national educational benchmarking and system optimization.
                      </label>
                      <button
                        type="button"
                        aria-label="Show anonymized analytics privacy explanation"
                        onClick={() => setShowAnalyticsTooltip((current) => !current)}
                        className="mt-0.5 inline-flex shrink-0 items-center justify-center rounded-full text-blue-700 hover:text-blue-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <Info size={16} />
                      </button>
                    </div>
                    {showAnalyticsTooltip && (
                      <div className="mt-2 rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs leading-5 text-blue-900">
                        We take privacy seriously. Your student names and school identity are completely stripped out using security protocols before approved data is pooled into aggregated graphs. Your school's private dashboard remains viewable only by you.
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    id="school-authority"
                    checked={schoolAuthorityConfirmed}
                    onChange={(e) => setSchoolAuthorityConfirmed(e.target.checked)}
                    className="mt-1 h-5 w-5 rounded border-slate-300 text-blue-900 focus:ring-blue-500 cursor-pointer"
                  />
                  <label htmlFor="school-authority" className="text-sm text-slate-600 cursor-pointer select-none">
                    I confirm that this school has authority to manage student, guardian, and school records in EduPulse SMT and understands that parent or guardian consent must be obtained before student biodata is uploaded.
                  </label>
                </div>
                <div className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    id="legacy-consent-plan"
                    checked={migrationConsentPlanConfirmed}
                    onChange={(e) => setMigrationConsentPlanConfirmed(e.target.checked)}
                    className="mt-1 h-5 w-5 rounded border-slate-300 text-blue-900 focus:ring-blue-500 cursor-pointer"
                  />
                  <label htmlFor="legacy-consent-plan" className="text-sm text-slate-600 cursor-pointer select-none">
                    I confirm that the school will use the parent-consent form sent to its registration email, or an approved equivalent, to notify parents or guardians and obtain any required consent before uploading student biodata, migrating legacy records, or uploading WAEC or BECE data.
                  </label>
                </div>
                <div className="rounded-xl border border-blue-100 bg-blue-50 p-4">
                  <p className="text-sm font-semibold text-blue-900">Anonymized educational benchmarking notice</p>
                  <p className="mt-2 text-sm leading-6 text-blue-900">
                    EduPulse SMT may de-identify and aggregate lawfully supplied academic records for district, regional, and national benchmarking, curriculum research, and system optimization. Student names, IDs, contact details, and direct school identifiers are intended to be removed before data enters the shared analytics layer, and shared outputs should remain aggregated rather than naming your students or school.
                  </p>
                </div>
                <p className="text-xs leading-5 text-slate-500">
                  By continuing, you confirm that your school has authority to manage student and guardian data in EduPulse SMT, will send the required parent or guardian notice or consent form before uploading any student biodata to EduPulse, including legacy records and WAEC or BECE result data, and explicitly accepts EduPulse SMT's Data Processing Agreement for anonymized, aggregated academic benchmarking and educational insights in line with Ghana's Data Protection Act.
                </p>
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
                  ℹ️ <strong>Free</strong> completes instantly. If you choose <strong>Basic</strong> or <strong>Premium</strong>, you will pay only the base fee now. Any overage above the included students will be billed later from actual usage.
                </p>
              </div>

              {plansLoading ? (
                <div className="flex items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 p-12">
                  <Loader className="h-8 w-8 animate-spin text-blue-600" />
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                  {plans.map((plan) => {
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
                        
                        <h3 className="text-xl font-bold text-slate-800 mb-2">{plan.displayName}</h3>
                        <p className="text-sm text-slate-600 mb-4">{plan.description}</p>
                        
                        <div className="mb-4">
                          {plan.name === 'Free' ? (
                            <div className="text-3xl font-black text-slate-800">GH₵ 0</div>
                          ) : (
                            <>
                              <div className="text-2xl font-black text-slate-800">GH₵ {plan.baseFee.toLocaleString()}</div>
                              <div className="text-sm text-slate-600">base fee at signup</div>
                              <div className="text-xs text-slate-500 mt-1">Includes first {plan.includedStudents} students each term</div>
                              <div className="text-xs text-slate-500">Later overage: GH₵ {plan.price}/student above {plan.includedStudents}</div>
                            </>
                          )}
                        </div>
                        
                        <ul className="space-y-2 text-sm">
                          {plan.features.map((feature, idx) => (
                            <li key={idx} className="flex items-start gap-2">
                              <CheckCircle className="text-green-600 shrink-0 mt-0.5" size={16} />
                              <span>
                                {feature.name}
                                {feature.note && <span className="ml-1 text-xs italic text-slate-500">{feature.note}</span>}
                              </span>
                            </li>
                          ))}
                        </ul>

                        {plan.packagingSummary && (
                          <p className="mt-4 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
                            {plan.packagingSummary}
                          </p>
                        )}

                        {plan.addonOptions.length > 0 && (
                          <div className="mt-4 border-t border-slate-100 pt-3">
                            <p className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">Future Add-Ons</p>
                            <p className="mb-2 text-xs text-slate-500">These are future optional products and do not come with the selected plan by default.</p>
                            <div className="flex flex-wrap gap-2">
                              {plan.addonOptions.map((addon) => (
                                <span key={addon} className="rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800">
                                  {addon}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

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
                  <div className="text-2xl font-black text-blue-600">{plans.find(p => p.name === form.selectedPlan)?.displayName || form.selectedPlan}</div>
                  {form.selectedPlan !== 'Free' && (
                    <div className="text-sm text-slate-600 mt-1">
                      GH₵ {plans.find(p => p.name === form.selectedPlan)?.baseFee?.toLocaleString()} due now at signup
                    </div>
                  )}
                  {form.selectedPlan !== 'Free' && (
                    <div className="text-xs text-slate-500 mt-1">
                      Overage above {plans.find(p => p.name === form.selectedPlan)?.includedStudents} students will be billed later based on actual active students.
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

              <p className="text-center mt-4 text-xs text-slate-500 leading-relaxed">
                Registration also confirms acceptance of the Data Processing Agreement and this onboarding notice's disclosure of EduPulse SMT's planned use of irreversibly de-identified, aggregated school-performance data for benchmarking, research, and system optimization.
              </p>

              <p className="text-center mt-6 text-xs text-slate-400">
                By completing registration, you confirm all information is accurate.
              </p>
            </div>
          )}

          <TermsModal isOpen={showTerms} onClose={() => setShowTerms(false)} />
          <PrivacyModal isOpen={showPrivacy} onClose={() => setShowPrivacy(false)} />
          <DataRetentionModal isOpen={showRetention} onClose={() => setShowRetention(false)} />
          <DataProcessingModal isOpen={showDataProcessing} onClose={() => setShowDataProcessing(false)} />

          <div className="mt-8 rounded-2xl border border-slate-200 bg-slate-50 p-5">
            <p className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">Registration Support</p>
            <p className="text-sm text-slate-600">{publicContent.auth?.register_support_note || DEFAULT_PUBLIC_CONTENT.auth.register_support_note}</p>
            <div className="mt-3 text-sm space-y-1">
              <p className="text-slate-700">Email: <a href={`mailto:${publicContent.support?.email || DEFAULT_PUBLIC_CONTENT.support.email}`} className="text-blue-600 font-semibold hover:underline">{publicContent.support?.email || DEFAULT_PUBLIC_CONTENT.support.email}</a></p>
              <p className="text-slate-700">Phone/WhatsApp: <a href={`tel:${(publicContent.support?.phone || DEFAULT_PUBLIC_CONTENT.support.phone).replace(/\s+/g, '')}`} className="text-blue-600 font-semibold hover:underline">{publicContent.support?.phone || DEFAULT_PUBLIC_CONTENT.support.phone}</a></p>
            </div>
            <p className="text-xs text-slate-500 mt-2">Typical response time: {publicContent.support?.response_time || DEFAULT_PUBLIC_CONTENT.support.response_time}.</p>
          </div>
        </div>
      </div>
    </div>
  );
}