# Platform Owner Console Guide

## Overview

The Platform Owner Console is a professional admin interface that allows you (the software owner) and your assistant admins to manage global platform settings and content. This is separate from the tenant (school) system and does not require school credentials.

## Features

1. **Help Content Management**: Edit the FAQ and tutorial videos that appear on the login page for all schools
2. **User Management**: Add and manage assistant admin users who can access the console
3. **Secure Authentication**: Owner-key protected operations with JWT-based authentication

## Getting Started

### 1. Set Platform Owner Key (Production)

Before deploying to production, set a secure owner key in your environment:

```bash
# Generate a secure random key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Example output: Xk7Jp2_QmNvR3sL9pW4tYzA8hBcD5eF6gH1iJ0kM
# ⚠️ SAVE THIS OUTPUT IMMEDIATELY! You cannot regenerate the same key.

# Set it in your .env file or environment
PLATFORM_OWNER_KEY=Xk7Jp2_QmNvR3sL9pW4tYzA8hBcD5eF6gH1iJ0kM
```

⚠️ **CRITICAL SECURITY NOTES**:
- The command generates a **different random key each time** - you cannot recreate it
- **Copy and save** the generated key immediately (password manager recommended)
- If you lose the key, you'll be locked out of owner-protected operations
- Change the default key in `.env` before production deployment!

### 2. Create Your First Admin User

Use the provided script to create your first platform admin user:

```bash
# Inside the backend container
docker compose exec backend python -c "
from backend.api.api import app
from backend.api.models import db, PlatformUser
from datetime import datetime, timezone

with app.app_context():
    user = PlatformUser(
        username='yourusername',
        email='your@email.com',
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    user.set_password('your_secure_password')
    db.session.add(user)
    db.session.commit()
    print('✅ Platform user created successfully')
"
```

Or use the standalone script:

```bash
python scripts/maintenance/create_platform_user.py yourusername your@email.com your_password
```

### 3. Access the Console

Navigate to: **http://localhost:3000/platform-console** (or your production domain)

Login with the credentials you created in step 2.

## Using the Console

### Help Content Management Tab

This tab allows you to edit the FAQ and tutorial videos shown on the login page.

**Steps:**
1. Navigate to the "Help Content" tab
2. Enter your **Platform Owner Key** in the yellow input box
3. Click "Load Help Content" to fetch current content
4. Edit FAQs:
   - Click "+ Add FAQ" to add new questions
   - Fill in Question and Answer fields
   - Click "Remove" to delete FAQs
5. Edit Tutorials:
   - Click "+ Add Tutorial" to add video tutorials
   - Enter title and YouTube URL
   - Click "Remove" to delete tutorials
6. Click "Save Help Content" to publish changes

**Changes are immediately visible** to all schools on their login page!

### User Management Tab

Add assistant admins who can help you manage the platform.

**Steps:**
1. Navigate to the "User Management" tab
2. Enter your **Platform Owner Key** (required for adding/removing users)
3. Fill in the "Add New Admin User" form:
   - Username (unique)
   - Email (unique)
   - Password (secure)
4. Click "Add User"

The new user can immediately log in to the console with their credentials.

**View All Users:**
- See all platform admin users in the table
- Check their last login time and status
- Remove users by clicking "Remove" (owner key required)

## API Endpoints

The console uses these REST API endpoints:

### Authentication Endpoints

**POST /api/platform/auth/login**
- Login with username and password
- Returns JWT token for authenticated requests
- No owner key required

**GET /api/platform/auth/me**
- Get current authenticated user info
- Requires JWT token in Authorization header

### Help Content Endpoints

**GET /api/public/help-content**
- Public endpoint (no auth required)
- Returns current FAQ and tutorial content
- Used by login pages

**GET /api/platform/help-content**
- Get help content for editing
- Requires X-Platform-Owner-Key header

**PUT /api/platform/help-content**
- Update help content
- Requires X-Platform-Owner-Key header
- Body: `{"faqs": [...], "tutorials": [...]}`

### User Management Endpoints

**GET /api/platform/users**
- List all platform admin users
- Requires JWT token

**POST /api/platform/users**
- Add new platform admin user
- Requires X-Platform-Owner-Key header
- Body: `{"username": "...", "email": "...", "password": "..."}`

**DELETE /api/platform/users/:id**
- Remove platform admin user
- Requires X-Platform-Owner-Key header

## Security Considerations

1. **Owner Key Protection**: 
   - Never commit the owner key to version control
   - Use environment variables in production
   - Rotate the key periodically

2. **Password Security**:
   - All passwords are hashed using Werkzeug's secure password hashing
   - Use strong passwords for admin accounts
   - Consider implementing 2FA in future

3. **JWT Tokens**:
   - Platform user JWTs are prefixed with "platform:" to distinguish from tenant users
   - Tokens expire after configured duration (default: 24 hours)
   - Tokens are stored in browser localStorage

4. **Database Isolation**:
   - Platform users are stored in `platform_users` table (no school_id)
   - Completely separate from tenant user system
   - Cannot access tenant data through console

## Database Schema

**platform_users table:**
```sql
CREATE TABLE platform_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP NOT NULL,
    last_login TIMESTAMP
);
```

**platform_settings table:**
```sql
CREATE TABLE platform_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(120) UNIQUE NOT NULL,
    setting_value JSON NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

## Troubleshooting

### "Access denied: Platform owner credentials required"
- Make sure you've entered the correct owner key
- Verify PLATFORM_OWNER_KEY is set in .env and containers are restarted
- Owner key is only required for adding/removing users and editing help content

### "Invalid credentials" on login
- Verify the username and password are correct
- Check that the user exists in the platform_users table
- Ensure the user is_active = true

### Frontend not loading
- Check that containers are running: `docker compose ps`
- Verify frontend is accessible: `curl http://localhost:3000`
- Check browser console for JavaScript errors

### Can't save help content
- Verify owner key is correct
- Check backend logs: `docker compose logs backend`
- Ensure PLATFORM_OWNER_KEY environment variable is set

## Development vs Production

**Development:**
- Owner key is set in `.env` file
- Console accessible at `http://localhost:3000/platform-console`
- Default key should be changed even in development

**Production:**
- Set owner key as environment variable on server/container platform
- Console accessible at `https://yourdomain.com/platform-console`
- Use HTTPS only
- Consider IP whitelisting for console access
- Enable rate limiting on auth endpoints

## Future Enhancements

Potential features for future versions:

- [ ] Two-factor authentication for platform admins
- [ ] Audit log of all owner console actions
- [ ] Email notifications configuration
- [ ] Platform-wide announcements
- [ ] Analytics dashboard (total schools, users, revenue)
- [ ] Tenant management (suspend/activate schools)
- [ ] Backup and restore functionality
- [ ] Role-based permissions for assistant admins

## Support

For issues or questions about the Platform Owner Console, contact the development team.

---

**Last Updated**: February 28, 2026  
**Version**: 1.0.0
