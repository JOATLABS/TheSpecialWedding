'use client';

import { useEffect, useRef } from 'react';
import { useCoupleSSEEvent } from '@/contexts/CoupleSSEContext';

export type CoupleSSEResource = 'couple_message';

export interface CoupleDataChangeEvent {
  resource: CoupleSSEResource | '__reconnected__';
  action: 'created' | 'updated' | 'deleted' | 'bulk_updated';
  wedding_id?: string | null;
  record_id?: string | null;
}

interface UseCoupleSSEOptions {
  resources?: CoupleSSEResource[];
  weddingId?: string | null;
  enabled?: boolean;
  onDataChange: (event: CoupleDataChangeEvent) => void;
}

export function useCoupleSSE({
  resources,
  weddingId,
  enabled = true,
  onDataChange,
}: UseCoupleSSEOptions) {
  const savedCallback = useRef(onDataChange);
  useEffect(() => {
    savedCallback.current = onDataChange;
  }, [onDataChange]);

  const resourceSet = useRef(new Set(resources));
  useEffect(() => {
    resourceSet.current = new Set(resources);
  }, [resources]);

  const weddingIdRef = useRef(weddingId);
  useEffect(() => {
    weddingIdRef.current = weddingId;
  }, [weddingId]);

  const enabledRef = useRef(enabled);
  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  useCoupleSSEEvent('data-change', (raw) => {
    if (!enabledRef.current) return;

    const data = raw as CoupleDataChangeEvent;

    if (data.resource === '__reconnected__') {
      savedCallback.current(data);
      return;
    }

    if (resourceSet.current.size > 0 && !resourceSet.current.has(data.resource as CoupleSSEResource)) {
      return;
    }

    if (weddingIdRef.current && data.wedding_id && data.wedding_id !== weddingIdRef.current) {
      return;
    }

    savedCallback.current(data);
  });
}
