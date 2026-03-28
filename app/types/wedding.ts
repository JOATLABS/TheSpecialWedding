// types/wedding.ts

export interface EventDetails {
  venue_name?: string;
  location?: string;
  time?: string;
  endTime?: string;
  attire?: string;
  timezone?: string;
}

export interface EventNote {
  id: string;
  author_role: 'planner' | 'couple';
  author_name?: string;
  text: string;
  status: 'pending' | 'seen' | 'addressed';
  created_at?: string;
}

export interface OrderOfEventsItem {
  id: string;
  title: string;
  description?: string;
  time?: string;
  duration_minutes?: number;
  order: number;
  notes: EventNote[];
}

export interface WeddingEvent {
  type: string;
  custom_type_label?: string;
  date: string;
  details?: EventDetails;
  order_of_events?: OrderOfEventsItem[];
  event_notes?: EventNote[];
}

export interface RegistryItem {
  name: string;
  url: string;
  color?: string;
}

export interface FAQItem {
  question: string;
  answer: string;
  link_url?: string;
  link_label?: string;
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

export interface PrivacySettings {
  privacy_mode: 'private' | 'password' | 'public';
  guest_auth_required: boolean;
  password_protection?: string;
  allow_guest_sharing: boolean;
  require_phone_verification: boolean;
  require_name_verification: boolean;
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

export interface WeddingPartySyncSettings {
  sync_enabled: boolean;
  sync_mode: 'auto' | 'manual';
  last_synced_at?: string;
}

export interface Wedding {
  id: string;
  slug: string;
  couple_names: string;
  date: string;
  timezone?: string;
  events: WeddingEvent[];
  rsvp_config?: RSVPConfig;
  privacy_settings?: PrivacySettings;
  registries?: RegistryItem[];
  faqs?: FAQItem[];
  theme_config?: ThemeConfig;
  featured_image?: string;
  our_story?: OurStory;
  wedding_party?: WeddingPartyMember[];
  wedding_party_sync?: WeddingPartySyncSettings;
  created_at?: string;
  [key: string]: any; // for flexibility (additional fields)
}
