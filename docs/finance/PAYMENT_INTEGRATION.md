# 💰 EduPulse SMT Payment Integration Guide

## Overview

Your revenue model is **SaaS subscription-based**. Schools (tenants) subscribe to different tiers (Free/Basic/Premium) and you receive automatic payments via **Paystack** (Ghana's leading payment gateway).

Important scope note:
- This document covers EduPulse's own school subscription billing.
- Parent and guardian fee collection is a separate operational payment layer documented in `docs/finance/PAYMENT_CATEGORIZATION.md`, `docs/finance/PAYMENT_REFERENCE_FORMAT.md`, `docs/finance/BANK_TRANSFER_INTEGRATION.md`, and `docs/strategy/B2B2C_AI_EMPLOYEE_ROADMAP.md`.

Current parent-fee scope note:
- EduPulse uses structured references for fee categorization.
- Reliable automatic transfer tracking is handled through on-demand Paystack dedicated virtual accounts created per learner fee reference.
- Those tracked transfer accounts split settlement so the school receives the base fee amount through its Paystack subaccount while EduPulse retains the convenience-fee remainder in the main Paystack settlement account.

### Current Onboarding Payment Behavior
- Free plan: registration completes immediately and user proceeds to login.
- Basic/Premium: registration initializes payment immediately and redirects to checkout.
- After successful payment verification, subscription is activated and user is redirected to login.
- Welcome email is sent once per registration flow (duplicate sends prevented by audit checks).

---

## 💳 Revenue Flow Diagram

```
School (Tenant)
    ↓
    Website: Upgrades to Basic/Premium Plan
    ↓
    Redirected to Paystack Payment Page
    ↓
    School enters card/mobile money details
    ↓
    Paystack processes → Sends to your Zenith/GCB account
    ↓
    Money lands in YOUR business account (daily)
    ↓
    Webhook notifies EduPulse backend
    ↓
    School's subscription activated automatically
```

---

## 🎯 Setup: 5 Steps

### Step 1: Get Paystack Business Account

**Sign up:** https://paystack.com/gh

1. Create business account
2. Provide:
  - School name: "EduPulse SMT"
   - Phone: Your business number
  - Email: danielasareanyinam2020@gmail.com
   - Bank account (Zenith/GCB)
3. Get verified (24-48 hours)
4. Receive API keys:
   - **Public Key** (frontend): pk_live_xxxxxxxx
   - **Secret Key** (backend): sk_live_xxxxxxxx

### Step 2: Update Environment Variables

Create/update `.env` in backend:

```bash
# Paystack Integration
PAYSTACK_SECRET_KEY=sk_live_your_secret_key_here
PAYSTACK_PUBLIC_KEY=pk_live_your_public_key_here
FRONTEND_URL=https://edupulse.com.gh  # For Paystack callback
```

### Step 3: Database Migration

The `Subscription` model is now in `backend/api/models.py`. Create migration:

```bash
cd /home/anyinam/Documents/EduPulse

# Using Alembic
flask db migrate -m "Add subscription tracking for SaaS billing"
flask db upgrade

# OR direct SQLite (if Alembic fails)
python backend/apply_migration.py
```

**Tables created:**
- `subscriptions` - School subscription status and dates
- `payments` - Payment transaction records

### Step 4: Register Payment Routes

Payment endpoints are implemented directly in `backend/routes.py` and use helpers from `backend/paystack_integration.py`.

```python
# Live payment endpoints:
# POST   /api/paystack/initialize-payment  - Start subscription payment
# GET    /api/paystack/verify/<reference>  - Verify after payment
# POST   /api/paystack/webhook             - Paystack notifications
# GET    /api/subscription/status          - Check subscription status
```

### Step 5: Frontend Integration

Update `backend/routes.py` `/api/school/subscription` endpoint to include Paystack URLs:

```python
@app.route('/api/school/subscription/<school_id>', methods=['GET'])
def get_subscription_info(school_id):
    return {
        'current_plan': 'free',
        'paystack_public_key': os.getenv('PAYSTACK_PUBLIC_KEY'),
        'upgrade_url': f'/api/payments/initialize'
    }
```

---

## 📱 Frontend: Payment UI

Add to `frontend/react/src/features/ProprietorPanel.jsx`:

```jsx
import axios from 'axios';

function SubscriptionUpgrade() {
  const [loading, setLoading] = useState(false);
  
  const handleUpgrade = async (plan) => {
    setLoading(true);
    try {
      // Initialize payment
      const response = await axios.post('/api/payments/initialize', {
        school_id: localStorage.getItem('school_id'),
        plan: plan,  // 'basic' or 'premium'
        billing_cycle: 1
      });

      if (response.data.authorization_url) {
        // Redirect to Paystack
        window.location.href = response.data.authorization_url;
      }
    } catch (error) {
      alert('Payment failed: ' + error.response.data.error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-3 gap-6 p-8">
      {/* FREE TIER */}
      <div className="bg-gray-50 p-6 rounded-lg border-2 border-gray-200">
        <h3 className="text-2xl font-bold">FREE</h3>
        <p className="text-3xl font-bold my-4 text-gray-600">₵0</p>
        <ul className="text-sm text-gray-600 space-y-2 mb-4">
          <li>✓ 1 Class</li>
          <li>✓ 50 Students</li>
          <li>✓ View-only Access</li>
          <li>✗ No AI Features</li>
        </ul>
        <button disabled className="w-full py-2 bg-gray-300 text-white rounded cursor-not-allowed">
          Current Plan
        </button>
      </div>

      {/* BASIC TIER */}
      <div className="bg-blue-50 p-6 rounded-lg border-2 border-blue-500">
        <h3 className="text-2xl font-bold">BASIC</h3>
        <p className="text-3xl font-bold my-4 text-blue-600">
          ₵360<span className="text-sm">/term base</span>
        </p>
        <ul className="text-sm text-gray-700 space-y-2 mb-4">
          <li>✓ 5 Classes</li>
          <li>✓ 200 Students</li>
          <li>✓ Full Access</li>
          <li>✓ Basic AI</li>
        </ul>
        <button 
          onClick={() => handleUpgrade('basic')}
          disabled={loading}
          className="w-full py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          {loading ? 'Processing...' : 'Upgrade to Basic'}
        </button>
      </div>

      {/* PREMIUM TIER */}
      <div className="bg-purple-50 p-6 rounded-lg border-2 border-purple-500">
        <h3 className="text-2xl font-bold">PREMIUM</h3>
        <p className="text-3xl font-bold my-4 text-purple-600">
          ₵750<span className="text-sm">/term base</span>
        </p>
        <ul className="text-sm text-gray-700 space-y-2 mb-4">
          <li>✓ Unlimited Classes</li>
          <li>✓ Unlimited Students</li>
          <li>✓ Full Features</li>
          <li>✓ Advanced AI</li>
        </ul>
        <button 
          onClick={() => handleUpgrade('premium')}
          disabled={loading}
          className="w-full py-2 bg-purple-600 text-white rounded hover:bg-purple-700"
        >
          {loading ? 'Processing...' : 'Upgrade to Premium'}
        </button>
      </div>
    </div>
  );
}

export default SubscriptionUpgrade;
```

---

## ✅ Payment Verification Flow

Note:
- Finance actions may be gated by school verification state.
- Schools are expected to complete KYB verification onboarding before unrestricted financial processing.

### 1. School Clicks "Upgrade to Basic"
```
Frontend: ↓
POST /api/payments/initialize
{
  school_id: "sch_123",
  plan: "basic",
  billing_cycle: 1
}
```

### 2. EduPulse Backend Creates Paystack Transaction
```
Response: {
  "authorization_url": "https://checkout.paystack.com/xyz123",
  "reference": "ref_abc123",
  "amount_ghs": 360
}
```

### 3. School Redirected to Paystack
- Enters card/mobile money details
- Paystack processes payment
- School sees "Payment Successful"

### 4. Paystack Notifies Backend via Webhook
```
POST /api/payments/webhook
Headers: X-Paystack-Signature: <verified_signature>
Body: {
  "event": "charge.success",
  "data": {
    "reference": "ref_abc123",
    "amount": 36000,  // in pesewas (×100)
    "status": "success",
    "metadata": {"school_id": "sch_123", "plan": "basic"}
  }
}
```

### 5. Backend Updates Subscription
```python
# Auto-updates in database:
- School.subscription_plan = "basic"
- Subscription.plan = "basic"
- Subscription end and billing dates align to the selected term billing cycle
- Subscription.status = "active"
- Payment record created
```

### 6. School Immediately Gets Access
- Lesson notes enabled ✓
- Grade entry enabled ✓
- Basic AI feedback enabled ✓
- 5 classes allowed ✓
- 200 students allowed ✓

### 7. Verification Gate Check (Where Enabled)
- If the school is not verified, selected finance actions can return verification-required responses.
- Proprietor submits school verification profile via compliance endpoints.
- External KYB provider can auto-verify clean schools; flagged outcomes route to manual review.

---

## 💰 How You Get Paid

### Payment Flow to Your Account:

```
1. School pays ₵360 on Paystack
   ↓
2. Paystack takes ~1.5% fee (₵5.40)
   ↓
3. You receive ₵354.60 in your account
   ↓
4. Settlement timing:
   - Test account: Manual withdrawal
   - Live account: Daily automatic transfer
   ↓
5. Funds land in your Zenith/GCB account
```

### Pricing Breakdown:

| Metric | Amount |
|--------|--------|
| Basic Plan Per Term | ₵360.00 |
| Paystack Fee (1.5%) | -₵5.40 |
| **You Receive** | **₵354.60/term** |
| | |
| Premium Plan Per Term | ₵750.00 |
| Paystack Fee (1.5%) | -₵11.25 |
| **You Receive** | **₵738.75/term** |

### Revenue Scenarios:

**Scenario 1: 10 schools on Basic**
- 10 × ₵354.60 = **₵3,546.00/term** = **₵10,638/year**

**Scenario 2: Mix of 20 Basic + 5 Premium**
- (20 × ₵354.60) + (5 × ₵738.75) = **₵10,785.75/term** = **₵32,357.25/year**

**Scenario 3: Scale to 100 schools (mix)**
- Avg ₵540/school = **₵54,000+/term** = **₵162,000+/year**

---

## 🔧 Paystack Dashboard Features

Login to https://dashboard.paystack.com:

### Key Screens:

1. **Transactions** - See all payments
   - Filter by status (successful, failed, pending)
   - Sort by date/amount
   - Download export

2. **Revenue** - Monthly/annual earnings
   - Total processed
   - Total fees
   - Net received

3. **Customers** - Track schools
   - Repeat customers
   - Subscription history

4. **API Keys** - Your integration keys
   - Test/Live switching
   - Key regeneration

---

## 📊 Financial Reporting

### Monthly Report (Automated)

The backend can generate:

```python
# GET /api/payments/dashboard/<school_id>
{
  "total_invested": "₵250.00",
  "current_plan": "premium",
  "subscription_active": true,
  "failed_payments": 0,
  "payment_count": 3,
  "monthly_trend": {
    "month": "February 2026",
    "revenue": "₵200.00"
  }
}
```

### Business Intelligence Queries:

```
SELECT 
  COUNT(*) as total_schools,
  COUNT(CASE WHEN plan='premium' THEN 1 END) as premium_schools,
  COUNT(CASE WHEN plan='basic' THEN 1 END) as basic_schools,
  SUM(CASE WHEN status='success' THEN amount ELSE 0 END) as total_revenue
FROM subscriptions s
JOIN payments p ON s.school_id = p.school_id
WHERE p.status = 'success'
AND p.transaction_date >= DATE_TRUNC('month', NOW())
```

---

## ⚠️ Important Security Notes

### 1. Never Expose Keys
❌ DON'T commit keys to Git
✓ Use `.env` files (add to .gitignore)
✓ Use environment variables in production

### 2. Webhook Verification
✓ Always verify `X-Paystack-Signature` header
✓ Prevents fraudulent webhook calls
✓ Implementation included in `backend/payments.py`

### 3. Subscription Enforcement
✓ Backend middleware checks `subscription_features.py`
✓ Free tier can't access Basic/Premium features
✓ Subscription expiry blocks feature access

---

## 🚀 Deployment Checklist

- [ ] Paystack account created and verified
- [ ] API keys added to production `.env`
- [ ] Database migrations applied
- [ ] Payment routes registered in Flask
- [ ] Frontend upgrade buttons styled and working
- [ ] Webhook endpoint accessible from Paystack
- [ ] SSL certificate active (https://)
- [ ] Test payment completed successfully
- [ ] Confirmation emails sending to schools
- [ ] Payment dashboard displaying correctly
- [ ] Automatic subscription enforcement working
- [ ] Failed payment handling implemented
- [ ] Monthly revenue reports configured

---

## 📞 Support

**Paystack Support:** support@paystack.com  
**Ghana Hotline:** +233 (0) XXX XXX XXXX  
**Documentation:** https://paystack.com/docs

---

**Last Updated:** February 21, 2026  
**Status:** Ready for Implementation
