# Frontend Billing Widgets - Implementation Guide

## Overview

This document describes the new frontend components for the Metronome-inspired billing system implemented in EduPulse. These widgets provide real-time visibility into student metering, billing alerts, trial management, and cost breakdowns.

---

## 📦 New Components

### 1. **BillingVisibility.jsx** (Full Dashboard Widget)

**Location:** `/frontend/react/src/components/BillingVisibility.jsx`

**Purpose:** Comprehensive billing dashboard showing active student meter, usage alerts, trial status, and cost breakdown.

**Features:**
- **Active Student Meter**
  - Real-time count of enrolled students
  - Progress bar showing usage percentage
  - Manual "Sync Now" button
  - Last synced timestamp

- **Smart Alerts (80% / 100% Thresholds)**
  - ✅ **OK Level** (< 80%): Green badge, "All systems normal"
  - ⚠️ **Warning Level** (80-99%): Amber badge, "Approaching capacity limit"
  - 🚨 **Critical Level** (≥ 100%): Red badge, "Over capacity - overage charges apply"

- **Premium Trial Banner**
  - Displays when trial is active
  - Shows days remaining with countdown
  - Expiry warning when ≤ 3 days remain
  - Gradient purple/indigo styling

- **Cost Breakdown Card**
  - Base fee (plan-specific)
  - Included students (no extra charge)
  - Overage students with per-unit rate
  - **Total Term Cost** (prominent display)
  - Grandfathered pricing indicator (if locked)

**API Endpoint:** `GET /api/school/subscription/billing-visibility`

**Integration Points:**
- `SubscriptionManager.jsx` - Full visibility section after status cards
- `ProprietorPanel.jsx` - Dashboard overview widget

**Usage Example:**
```jsx
import BillingVisibility from '../components/BillingVisibility';

<div className="mb-8">
  <BillingVisibility />
</div>
```

---

### 2. **TrialManager.jsx** (Trial Activation/Management)

**Location:** `/frontend/react/src/components/TrialManager.jsx`

**Purpose:** Self-service Premium trial activation and management interface.

**Features:**
- **Trial Available State**
  - Promotional banner with Premium benefits
  - Trial duration selector (7, 14, or 30 days)
  - One-click activation button
  - No credit card required messaging

- **Active Trial State**
  - Start date, end date, days remaining
  - Premium features checklist
  - Expiry warning (≤ 3 days)
  - "End Trial Early" option

- **Trial Used State**
  - Historical info (trial ended date)
  - Upgrade prompt for paid plan

**API Endpoints:**
- `GET /api/school/subscription/trial/status`
- `POST /api/school/subscription/trial/activate` (body: `{days: 30}`)
- `POST /api/school/subscription/trial/end`

**Integration Points:**
- `SubscriptionManager.jsx` - Placed after BillingVisibility widget

**Security:**
- Automatic localStorage update for `subscription_plan`
- Full page reload after activation/deactivation to refresh feature access

**Usage Example:**
```jsx
import TrialManager from '../components/TrialManager';

<div className="mb-8">
  <TrialManager />
</div>
```

---

### 3. **BillingSummaryCard.jsx** (Compact Dashboard Card)

**Location:** `/frontend/react/src/components/BillingSummaryCard.jsx`

**Purpose:** Lightweight billing snapshot for dashboard overview pages.

**Features:**
- Compact card format (fits dashboard grids)
- Student meter with mini progress bar
- Alert level badge (OK/Warning/Critical)
- Term cost summary
- Overage count (if applicable)

**API Endpoint:** `GET /api/school/subscription/billing-visibility` (same as full widget)

**Use Cases:**
- Dashboard quick view
- Multi-panel layouts
- Mobile-responsive summaries

**Usage Example:**
```jsx
import BillingSummaryCard from '../components/BillingSummaryCard';

<div className="grid grid-cols-3 gap-6">
  <BillingSummaryCard />
  {/* Other cards */}
</div>
```

---

## 🎯 User Flows

### **Flow 1: Proprietor Views Billing Status**

1. Navigate to **Subscription & Billing** page
2. See full `BillingVisibility` widget at top
3. **Student Meter** shows: "87 / 100 included students" (87% capacity)
4. **Alert Banner**: ⚠️ "Warning: Approaching capacity limit at 87%"
5. **Cost Breakdown**: Base ₵450 + Overage ₵0 = **Total ₵450**
6. Click **"Sync Now"** to manually refresh student count

### **Flow 2: Activate Premium Trial**

1. Navigate to **Subscription & Billing**
2. See `TrialManager` widget with "🎁 Activate Your Free Premium Trial!"
3. Select trial duration (default: 30 days)
4. Click **"Activate 30-Day Premium Trial"**
5. Confirm dialog appears with Premium feature list
6. On approval:
   - POST to `/api/school/subscription/trial/activate`
   - localStorage updated to `subscription_plan: 'Premium'`
   - Page reloads to apply Premium features
7. Trial banner appears showing countdown: "27 days remaining"

### **Flow 3: Threshold Alert Triggers**

**Scenario:** School adds 21st student (80% of 25 included in Basic plan)

