// types/wedding.ts

export interface EventDetails {
  venue_name?: string;
  location?: string;
  time?: string;
  attire?: string;
}

export interface WeddingEvent {
  type: 'traditional' | 'white_wedding' | 'reception' | 'engagement' | 'rehearsal';
  date: string;
  details?: EventDetails;
}

export interface RegistryItem {
  name: string;
  url: string;
  color?: string;
}

export interface FAQItem {
  question: string;
  answer: string;
}

export interface RSVPConfig {
  greeting: string;
  help_text: string;
  phone_numbers: string[];
}

export interface ThemeConfig {
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  background_style: 'gradient' | 'solid' | 'image';
  font_style: 'elegant' | 'modern' | 'classic' | 'playful';
}

export interface OurStory {
  text: string;
  image_url?: string;
  image_shape?: 'circle' | 'heart' | 'square' | 'hexagon';
}

export interface WeddingPartyMember {
  id: string;
  name: string;
  role: 'maid_of_honor' | 'bridesmaid' | 'best_man' | 'groomsman' | string;
  image_url?: string;
  display_order?: number;
  side: 'bride' | 'groom';
  linked_guest_id?: string;
  linked_guest_email?: string;
}

export interface Wedding {
  id: string;
  slug: string;
  couple_names: string;
  date: string;
  events: WeddingEvent[];
  rsvp_config?: RSVPConfig;
  registries?: RegistryItem[];
  faqs?: FAQItem[];
  theme_config?: ThemeConfig;
  featured_image?: string;
  our_story?: OurStory;
  wedding_party?: WeddingPartyMember[];
  created_at?: string;
  [key: string]: any; // for flexibility (additional fields)
}
