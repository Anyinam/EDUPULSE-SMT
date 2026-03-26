import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const DEFAULT_HELP_CONTENT = {
  faqs: [
    {
      question: 'How do I upload students in bulk?',
      answer: 'Go to Admissions, use the CSV upload section, and ensure required columns match the template.'
    },
    {
      question: 'Who can approve terminal reports?',
      answer: 'Homeroom submits, Headmaster reviews, and Proprietor gives final approval based on workflow.'
    },
    {
      question: 'How do I reset my password?',
      answer: 'Use Forgot Password on the login page, then verify your email reset link.'
    }
  ],
  tutorials: []
};

const FEATURE_GUIDES = [
  {
    title: 'Admissions & Student Import',
    body: 'Admit individual students, use CSV upload for bulk admissions, and manage class placement.'
  },
  {
    title: 'Staff & HR Setup',
    body: 'Create teacher, homeroom, headmaster, finance, and inventory accounts from Staff & HR.'
  },
  {
    title: 'Subscription & Billing',
    body: 'Review plan details, check current enrollment impact, and upgrade plans via Paystack payment.'
  },
  {
    title: 'Reports & Approval Workflow',
    body: 'Generate report cards, run terminal reports, and follow role-based approval flow for publication.'
  }
];

const SECURITY_ALERTS = [
  'EduPulse support will never call, text, or message you to ask for your bank OTP, MoMo OTP, card PIN, CVV, or full password.',
  'Do not approve transfers, share screen-control access, or follow payment instructions from personal numbers claiming to be EduPulse staff.',
  'Only trust payment and account actions started inside your official EduPulse dashboard or confirmed through the official support email and phone lines.',
  'If anything feels suspicious, stop immediately, do not complete the transaction, and contact official support before taking any further step.'
];

export default function HelpCenter() {
  const [helpContent, setHelpContent] = useState(DEFAULT_HELP_CONTENT);
  const [query, setQuery] = useState('');

  useEffect(() => {
    const fetchHelpContent = async () => {
      try {
        const res = await axios.get('/api/public/help-content');
        const faqs = Array.isArray(res.data?.faqs) ? res.data.faqs : DEFAULT_HELP_CONTENT.faqs;
        const tutorials = Array.isArray(res.data?.tutorials) ? res.data.tutorials : [];
        setHelpContent({ faqs, tutorials });
      } catch (err) {
        setHelpContent(DEFAULT_HELP_CONTENT);
      }
    };
    fetchHelpContent();
  }, []);

  const normalizedQuery = query.trim().toLowerCase();

  const filteredFaqs = useMemo(() => {
    if (!normalizedQuery) return helpContent.faqs;
    return helpContent.faqs.filter(
      (faq) =>
        faq.question.toLowerCase().includes(normalizedQuery) ||
        faq.answer.toLowerCase().includes(normalizedQuery)
    );
  }, [helpContent.faqs, normalizedQuery]);

  const filteredGuides = useMemo(() => {
    if (!normalizedQuery) return FEATURE_GUIDES;
    return FEATURE_GUIDES.filter(
      (guide) =>
        guide.title.toLowerCase().includes(normalizedQuery) ||
        guide.body.toLowerCase().includes(normalizedQuery)
    );
  }, [normalizedQuery]);

  const filteredTutorials = useMemo(() => {
    if (!normalizedQuery) return helpContent.tutorials;
    return helpContent.tutorials.filter(
      (tutorial) =>
        tutorial.title.toLowerCase().includes(normalizedQuery) ||
        tutorial.url.toLowerCase().includes(normalizedQuery)
    );
  }, [helpContent.tutorials, normalizedQuery]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-800">Help Center</h1>
        <p className="text-slate-500 mt-1">Search FAQs, browse feature guides, and find tutorial updates.</p>
      </div>

      <section className="mb-6 rounded-2xl border border-red-200 bg-linear-to-r from-red-50 via-amber-50 to-white p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 text-xl">🛡️</div>
          <div>
            <h2 className="text-lg font-bold text-red-900">Scam Alert</h2>
            <p className="mt-1 text-sm text-red-800">
              Protect your school accounts and payment setup. Verify suspicious contact before you share any sensitive information.
            </p>
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              {SECURITY_ALERTS.map((alert) => (
                <li key={alert} className="flex items-start gap-2">
                  <span className="mt-0.5 text-red-600">•</span>
                  <span>{alert}</span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-sm font-semibold text-slate-800">
              Official support: <a href="mailto:support@edupulse.com" className="text-blue-700 hover:underline">support@edupulse.com</a> | <a href="tel:+233552141384" className="text-blue-700 hover:underline">+233 552 141 384</a>
            </p>
          </div>
        </div>
      </section>

      <div className="mb-6 bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search help topics..."
          className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-all"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <h2 className="text-lg font-bold text-slate-800 mb-4">Frequently Asked Questions</h2>
          <div className="space-y-3">
            {filteredFaqs.length === 0 && (
              <p className="text-sm text-slate-500">No FAQ matches your search.</p>
            )}
            {filteredFaqs.map((faq, index) => (
              <details key={`${faq.question}-${index}`} className="group border border-slate-100 rounded-lg p-3">
                <summary className="cursor-pointer font-semibold text-slate-700">{faq.question}</summary>
                <p className="mt-2 text-sm text-slate-600">{faq.answer}</p>
              </details>
            ))}
          </div>
        </section>

        <section className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <h2 className="text-lg font-bold text-slate-800 mb-4">Feature Guides</h2>
          <div className="space-y-3">
            {filteredGuides.length === 0 && (
              <p className="text-sm text-slate-500">No feature guide matches your search.</p>
            )}
            {filteredGuides.map((guide) => (
              <div key={guide.title} className="border border-slate-100 rounded-lg p-3">
                <p className="font-semibold text-slate-700">{guide.title}</p>
                <p className="text-sm text-slate-600 mt-1">{guide.body}</p>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section id="tutorials" className="mt-6 bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <h2 className="text-lg font-bold text-slate-800 mb-2">Video Tutorials</h2>
        <p className="text-sm text-slate-600 mb-3">Tutorial videos are hidden for now and will be enabled after live production launch.</p>
        {filteredTutorials.length > 0 ? (
          <div className="space-y-2 text-sm">
            {filteredTutorials.map((tutorial, index) => (
              <p key={`${tutorial.title}-${index}`} className="text-slate-700">
                {index + 1}. {tutorial.title}
              </p>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">No active tutorial links yet.</p>
        )}
      </section>
    </div>
  );
}