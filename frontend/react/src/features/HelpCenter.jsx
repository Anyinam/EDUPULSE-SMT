import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const DEFAULT_HELP_CONTENT = {
  faqs: [
    {
      question: 'How do I upload students in bulk?',
      answer: 'Go to Admissions, use the CSV upload section, and ensure required columns match the template.',
    },
    {
      question: 'Who can approve terminal reports?',
      answer: 'Homeroom submits, Headmaster reviews, and Proprietor gives final approval based on workflow.',
    },
    {
      question: 'Do diagnostic mock strands appear on terminal reports?',
      answer: 'Yes. When a teacher adds diagnostic strands in Report Builder, they appear in a separate Diagnostic Strand Insights section on terminal reports and also support SHS pathway guidance.',
    },
    {
      question: 'How do I reset my password?',
      answer: 'Use Forgot Password on the login page, then verify your email reset link.',
    },
  ],
  tutorials: [],
  feature_guides: [
    {
      title: 'Admissions & Student Import',
      body: 'Admit individual students, use CSV upload for bulk admissions, and manage class placement.',
    },
    {
      title: 'Staff & HR Setup',
      body: 'Create teacher, homeroom, headmaster, finance, and inventory accounts from Staff & HR.',
    },
    {
      title: 'Terminal Reports & Diagnostics',
      body: 'Homeroom teachers can add optional diagnostic strand scores in Report Builder. Weak strands are highlighted on the printed terminal report and help shape academic guidance.',
    },
  ],
  security_alerts: [],
  support: {
    email: 'support@edupulse.com',
    phone: '+233 552 141 384',
    response_time: 'within 24 hours on business days',
  },
  help_center: {
    title: 'Help Center',
    subtitle: 'Search FAQs, browse feature guides, and find tutorial updates.',
    security_title: 'Scam Alert',
    security_body: 'Protect your school accounts and payment setup. Verify suspicious contact before you share any sensitive information.',
  },
};

export default function HelpCenter() {
  const [content, setContent] = useState(DEFAULT_HELP_CONTENT);
  const [query, setQuery] = useState('');

  useEffect(() => {
    const fetchHelpContent = async () => {
      try {
        const response = await axios.get('/api/public/platform-content');
        setContent((prev) => ({ ...prev, ...response.data }));
      } catch (error) {
        setContent(DEFAULT_HELP_CONTENT);
      }
    };

    fetchHelpContent();
  }, []);

  const normalizedQuery = query.trim().toLowerCase();

  const filteredFaqs = useMemo(() => {
    if (!normalizedQuery) return content.faqs;
    return content.faqs.filter(
      (faq) => faq.question.toLowerCase().includes(normalizedQuery) || faq.answer.toLowerCase().includes(normalizedQuery)
    );
  }, [content.faqs, normalizedQuery]);

  const filteredGuides = useMemo(() => {
    if (!normalizedQuery) return content.feature_guides;
    return content.feature_guides.filter(
      (guide) => guide.title.toLowerCase().includes(normalizedQuery) || guide.body.toLowerCase().includes(normalizedQuery)
    );
  }, [content.feature_guides, normalizedQuery]);

  const filteredTutorials = useMemo(() => {
    if (!normalizedQuery) return content.tutorials;
    return content.tutorials.filter(
      (tutorial) => tutorial.title.toLowerCase().includes(normalizedQuery) || tutorial.url.toLowerCase().includes(normalizedQuery)
    );
  }, [content.tutorials, normalizedQuery]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-800">{content.help_center.title}</h1>
        <p className="text-slate-500 mt-1">{content.help_center.subtitle}</p>
      </div>

      <section className="mb-6 rounded-2xl border border-red-200 bg-linear-to-r from-red-50 via-amber-50 to-white p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 text-xl">🛡️</div>
          <div>
            <h2 className="text-lg font-bold text-red-900">{content.help_center.security_title}</h2>
            <p className="mt-1 text-sm text-red-800">{content.help_center.security_body}</p>
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              {content.security_alerts.map((alert) => (
                <li key={alert} className="flex items-start gap-2">
                  <span className="mt-0.5 text-red-600">•</span>
                  <span>{alert}</span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-sm font-semibold text-slate-800">
              Official support:{' '}
              <a href={`mailto:${content.support.email}`} className="text-blue-700 hover:underline">{content.support.email}</a>
              {' '}|{' '}
              <a href={`tel:${content.support.phone.replace(/\s+/g, '')}`} className="text-blue-700 hover:underline">{content.support.phone}</a>
            </p>
          </div>
        </div>
      </section>

      <div className="mb-6 bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search help topics..."
          className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-all"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <h2 className="text-lg font-bold text-slate-800 mb-4">Frequently Asked Questions</h2>
          <div className="space-y-3">
            {filteredFaqs.length === 0 ? <p className="text-sm text-slate-500">No FAQ matches your search.</p> : null}
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
            {filteredGuides.length === 0 ? <p className="text-sm text-slate-500">No feature guide matches your search.</p> : null}
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
        <p className="text-xs text-slate-500 mt-4">Support response time: {content.support.response_time}</p>
      </section>
    </div>
  );
}