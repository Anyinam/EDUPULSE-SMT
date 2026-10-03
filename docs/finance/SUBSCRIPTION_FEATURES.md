# EduPulse SMT Subscription Feature Matrix

## Overview
EduPulse SMT offers three subscription tiers, each with specific features and resource limits. This document outlines what's included in each plan.

## Trial Expiry Enforcement

Access uses the current effective plan, not cached browser plan labels. After a Premium trial expires on a Free base subscription:

- New payment instructions, account provisioning, payment entry, approvals, recovery, and inventory operations are unavailable.
- Historical transaction history, student payment records, and financial audit reports remain readable by authorized staff on Free Tier. Subscription changes must not hide or delete recorded payment evidence. Historical reads remain available during over-capacity, verification restrictions, and billing suspension; tenant and role checks still apply.
- Payment receipt printing remains available on every plan, including after trial expiry, over-capacity, verification restrictions, and billing suspension. Authorized staff use Payment Receipts to search and print recorded payments; authentication and school isolation still apply. Pending or rejected records retain their actual status and are not represented as confirmed payments.
- Signed incoming payment callbacks are retained as Pending with a PAYMENT_FEATURE_UNAVAILABLE flag. They do not reduce student balances or create confirmed fee ledger entries.
- Attendance edits, feeding configuration edits, bulk imports/status updates, and lesson-note operations require paid access. Basic roster, admissions review, report viewing, branding, calendar, and subscription management remain available.
- New classes and staff respect plan quotas. The proprietor is excluded from the staff quota. Existing records are preserved after downgrade.
- Payment-instruction GET requests reuse stored routes; provider provisioning and route repricing use the guarded virtual-account POST endpoint.
- A failed optional student-profile data request shows a warning for that section without hiding the basic learner or guardian record. Admissions approval copies the dedicated learner passport photo into the student profile from local or durable S3 storage and retains the linked admissions documents.

Ledger confirmation now seals complete metadata before hashing. Existing failed hashes must be investigated against original payment/provider records; do not silently rebuild production hashes to hide the failure. Corrections should preserve the original evidence and be recorded through an audited process.

---

## 📊 Quick Comparison

| Feature | Free Tier | Basic | Premium |
|---------|-----------|-------|---------|
| **Max Classes** | 1 | 5 | ♾️ Unlimited |
| **Max Students** | 50 | 200 | ♾️ Unlimited |
| **Attendance Management** | View Only ❌ | Full Access ✅ | Full Access ✅ |
| **Feeding Records** | View Only ❌ | Full Access ✅ | Full Access ✅ |
| **Grade Entry & Editing** | Not Available ❌ | Full Access ✅ | Full Access ✅ |
| **Lesson Notes** | Not Available ❌ | Full Access ✅ | Full Access ✅ |
| **Report Templates** | 1 Template | All 5 Templates | All 5 + Custom HTML |
| **AI Lesson Analysis** | Not Available ❌ | Basic Feedback ⚡ | Full Analysis ⚡⚡ |
| **AI Grade Narratives** | Not Available ❌ | Not Available ❌ | Full Suite ✅ |
| **Payment Tracking** | Not Available ❌ | Basic Tracking ✅ | Full Reconciliation ✅ |
| **Advanced Analytics** | Not Available ❌ | Not Available ❌ | Full Dashboard ✅ |
| **Custom HTML Templates** | Not Available ❌ | Not Available ❌ | Upload & Use ✅ |
| **Price** | Free | Starts at ₵360/term | Starts at ₵750/term |

---

## 🆓 Free Tier

**Target**: Evaluation and small institutions (1 class only)

### What's Included:
- ✅ Basic school setup and configuration
- ✅ **Attendance**: View-only (teachers cannot record attendance)
- ✅ **Feeding Records**: View-only (cannot record feeding)
- ✅ **Grade Viewing**: Can view grades but not enter them
- ✅ **Report Generation**: Limited to basic template only (gradman_v1)
- ✅ Limited to **1 Class**
- ✅ Limited to **50 Students Max**
- ✅ Limited to **3 Staff Members**

