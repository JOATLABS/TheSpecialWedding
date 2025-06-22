'use client';

import React from 'react';
import { WeddingContext } from '@/contexts/WeddingContext';
import { Wedding } from '@/types/wedding';

interface WeddingProviderProps {
  wedding: Wedding;
  children: React.ReactNode;
}

export function WeddingProvider({ wedding, children }: WeddingProviderProps) {
  return (
    <WeddingContext.Provider value={wedding}>
      {children}
    </WeddingContext.Provider>
  );
}