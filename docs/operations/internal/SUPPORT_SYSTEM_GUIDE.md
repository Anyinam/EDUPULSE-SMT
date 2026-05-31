# 📧 SUPPORT TICKET SYSTEM - Complete Guide

## 🎯 Overview

**YOU NOW HAVE A FULLY FUNCTIONAL SUPPORT TICKET SYSTEM WITH EMAIL NOTIFICATIONS!**

### ✅ What Works NOW:
1. Tenants submit support tickets via "Help & Support" button
2. **YOU receive instant email notification** at: `danielasareanyinam2020@gmail.com`
3. **User receives confirmation email** that ticket was received
4. You respond via admin panel
5. **User receives email notification** when you reply

---

## 📩 How Email Notifications Work

### When Tenant Submits Ticket:

**1. EMAIL TO YOU (Admin):**
```
From: noreply@edupulse.local
To: danielasareanyinam2020@gmail.com
Subject: 🎫 New Support Ticket #123 - Bug Report

New support ticket submitted:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticket ID: #123
Status: Open
Type: Bug Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCHOOL DETAILS:
• School: ABC International School
• School ID: ABC-INT

USER DETAILS:
• Name: John Doe
• Email: john@abcschool.edu
• Role: Proprietor

ISSUE DESCRIPTION:
The payment gateway is not working when I try to upgrade...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Submitted: March 7, 2026 at 10:30 AM

To respond, log in to the admin panel or reply directly to this ticket.
```

**2. CONFIRMATION EMAIL TO USER:**
```
From: noreply@edupulse.local
To: john@abcschool.edu
Subject: ✅ Support Ticket #123 Received - EduPulse

Hello John Doe,

Thank you for contacting EduPulse support! Your ticket has been received 
and our team will review it shortly.

What happens next?
• Our support team will review your ticket within 24-48 hours
• You'll receive an email notification when we respond
• Track your ticket status in Help & Support > My Tickets
```

**3. WHEN YOU REPLY - EMAIL TO USER:**
```
From: noreply@edupulse.local
To: john@abcschool.edu
Subject: 💬 Response to Your Support Ticket #123 - EduPulse

Hello John Doe,

Great news! Our support team has responded to your ticket.

YOUR ORIGINAL MESSAGE:
The payment gateway is not working when I try to upgrade...

OUR RESPONSE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Thank you for reporting this! I've checked your account and the issue 
was due to... [your response here]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🖥️ How to View & Respond to Tickets

### Access Admin Panel:
```
URL: http://localhost:3000/admin/support
OR in production: https://your-aws-domain.com/admin/support
```

### Steps to Respond:
1. Navigate to `/admin/support` in your dashboard
2. You'll see all tickets with filters (All / Open / Resolved)
3. Click on any ticket to view full details
4. Type your response in the text area
5. Click "📧 Send Reply & Notify User"
6. User receives email automatically!

### Dashboard Features:
- **Real-time ticket list** with school ID and status
- **Filter by status** (All, Open, Resolved)
- **Click to select** any ticket for detailed view
- **Rich ticket info** including school details, user info, description
- **Send responses** that automatically email the user
- **Refresh button** to check for new tickets

---

## 🚀 AWS DEPLOYMENT PROCESS

### QUESTION: If I want to add more features, do I need to write code in VS Code and redeploy in AWS?

**YES! Here's the complete workflow:**

### Development → Production Pipeline:

#### 1️⃣ **DEVELOP LOCALLY (VS Code)**
```bash
# Make your code changes in VS Code
cd /home/anyinam/Documents/EduPulse

# Test locally with Docker
docker compose up --build

# Test at http://localhost:3000
# Make sure everything works!
```

#### 2️⃣ **PUSH TO GITHUB** (Optional but recommended)
```bash
git add .
git commit -m "Added new feature: XYZ"
git push origin main
```

#### 3️⃣ **DEPLOY TO AWS**

**Option A: Using AWS ECR + ECS (Recommended for Production)**

```bash
# 1. Build Docker images
docker build -t edupulse-backend ./backend
docker build -t edupulse-frontend ./frontend

