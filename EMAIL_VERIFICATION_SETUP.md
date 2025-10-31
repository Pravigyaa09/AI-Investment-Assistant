# Email Verification Setup Guide

Complete end-to-end implementation of SMTP email verification for the AI Investment Assistant.

## 📋 Table of Contents
- [Overview](#overview)
- [Backend Configuration](#backend-configuration)
- [Testing the Implementation](#testing-the-implementation)
- [Frontend Integration](#frontend-integration)
- [Complete User Flow](#complete-user-flow)
- [Troubleshooting](#troubleshooting)

---

## Overview

The email verification system allows users to verify their email addresses after registration.

**Status:** ✅ **Fully Configured** (SMTP credentials already in `.env`)

---

## Backend Configuration

### 1. Settings Configuration

**File:** `backend/app/core/config.py`

Added SMTP settings:
```python
SMTP_HOST: Optional[str] = None
SMTP_PORT: int = 587
SMTP_USER: Optional[str] = None
SMTP_PASSWORD: Optional[str] = None
SMTP_FROM_NAME: str = "AI Investment Assistant"
FRONTEND_URL: str = "http://localhost:5173"
```

### 2. Environment Variables

**File:** `backend/.env`

Your current configuration:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=shreyyatnoor@gmail.com
SMTP_PASSWORD=loxz tlhz kzxa fuce
SMTP_FROM_NAME=AI Investment Assistant
FRONTEND_URL=http://localhost:5173
```

---

## Testing the Implementation

### Test Script

**File:** `backend/test_email.py`

Run the test script:
```bash
cd backend
python test_email.py
```

### Manual Testing via API

#### 1. Register a New User
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "SecurePass123",
    "confirm_password": "SecurePass123"
  }'
```

**Response:**
```json
{
  "id": "64f1a2b3c4d5e67890ab12cd",
  "email": "test@example.com",
  "username": "testuser",
  "is_active": true,
  "is_verified": false,
  "created_at": "2025-10-07T12:34:56.789Z"
}
```

🎉 **Verification email sent automatically in background!**

#### 2. Verify Email
```bash
curl -X POST http://localhost:8000/api/auth/verify-email/{TOKEN}
```

#### 3. Resend Verification
```bash
curl -X POST http://localhost:8000/api/auth/resend-verification \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

---

## Frontend Integration

### 1. Email Verification Page

**File:** `trading-platform-frontend/src/pages/VerifyEmail.jsx`

✅ Complete verification page with:
- Loading state while verifying
- Success message with auto-redirect
- Error handling with resend option

### 2. Router Configuration

**File:** `trading-platform-frontend/src/App.jsx`

✅ Added routes:
```jsx
<Route path="/register" element={<Register />} />
<Route path="/verify-email" element={<VerifyEmail />} />
```

---

## Complete User Flow

```
1. User Registers
   POST /api/auth/register
   → Account created with is_verified: false
   → Background task sends verification email

2. User Receives Email
   → HTML email with verification link
   → Link: http://localhost:5173/verify-email?token=...
   → Token valid for 24 hours

3. User Clicks Link
   → Frontend makes POST /api/auth/verify-email/{token}
   → Backend validates token and updates is_verified
   → Success message displayed

4. User Logs In
   → Can now access protected endpoints
```

---

## Troubleshooting

### Issue: "SMTP not configured" warning
**Solution:** Verify `.env` has all SMTP settings

### Issue: "Authentication failed" error
**Solution:** Use Gmail App Password (not regular password)

**Gmail App Password Setup:**
1. Enable 2FA: https://myaccount.google.com/security
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Copy 16-character password (remove spaces)
4. Update `.env`: `SMTP_PASSWORD=abcdefghijklmnop`

### Issue: Token expired
**Solution:** Request new verification email via resend endpoint

### Issue: Email goes to spam
**Solutions:**
- Add sender to contacts
- Mark as "Not spam"
- Use transactional email service (SendGrid, AWS SES) for production

---

## API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Register + send verification email |
| `/api/auth/login` | POST | Login (works with unverified users) |
| `/api/auth/verify-email/{token}` | POST | Verify email with token |
| `/api/auth/resend-verification` | POST | Resend verification email |
| `/api/auth/forgot-password` | POST | Request password reset email |
| `/api/auth/reset-password/{token}` | POST | Reset password with token |
| `/api/auth/me` | GET | Get current user info |

---

## Summary

✅ **SMTP Configuration** - Configured in `config.py` and `.env`
✅ **Email Service** - Implemented with HTML templates
✅ **Token Management** - JWT tokens with 24h expiration
✅ **Frontend Page** - Verification UI created
✅ **Router Integration** - Routes added to App.jsx
✅ **Test Script** - Testing tool available

**Your email verification system is ready to use!** 🎉

### Quick Start

1. **Start Backend:**
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. **Start Frontend:**
   ```bash
   cd trading-platform-frontend
   npm run dev
   ```

3. **Test Registration:**
   - Navigate to `http://localhost:5173/register`
   - Create account with real email
   - Check inbox for verification email
   - Click link to verify

4. **Monitor Logs:**
   ```bash
   tail -f backend/logs/app.log
   ```
