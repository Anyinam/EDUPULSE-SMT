import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Check, LoaderCircle, RotateCcw, X } from 'lucide-react';
import axios from 'axios';
import PublicSiteLayout from '../components/PublicSiteLayout';
import TermsModal from '../components/TermsModal';
import PrivacyModal from '../components/PrivacyModal';
import DataRetentionModal from '../components/DataRetentionModal';
import '../styles/public-pricing.css';

const money = (amount) => `GH\u20b5 ${amount.toLocaleString('en-GH', { maximumFractionDigits: 2 })}`;
const numericFields = ['base_fee_per_term', 'included_students', 'price_per_student_per_term'];

function preparePlans(data) {
  if (!Array.isArray(data)) throw new Error('Missing plans');
  return ['Free Tier', 'Basic', 'Premium'].map((name) => {
    const plan = data.find((item) => item.name === name);
    if (!plan || numericFields.some((field) => plan[field] === null || plan[field] === undefined || String(plan[field]).trim() === '' || !Number.isFinite(Number(plan[field])) || Number(plan[field]) < 0)) {
      throw new Error('Incomplete pricing');
    }
    const returnedLimit = Number(plan.max_students);
    const capacity = Number.isFinite(returnedLimit) && returnedLimit > 0
      ? returnedLimit
      : name === 'Free Tier' ? 50 : name === 'Basic' ? 200 : Infinity;
    return {
      ...plan,
      baseFee: Number(plan.base_fee_per_term),
      includedStudents: Number(plan.included_students),
      extraRate: Number(plan.price_per_student_per_term),
      capacity,
      marketing_features: Array.isArray(plan.marketing_features) ? plan.marketing_features : [],
      addon_options: Array.isArray(plan.addon_options) ? plan.addon_options : [],
    };
  });
}

