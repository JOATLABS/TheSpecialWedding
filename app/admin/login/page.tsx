'use client';

import { useState } from 'react';
import { useAdmin } from '@/contexts/AdminContext';

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
    } catch (err) {
      // handled in AdminContext
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="max-w-md mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">Admin Login</h1>

      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="block w-full mb-2 px-3 py-2 border rounded"
        autoFocus
      />

      <div className="relative w-full mb-2">
        <input
          type={showPassword ? 'text' : 'password'}
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="block w-full px-3 py-2 border rounded pr-10"
        />
        <button
          type="button"
          onClick={() => setShowPassword((prev) => !prev)}
          className="absolute right-2 top-2 text-sm text-gray-600 hover:text-gray-800"
        >
          {showPassword ? 'Hide' : 'Show'}
        </button>
      </div>

      <label className="flex items-center text-sm mb-4">
        <input
          type="checkbox"
          checked={rememberMe}
          onChange={(e) => setRememberMe(e.target.checked)}
          className="mr-2"
        />
        Remember me
      </label>

      <button
        onClick={handleLogin}
        disabled={!email || !password || loading}
        className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:bg-blue-300"
      >
        {loading ? 'Logging in...' : 'Log In'}
      </button>
    </main>
  );
}
