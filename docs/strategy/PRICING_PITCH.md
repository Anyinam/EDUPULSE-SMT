# EduPulse SMT Pricing Pitch

This document reflects the current runtime pricing model implemented in the application. The operational source of truth remains backend/subscription_features.py, with support references in PRICING_FEATURES.csv and PRICING_TABLE.txt.

## Positioning

EduPulse now sells in three layers:

- Free: low-friction entry for setup and light record keeping.
- School OS: the core paid operating system for day-to-day school management.
- School OS Plus: the governance and scale layer for larger schools.
- Optional add-ons: AI Pack and Automation Pack for schools that need those workflows without forcing every paid customer to subsidize them.

That structure fixes the earlier pricing problem. The old jump from Basic to Premium was too steep and bundled too much value into the top tier. The current model separates operational scale from optional AI and payment automation.

## Live Pricing

### Free

- Price: GH₵ 0
- Capacity: 50 students, 1 class
- Best fit: pilots, very small schools, early onboarding

### School OS

- Price: GH₵ 300 per term base
- Included students: 50
- Overage: GH₵ 7 per additional student per term
- Capacity cap: 200 students, 5 classes
- Best fit: the mainstream Ghana private/basic school segment that needs full operations but not advanced governance tooling

Examples:

- 30 students: GH₵ 300 per term, GH₵ 900 per year
- 100 students: GH₵ 650 per term, GH₵ 1,950 per year
- 150 students: GH₵ 1,000 per term, GH₵ 3,000 per year

### School OS Plus

- Price: GH₵ 600 per term base
- Included students: 100
- Overage: GH₵ 9 per additional student per term
- Capacity cap: unlimited students, classes, and staff
- Best fit: larger schools that need stronger reporting, reconciliation, and admin controls

Examples:

- 30 students: GH₵ 600 per term, GH₵ 1,800 per year
- 100 students: GH₵ 600 per term, GH₵ 1,800 per year
- 150 students: GH₵ 1,050 per term, GH₵ 3,150 per year
- 200 students: GH₵ 1,500 per term, GH₵ 4,500 per year

### Optional Add-Ons

- AI Pack: GH₵ 200 per term
- Automation Pack: GH₵ 250 per term

Add-ons are available only on paid base plans. They can now be enabled through proprietor checkout instead of manual internal toggles.

## Packaging Logic

### What School OS Includes

- Full attendance, feeding, grades, and lesson-note workflows
- Finance, inventory, alerts, and student support operations
- AI Registrar admissions workflow
- Standard proprietor reporting and core transaction visibility

School OS should feel complete for a normal school operator. It is not a teaser tier.

### What School OS Plus Adds

- Unlimited scale
- Advanced analytics
- Stronger payment reconciliation workflows
- Custom HTML report-template uploads
- Higher-governance reporting and administrative visibility

School OS Plus is for scale and governance, not for every premium-sounding feature.

### What the AI Pack Adds

- AI Student Pulse
- Student Rescue Agent
- AI-generated narratives
- Exam Intelligence
- AI admissions question generation and related academic intelligence flows

This keeps advanced AI monetized without forcing every paid school to pay for it.

### What the Automation Pack Adds

- MoMo webhook automation
- Bank transfer webhook automation
- Automatic payment categorization
- Duplicate payment prevention
- Real-time balance updates from automated payment flows

This isolates the higher-cost payment automation workflows into a separate product line.

## Trial Strategy

Trials are now plan-selectable instead of being hardcoded to School OS Plus only.

- Each school gets one 30-day subscription trial.
- Free schools can choose School OS or School OS Plus.
- School OS schools can choose School OS Plus.
- School OS Plus trial temporarily includes AI Pack and Automation Pack access.
- Trial conversion remains prorated to the remaining current-term days.

This is a stronger sales tool because it lets smaller schools try the right commercial step instead of forcing every prospect into the highest package.

## Why This Model Is Better

### Better conversion path

The first paid step is now materially easier to say yes to. GH₵ 300 per term is a more credible operational entry point than the previous structure.

### Better margin control

AI and webhook automation remain monetized separately. That protects gross margin and avoids bundling expensive features into the default paid seat.

### Better story in sales

The pitch becomes simple:

