"""Test script for email verification functionality"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.routers.auth import EmailService, TokenManager


async def test_smtp_connection():
    """Test SMTP connection"""
    print("=" * 60)
    print("SMTP Configuration Test")
    print("=" * 60)

    print(f"SMTP Host: {settings.SMTP_HOST}")
    print(f"SMTP Port: {settings.SMTP_PORT}")
    print(f"SMTP User: {settings.SMTP_USER}")
    print(f"SMTP Password: {'*' * len(settings.SMTP_PASSWORD) if settings.SMTP_PASSWORD else 'Not set'}")
    print(f"Frontend URL: {settings.FRONTEND_URL}")

    if not all([settings.SMTP_HOST, settings.SMTP_USER, settings.SMTP_PASSWORD]):
        print("\n❌ SMTP not fully configured!")
        return False

    print("\n✅ SMTP configuration looks good!")
    return True


async def test_email_sending():
    """Test sending verification email"""
    print("\n" + "=" * 60)
    print("Email Sending Test")
    print("=" * 60)

    test_email = input("\nEnter test email address (or press Enter to skip): ").strip()

    if not test_email:
        print("Skipped email sending test")
        return

    print(f"\nGenerating verification token for: {test_email}")

    # Generate a test token
    test_user_id = "507f1f77bcf86cd799439011"  # Dummy ObjectId
    token = TokenManager.generate_verification_token(test_user_id, test_email)

    print(f"Token generated: {token[:50]}...")
    print(f"\nVerification link would be:")
    print(f"{settings.FRONTEND_URL}/verify-email?token={token}")

    send = input("\nActually send this email? (y/n): ").strip().lower()

    if send == 'y':
        print("\nSending email...")
        try:
            EmailService.send_verification_email(test_email, token)
            print("✅ Email sent successfully!")
            print(f"\nCheck inbox for: {test_email}")
            print("(Note: May take a few seconds to arrive, check spam folder)")
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
    else:
        print("Email sending skipped")


async def test_token_verification():
    """Test token verification"""
    print("\n" + "=" * 60)
    print("Token Verification Test")
    print("=" * 60)

    token = input("\nEnter verification token to test (or press Enter to skip): ").strip()

    if not token:
        print("Skipped token verification test")
        return

    print("\nVerifying token...")
    payload = TokenManager.verify_token(token, "email_verification")

    if payload:
        print("✅ Token is valid!")
        print(f"User ID: {payload.get('user_id')}")
        print(f"Email: {payload.get('email')}")
        print(f"Type: {payload.get('type')}")
        print(f"Issued at: {payload.get('iat')}")
        print(f"Expires at: {payload.get('exp')}")
    else:
        print("❌ Token is invalid or expired!")


async def main():
    """Main test function"""
    print("\n" + "=" * 60)
    print("AI Investment Assistant - Email Verification Test")
    print("=" * 60)

    # Test 1: SMTP Configuration
    smtp_ok = await test_smtp_connection()

    if not smtp_ok:
        print("\n⚠️  Please configure SMTP settings in .env file")
        return

    # Test 2: Email Sending
    await test_email_sending()

    # Test 3: Token Verification
    await test_token_verification()

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
