// types/landing.ts

import { Wedding } from '@/types/wedding';

export interface GalleryImage {
  key: string;
  url: string;
}

export interface LandingLayoutProps {
  wedding: Wedding;
  images: GalleryImage[];
}

export type SectionId = 'rsvp' | 'gallery' | 'registry' | 'faq';