- Start free.
- Move to School OS when you need full operations.
- Move to School OS Plus when you need scale and governance.
- Add AI Pack or Automation Pack only if those workflows matter to your school.

### Better for Ghana school buying behavior

Most schools do not buy software like enterprise departments. They buy in practical steps. A professional pricing ladder should mirror that decision pattern.

## Recommended Sales Language

### Free

Use for onboarding and low-friction adoption.

Suggested framing:
"Start with EduPulse Free while you centralize records and get your staff used to the system."

### School OS

Lead with this package in most sales conversations.

Suggested framing:
"School OS gives your school the full day-to-day operating system for attendance, payments, feeding, reports, inventory, and staff workflows."

### School OS Plus

Position this for larger or more disciplined operators.

Suggested framing:
"School OS Plus is for schools that need deeper financial control, stronger reporting, and room to scale without limits."

### AI Pack

Sell this only when the school sees direct value from intervention, narratives, or academic intelligence.

Suggested framing:
"Add the AI Pack when you want EduPulse to help staff spot risk, generate narratives, and support faster academic decisions."

### Automation Pack

Sell this when the pain is reconciliation and payment operations.

Suggested framing:
"Add the Automation Pack when you want payment processing to move from manual follow-up into verified automated workflows."

## Revenue Framing

Illustrative annual examples:

- 70 schools on School OS at 100 students each: 70 x GH₵ 1,950 = GH₵ 136,500
- 30 schools on School OS Plus at 100 students each: 30 x GH₵ 1,800 = GH₵ 54,000
- 25 paid schools on AI Pack: 25 x GH₵ 600 = GH₵ 15,000
- 20 paid schools on Automation Pack: 20 x GH₵ 750 = GH₵ 15,000

Illustrative annual total: GH₵ 220,500

The important point is not the exact forecast. It is that add-ons create a cleaner path to expansion revenue without destabilizing the core entry offer.

## Guardrails

- Internal stored plan keys remain Free Tier, Basic, and Premium for compatibility.
- Public-facing names are Free, School OS, and School OS Plus.
- Paid plan upgrades and add-on activation only apply after successful checkout.
- Feature restrictions are enforced by the subscription feature layer, not by scattered UI-only checks.

## Bottom Line

This pricing model is more professional, easier to sell, safer operationally, and better aligned with how the product is actually implemented today. It gives EduPulse a credible entry tier, a realistic mainstream paid plan, a governance-tier upgrade, and two monetizable expansion packs without confusing the runtime entitlement model.
    # Sack-Risk Prediction

@subscription_required('Premium')
def generate_admission_test():
    # AI Question Generation

# Student capacity limits
if school.subscription_plan == 'Free Tier':
    limit = 50
elif school.subscription_plan == 'Basic':
    limit = 200
else:  # Premium
    limit = float('inf')

# AI features gated
if school.subscription_plan == 'Premium':
    grade_record.ai_narrative = generate_narrative(student)
else:
    grade_record.ai_narrative = "AI Analysis requires Premium Plan."
