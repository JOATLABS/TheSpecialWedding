'use client';

import { useState } from 'react';
import { useAdmin } from '@/contexts/AdminContext';

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { SocialAuthButtons } from '@/components/auth/SocialAuthButtons';

export default function AdminLoginPage() {
  const { login } = useAdmin();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!email || !password) return;
    setLoading(true);
    try {
      await login(email, password, rememberMe);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-wedding-ivory">
      <Card className="w-full max-w-md bg-opacity-60 backdrop-blur-lg animate-slide-up">
        <CardHeader className="pb-0 text-center">
          <CardTitle className="font-elegant text-wedding-navy text-2xl">
            Admin Login
          </CardTitle>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="space-y-3" aria-label="Social login options">
            <SocialAuthButtons flow="login" redirectPath="/admin" />
            <p className="text-xs text-wedding-navy/80 text-center">
              Use your Google Workspace or Apple ID for secure, passwordless access.
            </p>
            <div className="flex items-center gap-3 text-wedding-navy/60 text-xs uppercase tracking-[0.3em]">
              <div className="h-px flex-1 bg-wedding-navy/20" aria-hidden="true"></div>
              <span>or</span>
              <div className="h-px flex-1 bg-wedding-navy/20" aria-hidden="true"></div>
            </div>
          </div>

          <input
            type="email"
            placeholder="Email"
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-wedding-rose transition"
          />

          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg pr-10 focus:outline-none focus:ring-2 focus:ring-wedding-rose transition"
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="absolute inset-y-0 right-3 flex items-center text-sm text-wedding-navy hover:text-wedding-rose"
            >
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>

          <label className="flex items-center text-sm text-wedding-navy">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="h-4 w-4 text-wedding-rose focus:ring-wedding-rose border-gray-300 rounded transition"
            />
            <span className="ml-2">Remember me</span>
          </label>

          <Button
            onClick={handleLogin}
            disabled={!email || !password || loading}
            className="w-full py-2 font-medium"
          >
            {loading ? 'Logging in…' : 'Log In'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