### What's **NOT** Included ❌:
- Grade entry and editing
- Lesson notes planning
- AI analysis of any kind
- Payment tracking
- Advanced reports
- HTML template uploads
- Bulk operations

### Use Case:
- School evaluation period
- Testing the system
- Single classroom pilot

### Access Level:
- **Read-only**: For most features
- **No editing**: Cannot modify attendance or records

---

## 💼 Basic Tier

**Target**: Active schools with up to 5 classes (200 students)

### What's Included:
- ✅ Everything in Free Tier PLUS:
- ✅ **Attendance Management**: Full read/write access
- ✅ **Feeding Records**: Full read/write access (record meals)
- ✅ **Grade Entry**: Full access to enter and edit grades
- ✅ **Lesson Notes**: Create and manage lesson plans with daily phases
- ✅ **Report Templates**: Access to all 5 standard templates
- ✅ **AI Lesson Analysis**: Basic AI feedback on lesson note submissions
- ✅ **Bulk Operations**: Batch attendance/feeding record updates
- ✅ **Basic Payment Tracking**: Record student payments
- ✅ Limited to **5 Classes**
- ✅ Limited to **200 Students Max**
- ✅ Limited to **15 Staff Members**

### What's **NOT** Included ❌:
- AI-generated grade narratives
- Advanced analytics dashboard
- HTML/CSS custom templates
- Full payment reconciliation
- Advanced features

### Use Case:
- Primary/Secondary schools
- Schools with steady operations
- Class-based teaching institutions
- Standard reporting needs

### Access Level:
- **Full Control**: For core features (attendance, grades, lesson notes)
- **Limited AI**: Basic feedback instead of full analysis

---

## 🏆 Premium Tier

**Target**: Large institutions, advanced analytics, unlimited growth

### What's Included:
- ✅ Everything in Basic Tier PLUS:
- ✅ **Unlimited Classes** (♾️)
- ✅ **Unlimited Students** (♾️)
- ✅ **Unlimited Staff**
- ✅ **AI-Generated Grade Narratives**: Automatic narrative generation for each student's report
- ✅ **Full AI Suite**: 
  - Advanced lesson note analysis and scoring
  - Anomaly detection in attendance/performance
  - Predictive analytics
- ✅ **Advanced Analytics Dashboard**: 
  - Comprehensive analytics across all metrics
  - Custom KPI tracking
  - Trend analysis
- ✅ **Custom HTML Templates**: 
  - Upload and use custom HTML/CSS report designs
  - Maintain brand consistency
  - Complex report layouts
- ✅ **Full Payment Reconciliation**: 
  - Complete payment tracking
  - Reconciliation tools
  - Financial reports
- ✅ **Priority Support**: 
  - Priority email/chat support
  - Faster response times

### What's Included ✅:
- Everything - no restrictions

### Use Case:
- Large school networks
- International schools
- Schools with advanced reporting needs
- Schools requiring complete analytics
- Multi-campus operations

### Access Level:
- **Complete Control**: Full access to all features
- **AI-Powered**: Full AI analysis on all applicable features
- **Unlimited**: No quotas or limits

---

## 🔄 Feature Details & Access Levels

### Attendance Management
| Tier | Level | Details |
|------|-------|---------|
| Free | View Only | Can see attendance records but cannot add/edit |
| Basic | Full Access | Can record, edit, and bulk update attendance |
| Premium | Full Access | Same as Basic + advanced analytics |

### Feeding Records
| Tier | Level | Details |
|------|-------|---------|
| Free | View Only | Can see feeding records but cannot record meals |
| Basic | Full Access | Can record meals, update payments, bulk operations |
| Premium | Full Access | Same as Basic + reconciliation tools |

### Grade Entry & Management
| Tier | Level | Details |
|------|-------|---------|
| Free | View Only | Can only view grades (read-only) |
| Basic | Full Access | Can enter, edit, and finalize grades |
| Premium | Full Access | Same as Basic + AI narratives |

### Lesson Notes
| Tier | Level | Details |
|------|-------|---------|
| Free | ❌ Not Available | No access to lesson planning |
| Basic | Full Access | Can create notes with daily phases; basic AI feedback |
| Premium | Full Access | Full access + advanced AI analysis and scoring |