```

---

## 💰 Pricing Strategy

### AI Employee Add-ons

Recommended packaging model:
- keep the main platform on subscription pricing
- bundle AI Registrar into the current paid subscriptions
- keep Student Rescue Agent and already-shipped Premium AI value bundled in Premium
- sell new workflow workers as optional add-ons
- do not start with per-task AI billing

Bundled now:
- AI Registrar: included in Basic and Premium

Draft add-ons:
- AI Bursar Add-on: GH₵240 to GH₵420 per term for Basic, GH₵180 to GH₵360 per term for Premium
- Communications Automation Add-on: small add-on fee plus message credits or pass-through SMS/WhatsApp cost

Why Basic and Premium add-on prices differ:
- Premium already includes adjacent AI, analytics, and governance surfaces, so the add-on is an incremental expansion
- Basic schools get a larger net-new workflow lift from the same worker
- the worker itself should remain substantively the same for the add-on tier; the price difference reflects surrounding bundled value, not a lower-quality Premium add-on

### Value Proposition by Tier

**Free Tier** (GH₵0)
- **Pitch**: "Test EduPulse risk-free"
- **Conversion Path**: Start small, hit 50-student limit, upgrade
- **Churn Risk**: High (feature limits force upgrade or switch)

**Basic Plan** (GH₵360/term base + GH₵12/student/term = ~GH₵1,080-3,600/year)
- **Pitch**: "Full operational suite for growing schools"
- **ROI**: ~GH₵10-20 per student/month in efficiency gains
- **Upsell**: "AI features unlock at Premium"
- **Target**: 50-200 student schools, 5-10 staff
- **30 students:** GH₵1,080/year (base only)
- **100 students:** GH₵3,600/year (base + 70 × GH₵12 × 3)

**Premium Plan** (GH₵750/term base + GH₵22/student/term = ~GH₵2,250-13,470/year)
- **Pitch**: "Intelligence-driven governance for large schools"
- **ROI**: Predictive AI prevents dropout losses (estimated GH₵2,000+/student saved)
- **Unlimited scaling**: No cap on student growth
- **Target**: 200+ student schools, enterprise needs

---

## 📈 Revenue Potential

### Example School Scenarios

**Scenario 1: Small Primary School (50 students)**
```
Plan: Free Tier
Revenue: GH₵0/month
Conversion: Offer Basic upgrade
```

**Scenario 2: Mid-Size JHS (150 students)**
```
Plan: Basic (GH₵360 base + 120 students × GH₵12/term)
Per Term Cost: GH₵360 + GH₵1,440 = GH₵1,800
Annual Revenue: GH₵5,400 (3 terms)
Staff: 8-10 people
Use Case: Full attendance, grades, basic finance tracking
Upgrade Trigger: Want AI features (hit Premium for GH₵3,390/term with same enrollment)
```

**Scenario 3: Large Secondary School (400+ students)**
```
Plan: Premium
Base Fee: GH₵510/term × 3 terms = GH₵1,530/year
Base Fee: GH₵750/term × 3 terms = GH₵2,250/year
Overage: (400 - 30 students) × GH₵22/term × 3 terms = GH₵24,420/year
Total Annual: GH₵2,250 + GH₵24,420 = GH₵26,670/year
Staff: 20+ people
Use Case: AI risk prediction, automated payments, unlimited growth
Business Impact: Predict & prevent student dropouts
Cost Per Student: GH₵66.68/student/year
```

### Tax Assumptions
```
GH₵200/month Basic:    ~GH₵2,400/year per school
GH₵500/month Premium:  ~GH₵6,000/year per school

