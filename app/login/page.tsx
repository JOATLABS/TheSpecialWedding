import type { Metadata } from 'next';
import LoginRedirectClient from './LoginRedirectClient';

export const metadata: Metadata = {
  title: 'Sign in | The Special Wedding',
  description: 'Continue to The Special Wedding workspace sign-in.',
  robots: {
    index: false,
    follow: false,
  },
  alternates: {
    canonical: '/login',
  },
};

export default function LoginPage() {
  return <LoginRedirectClient />;
}