# 2. Login to AWS ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin YOUR_ECR_URL

# 3. Tag images
docker tag edupulse-backend:latest YOUR_ECR_URL/edupulse-backend:latest
docker tag edupulse-frontend:latest YOUR_ECR_URL/edupulse-frontend:latest

# 4. Push to ECR
docker push YOUR_ECR_URL/edupulse-backend:latest
docker push YOUR_ECR_URL/edupulse-frontend:latest

# 5. Update ECS services (this triggers deployment)
aws ecs update-service \
  --cluster edupulse-cluster \
  --service backend-service \
  --force-new-deployment

aws ecs update-service \
  --cluster edupulse-cluster \
  --service frontend-service \
  --force-new-deployment
```

**Option B: Direct SSH to EC2 (Simpler for small updates)**

```bash
# 1. SSH into your AWS EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# 2. Pull latest code
cd /path/to/edupulse
git pull origin main

# 3. Rebuild and restart
docker compose down
docker compose up --build -d

# 4. Verify it's running
docker compose ps
docker compose logs backend --tail=50
```

---

## 🔧 CONFIGURATION FILES TO UPDATE FOR AWS

### 1. Environment Variables (.env)
**⚠️ IMPORTANT:** Update these for production:

```env
# In AWS, create /path/to/edupulse/.env with:

# YOUR EMAIL (where support tickets go)
FOUNDER_EMAIL=danielasareanyinam2020@gmail.com

# Database (use AWS RDS credentials)
DATABASE_URL=postgresql://username:password@rds-endpoint:5432/edupulse_db

# Email (use production SMTP or AWS SES)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=danielasareanyinam2020@gmail.com
MAIL_PASSWORD=your_app_password_here

# Production domain
FRONTEND_URL=https://edupulse.com
APP_URL=https://edupulse.com

# Security (generate new keys!)
SECRET_KEY=<generate-new-random-key>
JWT_SECRET_KEY=<generate-new-random-key>

# Disable debug mode
DEBUG=False
```

### 2. Docker Compose (docker-compose.yml)
No changes needed! Just ensure ports are correct:
- Backend: 5000
- Frontend: 3000 (or 80 with nginx)
- Database: 5432 (internal only)

---

## 📊 MONITORING SUPPORT TICKETS IN AWS

### Real-Time Monitoring:

**1. Check Backend Logs:**
```bash
ssh -i key.pem ubuntu@your-ec2-ip
cd /path/to/edupulse
docker compose logs backend --tail=100 -f
```

**2. Check Database Directly:**
```bash
docker compose exec db psql -U postgres -d edupulse_db

# Query tickets
SELECT id, type, status, description, created_at 
FROM support_tickets 
ORDER BY created_at DESC 
LIMIT 10;
```

**3. AWS CloudWatch (if configured):**
- View container logs in CloudWatch Logs
- Set up alerts for "Support Ticket" keywords
- Create dashboard for ticket metrics

---

## 🆘 TROUBLESHOOTING

### Email Not Sending?

**1. Check Backend Logs:**
```bash
docker compose logs backend | grep -i "email\|mail"
```

**2. Verify Gmail App Password:**
- Visit: https://myaccount.google.com/apppasswords
- Generate new password if expired
- Update `.env` file with new password

**3. Test Email Manually:**
```bash
# Enter backend container
docker compose exec backend bash

