'use client';

// contexts/WeddingContext.ts

import React from 'react';
import { Wedding } from '@/types/wedding';

export const WeddingContext = React.createContext<Wedding | null>(null);
