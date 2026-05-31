# Monthly Usage Report Email Template

## 📊 EduPulse Monthly Usage Report - [Month Year]

---

### Email Subject Line Options

**Option 1 (Value-Focused):**  
`📊 [School Name]: You managed GH₵ [Amount] in fees this month on EduPulse`

**Option 2 (Predictability-Focused):**  
`💰 [School Name]: Your March billing summary & April forecast`

**Option 3 (Achievement-Focused):**  
`🎯 [School Name]: [X] students, [Y] transactions tracked this month`

---

## HTML Email Template

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EduPulse Monthly Usage Report</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8fafc;">
    
    <!-- Email Container -->
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; padding: 40px 20px;">
        <tr>
            <td align="center">
                <!-- Main Content Card -->
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); overflow: hidden;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0 0 8px 0; font-size: 28px; font-weight: 800;">
                                📊 Monthly Usage Report
                            </h1>
                            <p style="color: #e0e7ff; margin: 0; font-size: 16px;">
                                {{school_name}} · {{report_month}} {{report_year}}
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Greeting -->
                    <tr>
                        <td style="padding: 30px 30px 20px 30px;">
                            <p style="color: #1e293b; font-size: 16px; line-height: 1.6; margin: 0;">
                                Dear <strong>{{proprietor_name}}</strong>,
                            </p>
                            <p style="color: #475569; font-size: 15px; line-height: 1.6; margin: 16px 0 0 0;">
                                Here's your monthly summary of how EduPulse SMT is helping you manage 
                                <strong>{{school_name}}</strong> more effectively.
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Value Delivered Section -->
                    <tr>
                        <td style="padding: 0 30px 30px 30px;">
                            <table width="100%" cellpadding="0" cellspacing="0" style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border-radius: 12px; border: 2px solid #0ea5e9; padding: 24px;">
                                <tr>
                                    <td>
                                        <h2 style="color: #0369a1; margin: 0 0 16px 0; font-size: 18px; font-weight: 700;">
                                            🎯 Value Delivered This Month
                                        </h2>
                                        <table width="100%" cellpadding="8" cellspacing="0">
                                            <tr>
                                                <td style="color: #334155; font-size: 14px; padding: 8px 0;">
                                                    💰 Total Fees Tracked & Reconciled
                                                </td>
                                                <td align="right" style="color: #0f172a; font-size: 18px; font-weight: 800; padding: 8px 0;">
                                                    GH₵ {{total_fees_tracked}}
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="color: #334155; font-size: 14px; padding: 8px 0;">
                                                    📋 Payment Transactions Logged
                                                </td>
                                                <td align="right" style="color: #0f172a; font-size: 18px; font-weight: 800; padding: 8px 0;">
                                                    {{transaction_count}}
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="color: #334155; font-size: 14px; padding: 8px 0;">
                                                    📊 Report Cards Generated
                                                </td>
                                                <td align="right" style="color: #0f172a; font-size: 18px; font-weight: 800; padding: 8px 0;">
                                                    {{report_cards_generated}}
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="color: #334155; font-size: 14px; padding: 8px 0;">
                                                    👥 Active Students Managed
                                                </td>
                                                <td align="right" style="color: #0f172a; font-size: 18px; font-weight: 800; padding: 8px 0;">
                                                    {{active_student_count}}
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="color: #334155; font-size: 14px; padding: 8px 0;">
                                                    🍽️ Feeding Logs Recorded
                                                </td>
                                                <td align="right" style="color: #0f172a; font-size: 18px; font-weight: 800; padding: 8px 0;">
                                                    {{feeding_logs_count}}
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Student Meter Section -->
                    <tr>
                        <td style="padding: 0 30px 30px 30px;">
                            <h2 style="color: #1e293b; margin: 0 0 16px 0; font-size: 18px; font-weight: 700;">
                                📈 Your Student Meter
                            </h2>
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; border-radius: 8px; padding: 20px; border: 1px solid #e2e8f0;">
                                <tr>
                                    <td>
                                        <div style="margin-bottom: 12px;">
                                            <span style="color: #0f172a; font-size: 32px; font-weight: 900;">
                                                {{current_student_count}}
                                            </span>
                                            <span style="color: #94a3b8; font-size: 20px; font-weight: 600;">
                                                / {{included_students}}
                                            </span>
                                            <span style="color: #64748b; font-size: 14px; margin-left: 8px;">
                                                included students
                                            </span>
                                        </div>
                                        
                                        <!-- Progress Bar -->
                                        <div style="background-color: #e2e8f0; height: 12px; border-radius: 6px; overflow: hidden; margin-bottom: 8px;">
                                            <div style="background-color: {{progress_bar_color}}; height: 12px; width: {{usage_percent}}%; transition: width 0.3s;"></div>
                                        </div>
                                        
                                        <p style="margin: 0; color: #64748b; font-size: 13px;">
                                            {{usage_percent}}% capacity used · 
                                            <span style="color: {{alert_color}}; font-weight: 600;">
                                                {{alert_status}}
                                            </span>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Billing Preview Section -->
                    <tr>
                        <td style="padding: 0 30px 30px 30px;">
                            <table width="100%" cellpadding="0" cellspacing="0" style="background: linear-gradient(135deg, #fefce8 0%, #fef3c7 100%); border-radius: 12px; border: 2px solid #fbbf24; padding: 24px;">
                                <tr>
                                    <td>
                                        <h2 style="color: #92400e; margin: 0 0 16px 0; font-size: 18px; font-weight: 700;">
                                            💰 This Term's Billing Preview
                                        </h2>
                                        <table width="100%" cellpadding="6" cellspacing="0">
                                            <tr>
                                                <td style="color: #78350f; font-size: 14px; padding: 6px 0;">
                                                    Base Fee ({{subscription_plan}} Plan)
                                                </td>
                                                <td align="right" style="color: #451a03; font-size: 16px; font-weight: 700; padding: 6px 0;">
                                                    GH₵ {{base_fee}}
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="color: #78350f; font-size: 14px; padding: 6px 0;">
                                                    Included Students (Free)
                                                </td>
                                                <td align="right" style="color: #16a34a; font-size: 16px; font-weight: 700; padding: 6px 0;">
                                                    Included
                                                </td>
                                            </tr>
                                            {{#if has_overage}}
                                            <tr>
                                                <td style="color: #78350f; font-size: 14px; padding: 6px 0;">
                                                    Additional Students ({{overage_count}} × GH₵ {{overage_rate}})
                                                </td>
                                                <td align="right" style="color: #ea580c; font-size: 16px; font-weight: 700; padding: 6px 0;">
                                                    + GH₵ {{overage_cost}}
                                                </td>
                                            </tr>
                                            {{/if}}
                                            <tr style="border-top: 2px solid #fbbf24;">
                                                <td style="color: #78350f; font-size: 16px; font-weight: 800; padding: 12px 0 0 0;">
                                                    Total This Term
                                                </td>
                                                <td align="right" style="color: #0369a1; font-size: 24px; font-weight: 900; padding: 12px 0 0 0;">
                                                    GH₵ {{total_term_cost}}
                                                </td>
                                            </tr>
                                        </table>
                                        
                                        {{#if has_overage}}
                                        <p style="margin: 16px 0 0 0; color: #92400e; font-size: 13px; background-color: #fef3c7; padding: 12px; border-radius: 6px; border-left: 4px solid #f59e0b;">
                                            <strong>💡 Tip:</strong> You have {{overage_count}} student(s) beyond your included allowance. 
                                            Consider upgrading to the next plan to save on per-student costs.
                                        </p>
                                        {{/if}}
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Next Month Forecast (Predictability Pillar) -->
                    <tr>
                        <td style="padding: 0 30px 30px 30px;">
                            <h2 style="color: #1e293b; margin: 0 0 16px 0; font-size: 18px; font-weight: 700;">
                                🔮 Next Month Forecast
                            </h2>
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f1f5f9; border-radius: 8px; padding: 16px; border: 1px solid #cbd5e1;">
                                <tr>
                                    <td>
                                        <p style="margin: 0; color: #475569; font-size: 14px; line-height: 1.6;">
                                            📊 <strong>Projected Student Count:</strong> {{projected_students}} 
                                            ({{growth_trend}})
                                        </p>
                                        <p style="margin: 12px 0 0 0; color: #475569; font-size: 14px; line-height: 1.6;">
                                            💰 <strong>Estimated Cost:</strong> GH₵ {{projected_cost}}
                                        </p>
                                        {{#if approaching_capacity}}
                                        <p style="margin: 12px 0 0 0; color: #dc2626; font-size: 13px; background-color: #fee2e2; padding: 10px; border-radius: 6px; border-left: 4px solid #ef4444;">
                                            <strong>⚠️ Alert:</strong> You're projected to reach {{projected_percent}}% capacity next month. 
                                            Plan ahead to avoid service interruptions.
                                        </p>
                                        {{/if}}
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Trial Reminder (if applicable) -->
                    {{#if has_active_trial}}
                    <tr>
                        <td style="padding: 0 30px 30px 30px;">
                            <table width="100%" cellpadding="0" cellspacing="0" style="background: linear-gradient(135deg, #f3e8ff 0%, #e9d5ff 100%); border-radius: 12px; border: 2px solid #a855f7; padding: 20px;">
                                <tr>
                                    <td>
                                        <h3 style="color: #6b21a8; margin: 0 0 12px 0; font-size: 16px; font-weight: 700;">
                                            ⚡ Premium Trial Active
                                        </h3>
                                        <p style="margin: 0; color: #581c87; font-size: 14px; line-height: 1.5;">
                                            You have <strong>{{trial_days_remaining}} days</strong> remaining in your Premium trial. 
                                            Expires on <strong>{{trial_end_date}}</strong>.
                                        </p>
                                        {{#if trial_expiring_soon}}
                                        <p style="margin: 12px 0 0 0; color: #9f1239; font-size: 13px; background-color: #fce7f3; padding: 10px; border-radius: 6px;">
                                            ⏰ Your trial expires soon! Upgrade now to keep Premium features.
                                        </p>
                                        {{/if}}
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    {{/if}}
                    
                    <!-- Action Buttons -->
                    <tr>
                        <td style="padding: 0 30px 30px 30px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 10px;">
                                        <a href="{{dashboard_url}}" style="display: inline-block; background-color: #3b82f6; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 700; font-size: 15px;">
                                            📊 View Full Dashboard
                                        </a>
                                    </td>
                                </tr>
                                {{#if should_show_upgrade}}
                                <tr>
                                    <td align="center" style="padding: 10px;">
                                        <a href="{{upgrade_url}}" style="display: inline-block; background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%); color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 700; font-size: 15px;">
                                            🚀 Upgrade Your Plan
                                        </a>
                                    </td>
                                </tr>
                                {{/if}}
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px; background-color: #f8fafc; border-top: 1px solid #e2e8f0;">
                            <p style="margin: 0 0 12px 0; color: #64748b; font-size: 13px; text-align: center; line-height: 1.5;">
                                Questions about your billing? Reply to this email or visit our 
                                <a href="{{help_center_url}}" style="color: #3b82f6; text-decoration: none;">Help Center</a>.
                            </p>
                            <p style="margin: 0; color: #94a3b8; font-size: 12px; text-align: center;">
                                EduPulse SMT - Empowering Ghanaian Schools<br>
                                © 2026 EduPulse SMT. All rights reserved.
                            </p>
                            <p style="margin: 12px 0 0 0; color: #cbd5e1; font-size: 11px; text-align: center;">
                                <a href="{{unsubscribe_url}}" style="color: #cbd5e1; text-decoration: underline;">
                                    Unsubscribe from monthly reports
                                </a>
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
    
</body>
</html>
```

---

## Template Variables Reference

| Variable | Type | Example | Source |
|----------|------|---------|--------|
| `school_name` | String | "St. Mary's School" | School.name |
| `proprietor_name` | String | "Mrs. Adwoa Mensah" | User.full_name |
| `report_month` | String | "February" | datetime.now().strftime('%B') |
| `report_year` | String | "2026" | datetime.now().year |
| `total_fees_tracked` | Decimal | "124,350.00" | SUM(Payment.amount) WHERE status='Confirmed' |
| `transaction_count` | Integer | "487" | COUNT(Payment) WHERE month |
| `report_cards_generated` | Integer | "52" | COUNT(ReportCard) WHERE month |
| `active_student_count` | Integer | "87" | School.current_student_count |
| `feeding_logs_count` | Integer | "1,234" | COUNT(FeedingLog) WHERE month |
| `current_student_count` | Integer | "87" | School.current_student_count |
| `included_students` | Integer | "100" | PRICING[plan]['included_students'] |
| `usage_percent` | Float | "87.0" | (current / included) × 100 |
| `progress_bar_color` | String | "#10b981" | Green if < 80%, Amber if 80-99%, Red if ≥ 100% |
| `alert_color` | String | "#10b981" | Same logic as progress_bar_color |
| `alert_status` | String | "All systems normal" | Alert level text |
| `subscription_plan` | String | "Basic" | School.subscription_plan |
| `base_fee` | Decimal | "450.00" | PRICING[plan]['base_fee'] |
| `has_overage` | Boolean | true/false | current_student_count > included_students |
| `overage_count` | Integer | "0" | max(0, current - included) |
| `overage_rate` | Decimal | "12.00" | PRICING[plan]['overage_rate'] |
| `overage_cost` | Decimal | "0.00" | overage_count × overage_rate |
| `total_term_cost` | Decimal | "450.00" | base_fee + overage_cost |
| `projected_students` | Integer | "92" | growth_rate × current_count |
| `growth_trend` | String | "+5 from last month" | Calculated delta |
| `projected_cost` | Decimal | "488.00" | Forecasted billing |
| `approaching_capacity` | Boolean | true/false | projected_percent > 75% |
| `projected_percent` | Float | "92.0" | Forecast usage |
| `has_active_trial` | Boolean | true/false | School.is_trial_active |
| `trial_days_remaining` | Integer | "12" | (trial_end_date - now).days |
| `trial_end_date` | String | "March 17, 2026" | School.trial_end_date.strftime('%B %d, %Y') |
| `trial_expiring_soon` | Boolean | true/false | trial_days_remaining <= 3 |
| `dashboard_url` | String | "https://edupulse.com/dashboard" | Config |
| `should_show_upgrade` | Boolean | true/false | has_overage OR approaching_capacity |
| `upgrade_url` | String | "https://edupulse.com/subscription" | Config |
| `help_center_url` | String | "https://edupulse.com/help" | Config |
| `unsubscribe_url` | String | "https://edupulse.com/unsubscribe?token=..." | Generated token |

---

## Plain Text Version (for email clients without HTML support)

```text
==================================================================
   📊 EduPulse Monthly Usage Report - {{report_month}} {{report_year}}
==================================================================

Dear {{proprietor_name}},

Here's your monthly summary for {{school_name}}.

-------------------------------------------------------------------
🎯 VALUE DELIVERED THIS MONTH
-------------------------------------------------------------------

💰 Total Fees Tracked & Reconciled:    GH₵ {{total_fees_tracked}}
📋 Payment Transactions Logged:        {{transaction_count}}
📊 Report Cards Generated:             {{report_cards_generated}}
👥 Active Students Managed:            {{active_student_count}}
🍽️  Feeding Logs Recorded:             {{feeding_logs_count}}

-------------------------------------------------------------------
📈 YOUR STUDENT METER
-------------------------------------------------------------------

Current Students: {{current_student_count}} / {{included_students}} included
Capacity Used: {{usage_percent}}%
Status: {{alert_status}}

-------------------------------------------------------------------
💰 THIS TERM'S BILLING PREVIEW
-------------------------------------------------------------------

Base Fee ({{subscription_plan}} Plan):     GH₵ {{base_fee}}
Included Students:                         Included
{{#if has_overage}}
Additional Students ({{overage_count}}):   + GH₵ {{overage_cost}}
{{/if}}

TOTAL THIS TERM:                           GH₵ {{total_term_cost}}

{{#if has_overage}}
💡 Tip: You have {{overage_count}} student(s) beyond your included allowance.
Consider upgrading to save on per-student costs.
{{/if}}

-------------------------------------------------------------------
🔮 NEXT MONTH FORECAST
-------------------------------------------------------------------

Projected Student Count: {{projected_students}} ({{growth_trend}})
Estimated Cost: GH₵ {{projected_cost}}

{{#if approaching_capacity}}
⚠️  Alert: You're projected to reach {{projected_percent}}% capacity next month.
{{/if}}

{{#if has_active_trial}}
-------------------------------------------------------------------
⚡ PREMIUM TRIAL ACTIVE
-------------------------------------------------------------------

You have {{trial_days_remaining}} days remaining in your Premium trial.
Expires on {{trial_end_date}}.

{{#if trial_expiring_soon}}
⏰ Your trial expires soon! Upgrade now to keep Premium features.
{{/if}}
{{/if}}

-------------------------------------------------------------------

📊 View Full Dashboard: {{dashboard_url}}
{{#if should_show_upgrade}}
🚀 Upgrade Your Plan: {{upgrade_url}}
{{/if}}

Questions? Reply to this email or visit: {{help_center_url}}

EduPulse - Empowering Ghanaian Schools
© 2026 EduPulse. All rights reserved.

Unsubscribe: {{unsubscribe_url}}
==================================================================
```

---

## Sending Schedule Recommendation

**Frequency:** Monthly (1st of each month at 8:00 AM Ghana time)

**Target Audience:**
- Role: Proprietor (primary recipient)
- CC: Finance staff (optional)

**Triggers:**
1. **Scheduled Monthly Report** - Automatic on 1st of month
2. **Capacity Alert** - Immediate when 80% reached
3. **Trial Expiry Warning** - 7 days before, 3 days before, 1 day before

---

## Success Metrics to Track

1. **Email Open Rate** - Target: > 60%
2. **Dashboard Click-Through Rate** - Target: > 30%
3. **Upgrade Conversion Rate** - Target: > 10% of overage users
4. **Reply/Support Ticket Rate** - Target: < 5% (clarity indicator)

---

## Next Steps

1. Implement email service in backend (`backend/email_service.py`)
2. Add Celery/scheduler for monthly sends
3. Create unsubscribe management system
4. A/B test subject lines for optimal open rates
5. Add email analytics dashboard for admin panel