# Test Python email
python3
>>> from backend.utils import send_email_notification
>>> send_email_notification(
...     "your-email@gmail.com", 
...     "Test", 
...     "If you receive this, email works!"
... )
```

### Tickets Not Appearing in Admin Panel?

**1. Check JWT Token:**
```javascript
// In browser console (F12)
console.log(localStorage.getItem('token'));
// Should show a long JWT token
```

**2. Check API Endpoint:**
```bash
# Test endpoint directly
curl -X GET http://localhost:5000/api/admin/tickets \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "X-School-ID: YOUR_SCHOOL_ID"
```

**3. Verify Database:**
```sql
-- Check if tickets exist
SELECT COUNT(*) FROM support_tickets;
```

---

## 🆚 SUPPORT TICKETS vs LIVE CHAT

### You Asked: "Do they do the same thing? Should I use only one?"

**RECOMMENDATION: Use SUPPORT TICKETS ONLY** ✅

| Feature | Support Tickets ✅ | Live Chat ❌ |
|---------|-------------------|--------------|
| **Requires 24/7 monitoring** | ❌ No | ✅ Yes |
| **Can respond anytime** | ✅ Yes | ❌ No |
| **Email notifications** | ✅ Yes | 🟡 Complex |
| **Good for solo admin** | ✅ Perfect | ❌ Bad |
| **User expectations** | "Reply in 24-48h" | "Reply NOW" |
| **Best for** | Bug reports, feature requests | Sales teams, urgent support |

### Why Support Tickets are Better for You:

1. **No Pressure:** Respond when you have time
2. **Better Context:** Full ticket history with details
3. **Email Trail:** Automatic documentation
4. **Scalable:** Add team members later
5. **Works Offline:** Users submit anytime

### When to Enable Live Chat:

Only if you have:
- ✅ Dedicated support team (3+ people)
- ✅ 8+ hours daily availability
- ✅ WebSocket infrastructure
- ✅ Real-time monitoring tools

**For now: Keep `ENABLE_LIVE_CHAT=false` in .env**

---

## 📝 QUICK REFERENCE

### Important URLs:
- **Tenant Support Button:** Floating button on all pages
- **Admin Panel:** `/admin/support`
- **Help Center:** `/help`

### Important Files:
- **Support Ticket API:** `backend/routes.py` (lines 9723-9800)
- **Admin Response API:** `backend/routes.py` (lines 9923-9950)
- **Email Template:** Inline in routes.py
- **Frontend Component:** `frontend/react/src/components/Support.jsx`
- **Admin Dashboard:** `frontend/react/src/features/AdminSupport.jsx`

### Environment Variables:
```env
FOUNDER_EMAIL=danielasareanyinam2020@gmail.com  # Your email
MAIL_USERNAME=danielasareanyinam2020@gmail.com
MAIL_PASSWORD=<your-gmail-app-password>
ENABLE_LIVE_CHAT=false  # Keep disabled
```

---

## ✅ DEPLOYMENT CHECKLIST

Before deploying to AWS:

- [ ] Update `FOUNDER_EMAIL` in `.env`
- [ ] Generate new `SECRET_KEY` and `JWT_SECRET_KEY`
- [ ] Set `DEBUG=False`
- [ ] Update `DATABASE_URL` to AWS RDS
- [ ] Update `FRONTEND_URL` to production domain
- [ ] Verify Gmail app password works
- [ ] Test locally: `docker compose up --build`
- [ ] Push to GitHub (optional)
- [ ] Deploy to AWS via ECR/ECS or SSH
- [ ] Test support ticket submission in production
- [ ] Verify you receive email notifications
- [ ] Test admin response feature
- [ ] Verify users receive reply emails

---

## 🎉 SUMMARY

**What You Have Now:**
1. ✅ Full support ticket system with email notifications
2. ✅ Admin can receive ticket emails instantly
3. ✅ Users receive confirmation emails
4. ✅ Admin panel to view and respond to tickets
5. ✅ Users receive email when you reply
6. ✅ Support tickets (NOT live chat) - perfect for solo admin

**To Deploy New Features:**
1. Write code in VS Code
2. Test locally: `docker compose up --build`
3. Push to AWS via ECR or SSH
4. Restart containers in production

**To View Tickets:**
- Navigate to `/admin/support` in your dashboard
- OR check email at `danielasareanyinam2020@gmail.com`

---

**Need Help?** All support ticket code is in:
- Backend: `/backend/routes.py` (search for "support/ticket")
- Frontend: `/frontend/react/src/components/Support.jsx`
- Admin UI: `/frontend/react/src/features/AdminSupport.jsx`
