import React from 'react';

export default function PrivacyModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="p-6 border-b border-slate-100 flex justify-between items-center">
          <h3 className="text-xl font-bold text-slate-800">Privacy Policy</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 font-bold text-xl">×</button>
        </div>

        <div className="p-6 overflow-y-auto text-slate-600 text-sm leading-relaxed space-y-4">
          <p><strong>1. Scope and Legal Framework</strong><br/>This Privacy Policy describes how EduPulse SMT collects, uses, stores, and protects personal data processed through the platform. Our privacy and cybersecurity practices are aligned with applicable law, including the Data Protection Act, 2012 (Act 843), the Cybersecurity Act, 2020 (Act 1038), and the Electronic Transactions Act, 2008 (Act 772), together with any relevant regulations, guidance, and lawful orders.</p>
          <p><strong>2. Roles of the Parties</strong><br/>For school-managed records (student, guardian, staff, attendance, academic, finance, and admissions records), the school is generally the Data Controller and EduPulse SMT acts as a Data Processor or service provider on the school&apos;s documented instructions. For account, billing, security, and platform-operational records, EduPulse SMT may act as Data Controller where required by law and legitimate service operation.</p>
          <p><strong>3. Categories of Data Processed</strong><br/>Depending on enabled modules and school use, data may include identity and contact details, student and guardian biodata, attendance records, assessment and report data, payment and billing activity, admissions submissions, communication logs, audit trails, and technical security logs. Schools are responsible for limiting submitted data to what is necessary and lawful for educational administration.</p>
          <p><strong>4. Lawful Basis and School Obligations</strong><br/>Each school remains responsible for establishing and documenting an appropriate lawful basis for processing personal data under Act 843, including parental or guardian notice and consent where required by the school&apos;s legal obligations and internal policies. By using EduPulse SMT, the school confirms it has authority to process and submit data it uploads.</p>
          <p><strong>5. Purpose Limitation and Aggregated Analytics</strong><br/>Personal data is processed only for legitimate school and platform purposes such as admissions operations, student administration, reporting, communication, payment tracking, compliance, and service security. EduPulse SMT does not sell student or guardian personal data, but it may create irreversibly de-identified and aggregated educational statistics for benchmarking, research, system optimization, and related analytics where the source records can no longer reasonably identify a student or named school.</p>
          <p><strong>6. Security Safeguards</strong><br/>EduPulse SMT applies technical and organisational safeguards, including role-based access control, tenant isolation, authenticated access, activity logging, and reasonable security controls designed to reduce unauthorised access, alteration, disclosure, or loss.</p>
          <p><strong>7. Data Retention and Deletion</strong><br/>Data is retained only for as long as needed for contractual service delivery, educational operations, legal compliance, dispute handling, fraud prevention, and security auditing. Retention periods may vary by data type, school policy, and legal requirement. When data is no longer required, it is deleted or anonymised in line with operational and legal constraints.</p>
          <p><strong>8. International Data Protection (GDPR)</strong><br/>Where processing relates to data subjects in the European Economic Area (EEA) or United Kingdom, EduPulse SMT applies GDPR-aligned principles, including lawfulness, fairness, transparency, purpose limitation, data minimisation, accuracy, storage limitation, integrity, and confidentiality, to the extent GDPR applies to the processing activity.</p>
          <p><strong>9. Data Subject Rights</strong><br/>Subject to legal and contractual limits, data subjects may request access, correction, restriction, objection, deletion, and portability of personal data through the responsible school. EduPulse SMT will support controller schools with reasonable technical assistance for rights requests, where applicable.</p>
          <p><strong>10. Incident Response and Notification</strong><br/>If a personal data incident occurs, EduPulse SMT will follow its security and incident-response process, contain and investigate the event, and support required notifications in line with applicable law, contractual commitments, and regulator guidance.</p>
          <p><strong>11. Complaints and Regulatory Engagement</strong><br/>If a data subject or school believes personal data has been handled unlawfully, concerns should first be raised with the school and EduPulse SMT through the contact channel below. Where applicable under Ghana law, complaints may also be escalated to the Data Protection Commission of Ghana or another competent authority.</p>
          <p><strong>12. Policy Updates</strong><br/>This policy may be updated to reflect legal, regulatory, operational, or security changes. Updated versions become effective when published in the platform or otherwise communicated through official channels.</p>
          <p><strong>13. Contact</strong><br/>For privacy, security, or data-protection matters, contact danielasareanyinam2020@gmail.com.</p>
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