### Report Generation
| Tier | Level | Details |
|------|-------|---------|
| Free | Limited | Can generate 1 template only (gradman_v1) |
| Basic | Full | Can generate all 5 standard templates |
| Premium | Full | All templates + custom HTML templates |

### AI Features

#### Lesson Note Analysis
| Tier | Level | Details |
|------|-------|---------|
| Free | ❌ None | No AI analysis |
| Basic | ⚡ Basic | Auto-feedback on lesson structure |
| Premium | ⚡⚡ Full | Full AI scoring, curriculum alignment check, resource suggestions |

#### Grade Narratives
| Tier | Level | Details |
|------|-------|---------|
| Free | ❌ None | No narratives |
| Basic | ❌ None | Not available |
| Premium | ✅ Full | AI generates detailed narratives for each student |

#### Advanced Analytics
| Tier | Level | Details |
|------|-------|---------|
| Free | ❌ None | No analytics |
| Basic | ❌ None | Not available |
| Premium | ✅ Full | Dashboard with KPIs, trends, predictions |

---

## 🛒 Pricing

| Tier | Price | Billing |
|------|-------|---------|
| Free Tier | Free | - |
| Basic | ₵360 base + ₵12/student above 30 | Per Term |
| Premium | ₵750 base + ₵22/student above 30 | Per Term |

### Trial Access
- **Enterprise**: Ask for a custom evaluation arrangement where approved
- **Eligible schools**: One-time Premium trial runs for the remainder of the current term window, using the school's active term first and falling back to the EduPulse national basic-school calendar when needed

---

## ⚙️ Technical Limits

### Resource Quotas
| Resource | Free | Basic | Premium |
|----------|------|-------|---------|
| Classes | 1 | 5 | Unlimited |
| Students | 50 | 200 | Unlimited |
| Staff | 3 | 15 | Unlimited |
| Report Templates | 1 | 5 | 5 + Custom |

### API Rate Limits (all tiers)
- 200 requests per day
- 50 requests per hour
- Per-endpoint limits apply

---

## 🔐 Security & Support

### All Tiers Include:
- ✅ Multi-tenant data isolation
- ✅ End-to-end encryption for communications
- ✅ CSRF protection
- ✅ Role-based access control
- ✅ Audit logging
- ✅ Regular backups

### Support Levels
| Tier | Support | Response Time |
|------|---------|----------------|
| Free | Community Forum | Best effort |
| Basic | Email Support | 48 hours |
| Premium | Priority Support | 12 hours |

---

## 📋 FAQ

### Can I upgrade mid-month?
Yes! Upgrades take effect immediately, and prorated charges apply to your next billing cycle.

### What happens when I exceed quota?
- **Students**: Cannot add more than limit; must upgrade or archive old students
- **Classes**: Cannot create more classes; must upgrade
- **Reports**: Can only use templates available in current plan

### Can I downgrade?
Yes, downgrades take effect at the next billing cycle. Data is not deleted but access is restricted.

### Do you offer annual billing?
Not currently, but contact sales for enterprise agreements.

### Can schools get discounts?
Yes. Multi-year contracts and school networks can be reviewed directly with Daniel Asare Anyinam at danielasareanyinam2020@gmail.com.

### What if I need custom features?
Contact the support team for enterprise plan options.

---

## 🚀 Upgrade Path

**Free Tier → Basic Tier**:
- Add more classes (up to 5)
- Add up to 200 students
- Enable grade entry
- Get AI feedback on lesson notes
- Access full reporting

**Basic Tier → Premium Tier**:
- Unlimited classes and students
- Full AI suite (narratives, advanced analysis)
- Custom HTML templates
- Advanced analytics dashboard
- Financial reconciliation tools

---

## 📞 Support & Questions

For questions about features and plans:
- **Email**: danielasareanyinam2020@gmail.com
- **Phone**: +233 XXX XXX XXX
- **Documentation**: See the repository README and `docs/operations/`
- **Chat**: Available in app for Premium users

---

*Last Updated: February 21, 2026*
