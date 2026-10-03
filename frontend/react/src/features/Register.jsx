import React, { useEffect, useState } from 'react';
import axios from 'axios';
import TermsModal from '../components/TermsModal';
import PrivacyModal from '../components/PrivacyModal';
import DataRetentionModal from '../components/DataRetentionModal';
import DataProcessingModal from '../components/DataProcessingModal';
import PublicSiteLayout from '../components/PublicSiteLayout';
import '../styles/public-auth.css';
import { CheckCircle, XCircle, ArrowRight, ArrowLeft, Loader, Info } from 'lucide-react';

const TERMS_VERSION = '2026-03-07';
const POLICY_VERSION = '2026-03-07';

const DEFAULT_PUBLIC_CONTENT = {
  support: {
    email: 'info@edupulsesmt.com',
    phone: '+233 552 141 384',
    response_time: 'within 24 hours on business days',
  },
  auth: {
    register_title: 'Create your school account',
    register_subtitle: 'Start with your school and proprietor details.',
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
  const [isSubmitting, setIsSubmitting] = useState(false);
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
    if (isSubmitting) return;
    setIsSubmitting(true);
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
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PublicSiteLayout>
      <section className="public-auth public-auth--register" aria-labelledby="register-title">
          <div className="public-auth-heading">
            <h1 id="register-title">{DEFAULT_PUBLIC_CONTENT.auth.register_title}</h1>
            <p>{step === 1 ? DEFAULT_PUBLIC_CONTENT.auth.register_subtitle : step === 2 ? `Choose a plan for ${form.schoolName}.` : 'Review your details before completing registration.'}</p>
          </div>
          <ol className="public-auth-progress" aria-label="Registration progress">
            {['School details', 'Select plan', 'Confirm'].map((label, index) => (
              <li key={label} className={step >= index + 1 ? 'is-current' : ''} aria-current={step === index + 1 ? 'step' : undefined}>
                <span>{index + 1}</span>{label}
              </li>
            ))}
          </ol>
          {error && <p className="public-auth-error" role="alert">{error}</p>}

          {/* STEP 1: School Information */}
          {step === 1 && (
            <form onSubmit={handleNext}>
              <div className="public-auth-fields public-auth-school-fields">
                <div className="public-auth-field">
                  <label htmlFor="register-school-name">School Name</label>
                  <input 
                    id="register-school-name" autoComplete="organization"
                    placeholder="e.g. CCA Ofankor" 
                    value={form.schoolName}
                    onChange={e => setForm({...form, schoolName: e.target.value})} 
                    required 
                  />
                </div>
                <div className="public-auth-field">
                  <label htmlFor="register-school-id">School ID</label>
                  <input 
                    id="register-school-id"
                    placeholder="e.g. CCA-OFK" 
                    value={form.schoolCode}
                    onChange={e => setForm({...form, schoolCode: e.target.value})} 
                    required 
                  />
                </div>
                <div className="public-auth-field">
                  <label htmlFor="register-username">Proprietor Username</label>
                  <input 
                    id="register-username" autoComplete="username"
                    placeholder="Username" 
                    value={form.username}
                    onChange={e => setForm({...form, username: e.target.value})} 
                    required 
                  />
                </div>
                <div className="public-auth-field">
                  <label htmlFor="register-email">Email Address</label>
                  <input 
                    id="register-email" autoComplete="email"
                    type="email" 
                    placeholder="owner@school.com" 
                    value={form.email}
                    onChange={e => setForm({...form, email: e.target.value})} 
                    required 
                  />
                  <p className="public-auth-hint">Used for welcome email and password recovery</p>
                </div>
                <div className="public-auth-field public-auth-wide">
                  <label htmlFor="register-password">Password</label>
                  <input 
                    id="register-password" autoComplete="new-password"
                    type="password" 
                    placeholder="••••••••" 
                    value={form.password}
                    onChange={e => setForm({...form, password: e.target.value})} 
                    required 
                  />
                  <p className="public-auth-hint">Must be 8+ characters with uppercase, lowercase, and digit</p>
                </div>
              </div>
              <div className="public-auth-consents">
                <div className="public-auth-consent">
                  <input 
                    type="checkbox" 
                    id="terms" 
                    checked={agreed} 
                    onChange={(e) => setAgreed(e.target.checked)}
                    className="public-auth-checkbox"
                  />
                  <label htmlFor="terms">
                    I agree to the <button type="button" onClick={() => setShowTerms(true)} className="public-auth-link">Terms of Service</button> and{' '}
                    <button type="button" onClick={() => setShowPrivacy(true)} className="public-auth-link">Privacy Policy</button>{' '}and{' '}
                    <button type="button" onClick={() => setShowRetention(true)} className="public-auth-link">Data Retention Policy</button>
                  </label>
                </div>
                <div className="public-auth-consent">
                  <input
                    type="checkbox"
                    id="aggregated-analytics-acceptance"
                    checked={aggregatedAnalyticsAccepted}
                    onChange={(e) => setAggregatedAnalyticsAccepted(e.target.checked)}
                    className="public-auth-checkbox"
                  />
                  <div>
                    <div className="public-auth-analytics-label">
                      <label htmlFor="aggregated-analytics-acceptance">
                        I agree to the{' '}
                        <button type="button" onClick={() => setShowDataProcessing(true)} className="public-auth-link">
                          Data Processing Agreement
                        </button>, including the use of anonymized, aggregated academic metrics for national educational benchmarking and system optimization.
                      </label>
                      <button
                        type="button"
                        aria-label="Show anonymized analytics privacy explanation"
                        title="Anonymized analytics privacy explanation"
                        aria-expanded={showAnalyticsTooltip}
                        onClick={() => setShowAnalyticsTooltip((current) => !current)}
                        className="public-auth-info"
                      >
                        <Info size={16} />
                      </button>
                    </div>
                    {showAnalyticsTooltip && (
                      <div className="public-auth-notice">
                        We take privacy seriously. Your student names and school identity are completely stripped out using security protocols before approved data is pooled into aggregated graphs. Your school's private dashboard remains viewable only by you.
                      </div>
                    )}
                  </div>
                </div>
                <div className="public-auth-consent">
                  <input
                    type="checkbox"
                    id="school-authority"
                    checked={schoolAuthorityConfirmed}
                    onChange={(e) => setSchoolAuthorityConfirmed(e.target.checked)}
                    className="public-auth-checkbox"
                  />
                  <label htmlFor="school-authority">
                    I confirm that this school has authority to manage student, guardian, and school records in EduPulse SMT and understands that parent or guardian consent must be obtained before student biodata is uploaded.
                  </label>
                </div>
                <div className="public-auth-consent">
                  <input
                    type="checkbox"
                    id="legacy-consent-plan"
                    checked={migrationConsentPlanConfirmed}
                    onChange={(e) => setMigrationConsentPlanConfirmed(e.target.checked)}
                    className="public-auth-checkbox"
                  />
                  <label htmlFor="legacy-consent-plan">
                    I confirm that the school will use the parent-consent form sent to its registration email, or an approved equivalent, to notify parents or guardians and obtain any required consent before uploading student biodata, migrating legacy records, or uploading WAEC or BECE data.
                  </label>
                </div>
                <details className="public-auth-disclosure">
                  <summary>Anonymized educational benchmarking notice</summary>
                  <p>
                    EduPulse SMT may de-identify and aggregate lawfully supplied academic records for district, regional, and national benchmarking, curriculum research, and system optimization. Student names, IDs, contact details, and direct school identifiers are intended to be removed before data enters the shared analytics layer, and shared outputs should remain aggregated rather than naming your students or school.
                  </p>
                </details>
                <p className="public-auth-hint">
                  By continuing, you confirm that your school has authority to manage student and guardian data in EduPulse SMT, will send the required parent or guardian notice or consent form before uploading any student biodata to EduPulse, including legacy records and WAEC or BECE result data, and explicitly accepts EduPulse SMT's Data Processing Agreement for anonymized, aggregated academic benchmarking and educational insights in line with Ghana's Data Protection Act.
                </p>
              </div>

              <button type="submit" className="public-auth-primary">
                Continue to Plan Selection <ArrowRight size={20} />
              </button>

              <p className="public-auth-switch">
                Already have an account? <a href="/login">Login</a>
              </p>
            </form>
          )}

          {/* STEP 2: Plan Selection */}
          {step === 2 && (
            <div>
              <h2 className="public-auth-step-title">Choose Your Plan</h2>

              {/* Important Notice */}
              <div className="public-auth-notice">
                <p>
                  <strong>Free</strong> completes instantly. If you choose <strong>Basic</strong> or <strong>Premium</strong>, you will pay only the base fee now. Any overage above the included students will be billed later from actual usage.
                </p>
              </div>

              {plansLoading ? (
                <div className="public-auth-loading" role="status">
                  <Loader className="public-auth-spinner" size={24} /> Loading plans...
                </div>
              ) : (
                <div className="public-auth-plans" role="radiogroup" aria-label="Subscription plan">
                  {plans.map((plan) => {
                    const isSelected = form.selectedPlan === plan.name;
                    
                    return (
                      <label
                        key={plan.name}
                        className={`public-auth-plan ${isSelected ? 'is-selected' : ''}`}
                      >
                        <input type="radio" name="registration-plan" value={plan.name} checked={isSelected} onChange={() => setForm({...form, selectedPlan: plan.name})} aria-label={plan.displayName} />
                        {plan.popular && (
                          <div className="public-auth-plan-badge">
                            MOST POPULAR
                          </div>
                        )}
                        {isSelected && (
                          <div className="public-auth-plan-selected">
                            <CheckCircle size={20} />
                          </div>
                        )}
                        
                        <h3>{plan.displayName}</h3>
                        <p className="public-auth-plan-description">{plan.description}</p>
                        
                        <div className="public-auth-plan-price">
                          {plan.name === 'Free' ? (
                            <strong>GH₵ 0</strong>
                          ) : (
                            <>
                              <strong>GH₵ {plan.baseFee.toLocaleString()}</strong>
                              <div>base fee at signup</div>
                              <div>Includes first {plan.includedStudents} students each term</div>
                              <div>Additional students: GH₵ {plan.price} per student per term above {plan.includedStudents}</div>
                            </>
                          )}
                        </div>
                        
                        <ul className="public-auth-plan-features">
                          {plan.features.map((feature, idx) => (
                            <li key={idx}>
                              {feature.included ? <CheckCircle size={16} /> : <XCircle size={16} aria-label="Not included" />}
                              <span>
                                {feature.name}
                                {!feature.included && <span> (not included)</span>}
                                {feature.note && <span className="public-auth-plan-note"> {feature.note}</span>}
                              </span>
                            </li>
                          ))}
                        </ul>

                        {plan.packagingSummary && (
                          <p className="public-auth-plan-note">
                            {plan.packagingSummary}
                          </p>
                        )}

                        {plan.addonOptions.length > 0 && (
                          <div className="public-auth-addons">
                            <p><strong>Optional add-ons</strong></p>
                            <p>These are purchased separately and are not included in the selected plan.</p>
                            <div>
                              {plan.addonOptions.map((addon) => (
                                <span key={addon}>
                                  {addon}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </label>
                    );
                  })}
                </div>
              )}

              <div className="public-auth-actions">
                <button 
                  onClick={handleBack}
                  className="public-auth-secondary"
                >
                  <ArrowLeft size={20} /> Back
                </button>
                <button 
                  onClick={handleNext}
                  disabled={plansLoading || plans.length === 0}
                  className="public-auth-primary"
                >
                  Continue <ArrowRight size={20} />
                </button>
              </div>
            </div>
          )}

          {/* STEP 3: Confirmation */}
          {step === 3 && (
            <div aria-busy={isSubmitting}>
              <h2 className="public-auth-step-title">Confirm Registration</h2>
              <p className="public-auth-hint">
                {form.selectedPlan === 'Free'
                  ? 'Review your details before completing registration'
                  : 'Review your details before continuing to payment'}
              </p>

              <div className="public-auth-review">
                <div>
                  <div className="public-auth-review-label">School Name</div>
                  <div>{form.schoolName}</div>
                </div>
                <div>
                  <div className="public-auth-review-label">School ID</div>
                  <div>{form.schoolCode.toUpperCase()}</div>
                </div>
                <div>
                  <div className="public-auth-review-label">Proprietor</div>
                  <div>{form.username}</div>
                </div>
                <div>
                  <div className="public-auth-review-label">Email</div>
                  <div>{form.email}</div>
                </div>
                <div className="public-auth-wide">
                  <div className="public-auth-review-label">Selected Plan</div>
                  <div className="public-auth-review-plan">{plans.find(p => p.name === form.selectedPlan)?.displayName || form.selectedPlan}</div>
                  {form.selectedPlan !== 'Free' && (
                    <div className="public-auth-hint">
                      GH₵ {plans.find(p => p.name === form.selectedPlan)?.baseFee?.toLocaleString()} due now at signup
                    </div>
                  )}
                  {form.selectedPlan !== 'Free' && (
                    <div className="public-auth-hint">
                      Overage above {plans.find(p => p.name === form.selectedPlan)?.includedStudents} students will be billed later based on actual active students.
                    </div>
                  )}
                </div>
              </div>

              <div className="public-auth-actions">
                <button 
                  onClick={handleBack}
                  disabled={isSubmitting}
                  className="public-auth-secondary"
                >
                  <ArrowLeft size={20} /> Back
                </button>
                <button 
                  onClick={handleRegister}
                  disabled={isSubmitting}
                  className="public-auth-primary"
                >
                  {isSubmitting ? <Loader size={18} className="public-auth-spinner" /> : <ArrowRight size={18} />}
                  {isSubmitting ? 'Creating account...' : form.selectedPlan === 'Free' ? 'Complete Registration' : 'Proceed to Payment'}
                </button>
              </div>

              <p className="public-auth-hint public-auth-confirm-policy">
                By creating a school account, you accept our{' '}
                <button type="button" onClick={() => setShowTerms(true)} className="public-auth-link">Terms of Service</button>,{' '}
                <button type="button" onClick={() => setShowPrivacy(true)} className="public-auth-link">Privacy Policy</button>, and{' '}
                <button type="button" onClick={() => setShowRetention(true)} className="public-auth-link">Data Retention Policy</button>.
              </p>

              <p className="public-auth-hint">
                Registration also confirms acceptance of the Data Processing Agreement and this onboarding notice's disclosure of EduPulse SMT's planned use of irreversibly de-identified, aggregated school-performance data for benchmarking, research, and system optimization.
              </p>

              <p className="public-auth-hint">
                By completing registration, you confirm all information is accurate.
              </p>
            </div>
          )}

          <TermsModal isOpen={showTerms} onClose={() => setShowTerms(false)} />
          <PrivacyModal isOpen={showPrivacy} onClose={() => setShowPrivacy(false)} />
          <DataRetentionModal isOpen={showRetention} onClose={() => setShowRetention(false)} />
          <DataProcessingModal isOpen={showDataProcessing} onClose={() => setShowDataProcessing(false)} />

          <aside className="public-auth-help">
            <details>
              <summary>Registration support</summary>
              <p>{publicContent.auth?.register_support_note || DEFAULT_PUBLIC_CONTENT.auth.register_support_note}</p>
              <div>
              <p>Email: <a href={`mailto:${publicContent.support?.email || DEFAULT_PUBLIC_CONTENT.support.email}`}>{publicContent.support?.email || DEFAULT_PUBLIC_CONTENT.support.email}</a></p>
              <p>Phone/WhatsApp: <a href={`tel:${(publicContent.support?.phone || DEFAULT_PUBLIC_CONTENT.support.phone).replace(/\s+/g, '')}`}>{publicContent.support?.phone || DEFAULT_PUBLIC_CONTENT.support.phone}</a></p>
            </div>
              <p>Typical response time: {publicContent.support?.response_time || DEFAULT_PUBLIC_CONTENT.support.response_time}.</p>
            </details>
          </aside>
      </section>
    </PublicSiteLayout>
  );
}