Assumed blended rate (70% Basic, 30% Premium):
Average ARR per school: ~GH₵3,480
```

---

### Pitch Key Messages

### For Free Tier Schools
> *"Start free, no credit card. Use all core features to manage your 50 students. **Built-in Ghana Data Protection Act compliance** means you're audit-ready from day one."*

### For Basic Tier Schools
> *"GH₵200/month to run your entire school platform with **production-grade security and compliance**. Managing 150+ students? Every feature you need, encrypted and audit-ready."*

### For Premium Tier Schools
> *"Premium starts at GH₵750/term (includes 30 students), then GH₵22 per additional student per term. **Scales cleanly** from GH₵2,250/year (30 students) to GH₵6,870/year (100 students). **Enhanced DSAR support** means faster regulatory response times."*

### For Schools Growing Faster
> *"With Premium, each new student adds GH₵66/year (GH₵22/term × 3 terms). **Scale transparently** with no per-seat licenses or hidden fees."*

### For Compliance-Conscious Schools
> *"Most schools store data in plain Excel files—**no encryption, no audit trail, no compliance**. EduPulse gives you **Ghana Data Protection Act compliance out of the box**: encrypted data, tamper-proof ledgers, and documented DSAR workflows. **Pass regulatory audits without hiring a compliance team.**"*

---

## 🚀 Conversion Strategies

### Free → Basic
- Hit 50-student limit → Force upgrade prompt
- "You've reached capacity. Upgrade to Basic for 200 students."

### Basic → Premium
- Show locked AI features in dashboard
- "Premium: See which students are at risk of dropping out"
- A/B test: Cost savings from dropout prevention (GH₵2,000+/student saved) vs. GH₵22/student/term cost
- **Growth Advantage**: "Your school just hit 150 students. Premium costs GH₵22/extra student/term (vs. GH₵12/student/term in Basic) and adds the full AI workflow stack."

### Premium Scaling Advantage
- Schools **naturally grow into** Premium pricing
- 30 students: GH₵2,250/year (base fee only)
- 75 students: GH₵5,220/year (base + 45 students)
- 150 students: GH₵10,170/year (base + 120 students)
- **Per-student cost drops as school grows** (better than competing per-seat licensing)

### Bottlenecks for Upgrades
1. **Free Tier**: Student capacity (hard limit at 50)
2. **Basic Tier**: Missing AI & webhooks (soft limit, feature-gated); student limit at 200
3. **Premium**: None (unlimited growth + all features, scalable pricing)

---

## 📊 Competitive Positioning

| Feature | EduPulse | Traditional Solutions |
|---------|----------|----------------------|
| **AI Risk Prediction** | ✅ Premium | Manual / Excel-based |
| **Automated Payments** | ✅ Premium | Manual entry |
| **Multi-Tenant (Schools)** | ✅ All Tiers | Not available |
| **Pricing Entry Point** | ✅ FREE | GH₵200+ immediately |
| **Scalability** | ✅ Unlimited (Premium) | Per-seat license |
| **Data Protection Compliance** | ✅ All Tiers | Not documented |
| **Field-Level Encryption** | ✅ All Tiers | Plain text storage |
| **Tamper-Evident Ledger** | ✅ All Tiers | Manual Excel records |
| **DSAR Workflow Support** | ✅ All Tiers | Manual/ad-hoc |
| **Mandatory Policy Acceptance** | ✅ All Tiers | Not enforced |

---

## 📋 For Your Pitch Deck

### Headline
**"EduPulse: AI-Powered School Operations Platform"**

### Elevator Pitch
```
EduPulse helps Ghana's schools run on data, not guesswork.
- Free tier gets you started (50 students)
- Basic (GH₵200/mo) runs full operations for 150-200 schools
- Premium: GH₵510/term (base) + GH₵17/student/term for students beyond 30
  → Scales from GH₵1,530/year (30 students) to GH₵10,200/year (200 students)
  → Adds AI to predict student risk & automate payments
→ Save GH₵2,000+ per at-risk student before they drop out

✨ Built-in Ghana Data Protection Act compliance across all tiers:
   Encrypted data, tamper-proof ledgers, audit-ready from day one.
```

### Key Metrics for Investors
- TAM: 20,000+ schools in Ghana
- Feature-driven STM (Tier bottlenecks → conversion)
- Blended ARPU: GH₵3,480 (70/30 Basic/Premium mix)
- Churn Incentive: AI outcomes + compliance features prevent switching
- **Compliance Moat**: Built-in Data Protection Act compliance creates switching costs

---

## 💡 Notes for Pitch Meeting

- **Security & compliance built into all tiers** (no add-on fees for critical features)
- **Compliance moat**: Ghana Data Protection Act readiness creates switching costs

⚠️ **Consider Adding**
- Annual discount (e.g., 20% off 12-month commitment)
- Enterprise/Bulk pricing for school districts
- Per-SMS costs for parent notifications (add-on revenue)
- **Compliance certification service** (optional audit support for schools seeking Data Controller certification)

🎯 **Message to Investors**
- **TAM**: 20,000+ schools × GH₵3,210 avg = GH₵64.2M potential ARR
- **GTM**: Free tier as acquisition funnel (freemium play)
- **Retention**: AI features + compliance create stickiness (hard to replicate)
- **Expansion**: Unlimited Premium tier allows full capture
- **Regulatory Advantage**: Ghana Data Protection Commission enforcement increasing → compliance becomes mandatory buyer criterion
- **Switching Costs**: Encrypted data + audit trails + policy documentation = high migration friction
- **Scalable Pricing Model**: Premium revenue grows 2-3x as schools grow naturally (no forced upsells at tier limits)
- **TAM**: 20,000+ schools × GH₵3,480 avg = GH₵69.6M potential ARR
- **GTM**: Free tier as acquisition funnel (freemium play)
- **Retention**: AI features create stickiness (hard to replicate)
- **Expansion**: Unlimited Premium tier allows full capture
