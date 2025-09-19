import React from 'react';
import { SaasLandingPage } from '@/components/saas/SaasLandingPage';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'TheSpecialWedding - Professional Wedding Planning Platform',
  description: 'Transform your wedding planning business with TheSpecialWedding - a comprehensive SaaS platform for wedding planners',
};

export default function HomePage() {
  return <SaasLandingPage />;
}