export default function PricingComparison() {
  const [showTerms, setShowTerms] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [showRetention, setShowRetention] = useState(false);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [studentInput, setStudentInput] = useState('100');

  useEffect(() => {
    let active = true;
    async function fetchPlans() {
      setLoading(true);
      setError(false);
      try {
        const response = await axios.get('/api/subscription/plans');
        const nextPlans = preparePlans(response.data?.plans);
        if (active) setPlans(nextPlans);
      } catch {
        if (active) setError(true);
      } finally {
        if (active) setLoading(false);
      }
    }
    fetchPlans();
    return () => { active = false; };
  }, [attempt]);

  const students = Number(studentInput);
  const validStudents = studentInput.trim() !== '' && Number.isSafeInteger(students) && students >= 0;
  const validTotals = validStudents && plans.every((plan) => Number.isFinite(plan.baseFee + Math.max(0, students - plan.includedStudents) * plan.extraRate));

  return (
    <PublicSiteLayout>
      <div className="public-pricing">
        <section className="public-container public-pricing-intro" aria-labelledby="pricing-title">
          <p className="public-eyebrow">Plans for your school</p>
          <h1 id="pricing-title">EduPulse SMT pricing</h1>
          <p className="public-pricing-lead">Compare school operations, included students and term costs. Choose the capacity and tools your school needs.</p>
          <a href="#pricing-plans" className="public-text-link">Compare plans <ArrowRight size={17} aria-hidden="true" /></a>
        </section>

        <section className="public-pricing-comparison" id="pricing-plans" aria-labelledby="plans-title">
          <div className="public-container">
            <div className="public-pricing-calculator">
              <div>
                <h2 id="plans-title">Your school. Your term cost.</h2>
                <p>Estimates use active students and exclude optional add-ons. Paid plans include a base fee and a charge for students above the included allowance.</p>
              </div>
              <div className="public-pricing-input">
                <label htmlFor="pricing-students">Active students</label>
                <input id="pricing-students" type="number" min="0" step="1" inputMode="numeric" value={studentInput} onChange={(event) => setStudentInput(event.target.value)} aria-invalid={!validTotals} aria-describedby="pricing-count-help" />
                <p id="pricing-count-help">{validTotals ? 'Whole numbers, including zero.' : 'Enter a finite, whole student count of 0 or more.'}</p>
              </div>
            </div>

            {loading && <div className="public-pricing-status" role="status"><LoaderCircle size={20} className="public-pricing-spinner" aria-hidden="true" /> Loading current plans...</div>}
            {error && <div className="public-pricing-status public-pricing-error" role="alert"><div><strong>Current pricing is unavailable.</strong><p>We could not load the latest plans. Please retry to see prices and term estimates.</p></div><button type="button" className="public-button public-button-outline" onClick={() => setAttempt((value) => value + 1)}><RotateCcw size={16} aria-hidden="true" /> Retry loading plans</button></div>}

            {plans.length > 0 && !error && <div className="public-pricing-grid">
              {plans.map((plan) => {
                const isFree = plan.name === 'Free Tier';
                const unavailable = validStudents && students > plan.capacity;
                const extraStudents = validStudents ? Math.max(0, students - plan.includedStudents) : 0;
                const total = plan.baseFee + extraStudents * plan.extraRate;
                const features = plan.marketing_features.filter((feature) => !/receipt printing/i.test(feature.name));
                return (
                  <article key={plan.name} aria-labelledby={`pricing-${plan.name.replace(/\s/g, '-')}`} className={`public-pricing-plan${plan.popular ? ' public-pricing-plan-featured' : ''}`}>
                    <div className="public-pricing-plan-heading">
                      <h3 id={`pricing-${plan.name.replace(/\s/g, '-')}`}>{plan.display_name || plan.name}</h3>
                      {plan.popular && <span className="public-pricing-popular">Popular</span>}
                    </div>
                    <p className="public-pricing-description">{plan.description}</p>
                    <p className="public-pricing-price">{money(plan.baseFee)}<span>/ term</span></p>
                    <p className="public-pricing-price-label">{isFree ? 'Free plan' : 'Base platform fee'}</p>
                    <div className="public-pricing-allowance">
                      <p>{isFree ? `Up to ${plan.capacity} students included` : `${plan.includedStudents} students included`}</p>
                      <p>{isFree ? 'Unavailable above the student limit.' : `${money(plan.extraRate)} per extra student / term`}</p>
                      {!isFree && <p>{Number.isFinite(plan.capacity) ? `Available for up to ${plan.capacity} students.` : 'No student capacity limit.'}</p>}
                    </div>
                    <div className="public-pricing-estimate" aria-live="polite" aria-atomic="true">
                      <span>Estimated term cost</span>
                      <output aria-label="Estimated term cost">{!validTotals ? 'Enter a valid student count' : unavailable ? `Unavailable above ${plan.capacity} students` : money(total)}</output>
                      <p>{validTotals && !unavailable ? isFree ? `For ${students} active students` : `${money(plan.baseFee)} base + ${extraStudents} extra students at ${money(plan.extraRate)}` : 'No term quote available for this student count.'}</p>
                    </div>
                    <Link to="/register" className={`public-button${plan.popular ? '' : ' public-button-outline'}`}>{isFree ? 'Create free account' : 'Create account'}<ArrowRight size={17} aria-hidden="true" /></Link>
                    <p className="public-pricing-account-note">{isFree ? 'Choose Free during registration.' : 'Choose your plan during registration.'}</p>
                    <div className="public-pricing-features">
                      <h4>Plan features</h4>
                      <ul>
                        <li><Check size={17} aria-hidden="true" /><span>Receipt printing included</span></li>
                        {features.map((feature, index) => <li key={`${feature.name}-${index}`} className={feature.included ? '' : 'public-pricing-not-included'}>{feature.included ? <Check size={17} aria-hidden="true" /> : <X size={17} aria-hidden="true" />}<span className={feature.bold ? 'public-pricing-feature-bold' : ''}>{feature.name}{!feature.included && <span className="public-pricing-sr-only"> (not included)</span>}{feature.note && <small>{feature.note}</small>}</span></li>)}
                      </ul>
                    </div>
                    {plan.packaging_summary && <p className="public-pricing-summary">{plan.packaging_summary}</p>}
                  </article>
                );
              })}
            </div>}
          </div>
        </section>

        <section className="public-container public-pricing-details" aria-label="Trial and optional add-ons">
          <div className="public-pricing-trial">
            <p className="public-eyebrow">Try before moving up</p>
            <h2>A one-time, 30-day trial</h2>
            <p>Each school can use one plan trial, lasting 30 days from activation. Free schools can trial School OS or School OS Plus; School OS schools can trial School OS Plus.</p>
            <p>The School OS Plus trial temporarily includes AI Pack and Automation Pack access. Trial activation is separate from account creation.</p>
            <p>When the trial ends, your school returns to its base plan unless you activate a paid upgrade. Recorded payment receipts remain available on every plan.</p>
          </div>
          <div className="public-pricing-addons">
            <p className="public-eyebrow">Separate from your plan</p>
            <h2>Optional add-ons</h2>
            <p>Add-ons are optional for paid plans and are not bundled into the base fee or calculator estimates.</p>
            {!loading && !error && plans.filter((plan) => plan.addon_options.length > 0).map((plan) => <div className="public-pricing-addon-row" key={plan.name}><h3>{plan.display_name || plan.name}</h3><ul>{plan.addon_options.map((addon) => <li key={addon}><Check size={16} aria-hidden="true" />{addon}</li>)}</ul></div>)}
            {(loading || error) && <p>Add-on options and prices will appear when current plans load.</p>}
          </div>
        </section>

        <section className="public-pricing-billing" aria-labelledby="pricing-billing-title">
          <div className="public-container">
            <h2 id="pricing-billing-title">Understanding the estimate</h2>
            <div className="public-pricing-billing-grid">
              <div><h3>Per academic term</h3><p>Paid term costs are the base fee plus any active students above the included allowance. The Free plan is unavailable above 50 students; School OS is unavailable above 200.</p></div>
              <div><h3>Mid-term activation</h3><p>New paid activations after trial are prorated to the remaining days in the current term. This calculator shows a full-term estimate, not a prorated invoice.</p></div>
              <div><h3>Receipts on every plan</h3><p>Receipt printing is included on Free, School OS and School OS Plus. Payment tracking and reconciliation are separate features, as shown in the plan comparison.</p></div>
            </div>
          </div>
        </section>

        <section className="public-container public-pricing-policies" aria-label="Account policies">
          <p>By creating a school account, you accept our Terms of Service, Privacy Policy and Data Retention Policy.</p>
          <div><button type="button" onClick={() => setShowTerms(true)}>Terms of Service</button><button type="button" onClick={() => setShowPrivacy(true)}>Privacy Policy</button><button type="button" onClick={() => setShowRetention(true)}>Data Retention Policy</button></div>
        </section>
      </div>
      <TermsModal isOpen={showTerms} onClose={() => setShowTerms(false)} />
      <PrivacyModal isOpen={showPrivacy} onClose={() => setShowPrivacy(false)} />
      <DataRetentionModal isOpen={showRetention} onClose={() => setShowRetention(false)} />
    </PublicSiteLayout>
  );
}
