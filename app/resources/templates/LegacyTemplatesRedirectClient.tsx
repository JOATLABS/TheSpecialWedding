'use client';

import { useEffect } from 'react';

export default function LegacyTemplatesRedirectClient() {
  useEffect(() => {
    window.location.replace(`/resources?tab=templates${window.location.hash}`);
  }, []);

  return null;
}
