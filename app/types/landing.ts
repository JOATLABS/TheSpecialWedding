// types/landing.ts

import { Wedding } from '@/types/wedding';

export interface GalleryImage {
  key: string;
  url: string;
}

export interface LandingLayoutProps {
  wedding: Wedding;
  images: GalleryImage[];
  guest?: unknown;
  openGuestRsvpOnLoad?: boolean;
}

export type SectionId = 'rsvp' | 'gallery' | 'registry' | 'faq';
