import React from 'react';

export default function TermsModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="p-6 border-b border-slate-100 flex justify-between items-center">
          <h3 className="text-xl font-bold text-slate-800">Terms of Service</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 font-bold text-xl">×</button>
        </div>
        
        <div className="p-6 overflow-y-auto text-slate-600 text-sm leading-relaxed space-y-4">
          <p><strong>1. Agreement to Terms</strong><br/>By creating an account, accessing, or using EduPulse Professional, you confirm that you have read, understood, and agree to these Terms of Service, our Privacy Policy, and related lawful-use policies published by EduPulse Professional.</p>
          <p><strong>2. Governing Legal and Regulatory Context</strong><br/>Use of the platform must comply with applicable law, including the Data Protection Act, 2012 (Act 843), the Cybersecurity Act, 2020 (Act 1038), and the Electronic Transactions Act, 2008 (Act 772), in addition to any binding regulations or lawful directives issued by competent authorities.</p>
          <p><strong>3. School Authority and Lawful Processing</strong><br/>The registering school represents that it is duly authorised to submit and manage data uploaded to EduPulse Professional and that it will maintain a lawful basis for processing student, parent or guardian, staff, admissions, and examination-related records under applicable law.</p>
          <p><strong>4. Policy Acceptance at Registration</strong><br/>Registration confirms acceptance of the EduPulse Professional policy bundle, including data-protection and retention terms. The school is responsible for implementing internal governance and parent or guardian communication practices consistent with its legal obligations and school policy.</p>
          <p><strong>5. Acceptable Use and Prohibited Conduct</strong><br/>You must not use the platform for unlawful surveillance, unauthorised data disclosure, identity misuse, credential sharing, harmful activity, or any action that compromises system security, service integrity, or rights of data subjects.</p>
          <p><strong>6. Account Security and Access Control</strong><br/>Each school is responsible for safeguarding usernames, passwords, and role permissions within its tenant. Actions performed using valid credentials are attributable to the corresponding user or school account holder, subject to applicable law.</p>
          <p><strong>7. Service Availability and Changes</strong><br/>EduPulse Professional may improve, modify, suspend, or retire features to maintain performance, security, legal compliance, or operational continuity. Reasonable efforts are made to communicate material changes in advance where practicable.</p>
          <p><strong>8. Subscription, Billing, and Feature Access</strong><br/>Feature availability depends on active subscription plan and payment status. Paid features may be limited, suspended, or revoked where payment obligations are overdue, reversed, disputed, or otherwise non-compliant with billing terms.</p>
          <p><strong>9. Intellectual Property</strong><br/>EduPulse Professional retains all rights to platform software, trademarks, interface assets, and service documentation except where otherwise stated. Schools retain ownership of their submitted institutional and learner records, subject to rights necessary for service delivery and legal compliance.</p>
          <p><strong>10. Data Protection and International Scope</strong><br/>EduPulse Professional applies privacy and security controls appropriate to educational data handling. Where processing involves EEA or UK data subjects, GDPR-aligned safeguards and principles are applied to the extent required by applicable law.</p>
          <p><strong>11. Suspension and Termination</strong><br/>EduPulse Professional may suspend or terminate access for material breach, legal risk, security incidents, abuse, fraudulent activity, or other conduct that threatens users, data subjects, or platform operations, subject to applicable legal and contractual requirements.</p>
          <p><strong>12. Limitation of Liability</strong><br/>To the maximum extent permitted by law, EduPulse Professional is not liable for indirect, incidental, consequential, or special damages arising from service use, interruption, or misuse. Nothing in these terms excludes liability that cannot be excluded under applicable law.</p>
          <p><strong>13. Updates to Terms</strong><br/>These terms may be revised from time to time. Continued use after an update takes effect constitutes acceptance of the revised terms, unless a different acceptance mechanism is required by law.</p>
          <p><strong>14. Governing Law and Dispute Resolution</strong><br/>These terms are governed by the laws of the Republic of Ghana. Parties should first attempt good-faith resolution through written notice and senior-level engagement. If unresolved, the dispute may be referred to a competent court in Ghana. Where both parties expressly agree in writing, disputes may be submitted to arbitration in Accra under agreed procedural rules and any resulting award may be enforced by a court of competent jurisdiction.</p>
          <p><strong>15. Contact</strong><br/>For legal, compliance, or contractual questions, contact danielasareanyinam2020@gmail.com.</p>
        </div>

        <div className="p-6 border-t border-slate-100 bg-slate-50 rounded-b-2xl flex justify-end">
          <button onClick={onClose} className="bg-slate-800 text-white px-6 py-2 rounded-xl font-bold hover:bg-slate-700">
            I Understand
          </button>
        </div>
      </div>
    </div>
  );
}