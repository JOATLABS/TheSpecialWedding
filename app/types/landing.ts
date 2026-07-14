// types/landing.ts

import { Wedding } from '@/types/wedding';

export interface GalleryImage {
  key: string;
  url: string;
  displayName?: string;
  alt?: string;
  credit?: string;
}

export interface LandingLayoutProps {
  wedding: Wedding;
  images: GalleryImage[];
  galleryLoading?: boolean;
  galleryError?: boolean;
  onGalleryRetry?: () => void;
  guest?: unknown;
  openGuestRsvpOnLoad?: boolean;
}

export type SectionId = 'rsvp' | 'gallery' | 'registry' | 'faq';
