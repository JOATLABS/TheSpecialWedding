'use client';

import React, { useMemo } from 'react';
import { WeddingContext } from '@/contexts/WeddingContext';
import { Wedding } from '@/types/wedding';

interface WeddingProviderProps {
  wedding: Wedding;
  children: React.ReactNode;
}

export function WeddingProvider({ wedding, children }: WeddingProviderProps) {
  const normalizedWedding = useMemo<Wedding>(() => ({
    ...wedding,
    event_location_private: Boolean(wedding.event_location_private),
  }), [wedding]);

  return (
    <WeddingContext.Provider value={normalizedWedding}>
      {children}
    </WeddingContext.Provider>
  );
}