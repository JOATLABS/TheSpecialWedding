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
  created_at?: string;
  [key: string]: any; // for flexibility (additional fields)
}
