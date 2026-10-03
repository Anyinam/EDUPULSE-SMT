import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Check, Users, ClipboardCheck, Receipt, BookOpen, ShieldCheck, GraduationCap } from 'lucide-react';
import PublicSiteLayout from '../components/PublicSiteLayout';

const operations = [
  { icon: Users, title: 'A complete student record', text: 'Keep admissions, guardian details and learner documents together, from enrolment to graduation.' },
  { icon: ClipboardCheck, title: 'A clearer school day', text: 'Connect attendance, feeding and staff responsibilities, with the right access for each role.' },
  { icon: Receipt, title: 'Confidence in every payment', text: 'Print recorded receipts on every plan. Add payment tracking and reconciliation as your school grows.' },
  { icon: BookOpen, title: 'Reporting that works together', text: 'Bring grades, lesson notes and terminal reports into a coordinated review and approval process.' },
];

export default function PublicHome() {
  return (
    <PublicSiteLayout>
      <section className="public-hero">
        <img className="public-hero-photo" src="/images/ghana-classroom.jpg" alt="Ghanaian students reading together in a classroom in Amanya, Oti Region" fetchPriority="high" />
        <div className="public-hero-shade" />
        <div className="public-container public-hero-content">
          <p className="public-eyebrow">A better way to run your school</p>
          <h1>EduPulse SMT</h1>
          <p className="public-hero-lead">Less administration. <br />More room for education.</p>
          <p className="public-hero-description">Bring your students, staff, school fees and academic records together. One connected platform for the people behind every school day.</p>
          <div className="public-actions"><Link to="/register" className="public-button">Create free account <ArrowRight size={18} /></Link><a href="#school-operations" className="public-text-link">Explore the platform <ArrowRight size={18} /></a></div>
          <p className="public-hero-note"><Check size={16} /> Free for up to 50 students. Grow at your own pace.</p>
        </div>
        <div className="public-hero-caption">For the work that makes learning possible.</div>
      </section>
      <section className="public-intro public-container" id="why-edupulse">
        <p className="public-eyebrow">Why EduPulse SMT</p>
        <div className="public-intro-grid"><h2>A school runs on people. <br />Give them a better system.</h2><p>Your proprietor, headmaster, teachers and finance team should work from the same records, not disconnected spreadsheets. EduPulse connects the daily work while keeping responsibilities clear.</p></div>
        <div className="public-principles"><span><ShieldCheck size={20} /> Role-based access</span><span><GraduationCap size={20} /> School-centred workflows</span><span><Receipt size={20} /> Receipts on every plan</span></div>
      </section>
      <section className="public-operations" id="school-operations">
        <div className="public-container">
          <div className="public-section-heading"><div><p className="public-eyebrow">One connected school</p><h2>The essentials. <br />Working together.</h2></div><Link to="/pricing" className="public-text-link">Find your plan <ArrowRight size={18} /></Link></div>
          <div className="public-operation-grid">{operations.map(({ icon: Icon, title, text }, index) => <article key={title}><div className={`public-operation-icon tone-${index}`}><Icon size={25} /></div><h3>{title}</h3><p>{text}</p></article>)}</div>
        </div>
      </section>
      <section className="public-workflow public-container">
        <div><p className="public-eyebrow">Designed for real school life</p><h2>From the first admission <br />to the final report.</h2><p>Every team has its part to play. Keep the handovers organised, the records accessible and the next step clear.</p><Link to="/register" className="public-text-link">Start with your school <ArrowRight size={18} /></Link></div>
        <ol>{[['01', 'Welcome your learners', 'Build student records and manage admissions.'], ['02', 'Coordinate the day', 'Keep staff, attendance and feeding in step.'], ['03', 'Close the loop', 'Review reports and preserve payment receipts.']].map(([number, title, text]) => <li key={number}><span>{number}</span><div><h3>{title}</h3><p>{text}</p></div><Check size={19} /></li>)}</ol>
      </section>
      <section className="public-plan-band"><div className="public-container public-plan-band-inner"><div><p className="public-eyebrow">Start small. Build with confidence.</p><h2>A plan for your next chapter.</h2><p>Start free with up to 50 students. Move to School OS or School OS Plus when you need more operational capacity.</p></div><Link to="/pricing" className="public-button public-button-outline">Explore pricing <ArrowRight size={18} /></Link></div></section>
      <section className="public-final public-container"><p className="public-eyebrow">Your school, connected</p><h2>Make the next school day <br />a little simpler.</h2><Link to="/register" className="public-button">Create free account <ArrowRight size={18} /></Link><p>Already part of EduPulse? <Link to="/login">Log in to your school <ArrowRight size={14} /></Link></p></section>
    </PublicSiteLayout>
  );
}