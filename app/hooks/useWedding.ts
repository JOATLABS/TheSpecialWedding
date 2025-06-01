// hooks/useWedding.ts

import { useContext } from 'react';
import { WeddingContext } from '@/contexts/WeddingContext';
import { Wedding } from '@/types/wedding';

export function useWedding(): Wedding {
  const context = useContext(WeddingContext);
  if (!context) {
    throw new Error("useWedding must be used within a WeddingContext.Provider");
  }
return context as Wedding;
}
