"""
Shared configuration for backend unit and API tests.

Sets up environment variables and provides common fixtures.
"""

import os

# Setup environment BEFORE importing app
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-this-is-long-enough-for-validation-testing-purposes-2026",
)
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault(
    "API_KEY", "test-api-key-this-is-also-long-enough-for-validation-testing-purposes"
)
os.environ.setdefault("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")
os.environ.setdefault("MONGODB_URL", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_NAME", "test_wedding_app")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_" + "x" * 50)
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "pk_test_" + "x" * 50)
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")
os.environ.setdefault("S3_GUEST_MEDIA_BUCKET_NAME", "test-guest-media-bucket")
os.environ.setdefault("S3_AD_BUCKET_NAME", "test-ad-bucket")
os.environ.setdefault("S3_BLOG_BUCKET_NAME", "test-blog-bucket")
os.environ.setdefault("MEDIA_DOMAIN", "https://media.test.example.com")
os.environ.setdefault("GUEST_MEDIA_DOMAIN", "https://guest-media.test.example.com")
os.environ.setdefault("AD_MEDIA_DOMAIN", "https://ads.test.example.com")
os.environ.setdefault("BLOG_MEDIA_DOMAIN", "https://blogs.test.example.com")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("AURINKO_CLIENT_ID", "test-aurinko-client-id")
os.environ.setdefault("AURINKO_CLIENT_SECRET", "test-aurinko-client-secret")
os.environ.setdefault("AURINKO_APP_ID", "test-aurinko-app-id")
os.environ.setdefault("AURINKO_API_KEY", "test-aurinko-api-key")
os.environ.setdefault("AURINKO_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("AURINKO_OAUTH_STATE_SIGNING_KEY", "test-state-signing-key")
os.environ.setdefault(
    "AURINKO_REDIRECT_URI", "http://localhost:3000/admin/planner/calendar/callback"
)
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "test-token-encryption-key")
