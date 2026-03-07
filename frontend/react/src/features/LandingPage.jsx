import React from 'react';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white font-sans text-slate-800">
      {/* Navigation */}
      <nav className="flex justify-between items-center p-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          {/* Logo */}
          <div className="w-10 h-10 bg-blue-900 rounded-lg flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-blue-200">E</div>
          <span className="text-2xl font-black text-blue-900 tracking-tighter">EDUPULSE</span>
        </div>
        <div className="flex gap-4">
            <a href="/login" className="px-6 py-2 bg-blue-900 text-white rounded-xl font-bold hover:bg-blue-800 transition-all shadow-lg shadow-blue-100">
              Client Login
            </a>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="max-w-7xl mx-auto px-6 py-20 lg:py-32 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
        <div>
          <span className="text-blue-600 font-bold tracking-widest uppercase text-xs mb-2 block">Governance & Revenue Protection</span>
          <h1 className="text-5xl lg:text-7xl font-black text-slate-900 leading-tight mb-6">
            Stop Revenue Leakage in Your School.
          </h1>
          <p className="text-lg text-slate-600 mb-8 leading-relaxed">
            EduPulse combines <strong>AI-driven academic insights</strong> with <strong>financial auditing</strong> to prevent student dropouts and eliminate canteen waste.
          </p>
          <div className="flex gap-4">
            <a href="/register" className="px-8 py-4 bg-orange-500 text-white rounded-2xl font-bold text-lg hover:bg-orange-600 transition-all shadow-xl shadow-orange-200">
              Get Started
            </a>
            <a href="#features" className="px-8 py-4 bg-slate-100 text-slate-700 rounded-2xl font-bold text-lg hover:bg-slate-200 transition-all">
              Learn More
            </a>
          </div>
        </div>
        <div className="relative">
            <div className="absolute -inset-4 bg-blue-100 rounded-full blur-3xl opacity-50"></div>
            <img 
                src="https://images.unsplash.com/photo-1522202176988-66273c2fd55f?ixlib=rb-4.0.3&auto=format&fit=crop&w=1471&q=80" 
                alt="School Governance" 
                className="relative rounded-3xl shadow-2xl border-4 border-white transform rotate-2 hover:rotate-0 transition-all duration-500"
            />
        </div>
      </header>

      {/* Features Grid */}
      <section id="features" className="bg-slate-50 py-24">
        <div className="max-w-7xl mx-auto px-6">
            <div className="text-center mb-16">
                <h2 className="text-3xl font-black text-slate-900 mb-4">Why Top Proprietors Choose EduPulse</h2>
                <p className="text-slate-500 max-w-2xl mx-auto">We replace guesswork with data. From the canteen to the classroom, every operation is tracked.</p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100 hover:shadow-md transition-all">
                    <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center text-2xl mb-6">🧠</div>
                    <h3 className="text-xl font-bold mb-3">Sack-Risk Pulse AI</h3>
                    <p className="text-slate-500 leading-relaxed">Predicts which students are likely to drop out based on financial arrears and academic decline.</p>
                </div>
                <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100 hover:shadow-md transition-all">
                    <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center text-2xl mb-6">🍲</div>
                    <h3 className="text-xl font-bold mb-3">Zero-Waste Canteen</h3>
                    <p className="text-slate-500 leading-relaxed">Daily kitchen manifests generated from morning attendance ensure you never cook excess food.</p>
                </div>
                <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100 hover:shadow-md transition-all">
                    <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center text-2xl mb-6">📱</div>
                    <h3 className="text-xl font-bold mb-3">Remote Oversight</h3>
                    <p className="text-slate-500 leading-relaxed">Traveling? Monitor live revenue collection and staff activities from anywhere in the world.</p>
                </div>
            </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 py-12 border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row justify-between items-center">
            <div className="flex items-center gap-2 mb-4 md:mb-0">
                <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center text-white font-bold">E</div>
                <span className="text-white font-bold tracking-tight">EDUPULSE</span>
            </div>
            <p className="text-sm">© 2026 EduPulse Systems. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}