1. Student is added via `StudentsRegistry`
2. Backend `sync_student_meter()` auto-triggers (event listener on Student model)
3. Meter updates: `current_count: 21, usage_percent: 84%`
4. BillingVisibility widget auto-refreshes on next page load
5. Alert banner changes from **Green ✅** to **Amber ⚠️**:
   - Title: "Approaching Capacity Limit"
   - Message: "You're at 84% capacity. Consider upgrading or adding more students."

**Scenario:** School reaches 26th student (104% overage)

1. 26th student enrolled
2. Meter: `current_count: 26, usage_percent: 104%`
3. Alert banner: **Red 🚨 Critical**
   - Title: "Over Capacity"
   - Message: "You have 1 overage student. Additional charges: GH₵12/student."
4. Cost breakdown updates:
   - **Overage Students**: 1 × GH₵12 = +GH₵12
   - **Total This Term**: GH₵212 (was ₵200)

---

## 🎨 Component Styling

All components use the EduPulse design system:

- **Primary Colors**: Blue-600 (actions), slate-800 (text)
- **Alert Colors**: 
  - Green (OK): `bg-green-50`, `border-green-200`, `text-green-800`
  - Amber (Warning): `bg-amber-50`, `border-amber-300`, `text-amber-900`
  - Red (Critical): `bg-red-50`, `border-red-300`, `text-red-900`
- **Trial Branding**: Purple-600 to Indigo-600 gradients
- **Spacing**: `p-6`, `rounded-2xl`, `shadow-sm` (consistent with platform)

### Responsive Design

- All widgets are mobile-responsive
- Progress bars scale fluidly
- Cost breakdowns stack on small screens
- Trial manager maintains readability on phones

---

## 🔌 Backend Integration

### API Response Structure

**GET /api/school/subscription/billing-visibility**

```json
{
  "plan": "Basic",
  "status": "Active",
  "meter": {
    "current_count": 87,
    "included_students": 100,
    "usage_percent": 87.0,
    "last_synced": "2026-03-07T14:23:10",
    "alert": {
      "level": "warning",
      "title": "Approaching Capacity Limit",
      "message": "You're at 87% capacity. Consider upgrading soon."
    }
  },
  "trial": {
    "is_active": true,
    "start_date": "2026-02-15",
    "end_date": "2026-03-17",
    "plan": "Premium"
  },
  "cost_breakdown": {
    "base_fee": 450.0,
    "overage_students": 0,
    "overage_cost": 0.0,
    "total_due": 450.0
  },
  "pricing": {
    "base_fee": 450.0,
    "included_students": 100,
    "overage_rate": 12.0,
    "version": "2026-Q1"
  }
}
```

**POST /api/school/subscription/trial/activate**

Request:
```json
{
  "days": 30
}
```

Response:
```json
{
  "message": "Premium trial activated",
  "end_date": "2026-04-06",
  "plan": "Premium"
}
```

---

## 🧪 Testing Checklist

- [ ] BillingVisibility renders without errors
- [ ] Student meter shows correct count from backend
- [ ] Alert level changes at 80% and 100% thresholds
- [ ] Trial banner only shows when `trial.is_active === true`
- [ ] Trial countdown updates daily
- [ ] Cost breakdown matches backend calculations
- [ ] Sync button triggers meter refresh
- [ ] TrialManager shows correct state (available/active/used)
- [ ] Trial activation updates localStorage and reloads page
- [ ] Grandfathered pricing indicator appears when `pricing.version` exists

---

## 📊 Metrics & Monitoring

### Frontend Performance
- **Load Time**: BillingVisibility < 300ms (API call + render)
- **User Actions**: Track trial activations, manual syncs

### User Engagement
- **Trial Activation Rate**: % of schools that activate when offered
- **Alert Response**: Time from 80% alert to upgrade action
- **Sync Frequency**: How often proprietors manually sync meter

---

## 🚀 Future Enhancements

1. **Email Alerts**
   - Send email when 80% capacity reached
   - 3-day trial expiry warning
   - Monthly billing summary

2. **Predictive Insights**
   - "Based on enrollment trends, you'll reach capacity in 14 days"
   - Recommended upgrade timing

3. **Billing History**
   - Past term costs chart
   - Student count over time graph
   - Overage trend analysis

4. **Mobile App**
   - Push notifications for billing alerts
   - Quick view billing card in mobile dashboard

---

## 🔗 Related Documentation

- [Backend Implementation: subscription_metering.py](../backend/subscription_metering.py)
- [API Endpoints: routes.py](../backend/routes.py) (lines for subscription routes)
- [Database Schema: models.py](../backend/api/models.py) (School model columns)
- [Alembic Migration: 9a1c2d3e4f55](../alembic/versions/9a1c2d3e4f55_add_school_meter_and_pricing_version_fields.py)

---

## 📞 Support

For questions or issues with billing widgets:
- **Technical Issues**: Check browser console for API errors
- **Incorrect Meter Counts**: Use "Sync Now" button, check backend logs
- **Trial Activation Fails**: Verify school hasn't already used trial

---

**Last Updated:** March 7, 2026  
**Version:** 1.0.0  
**Author:** EduPulse Development Team
