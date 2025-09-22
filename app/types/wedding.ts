// types/wedding.ts

export interface EventDetails {
  venue_name?: string;
  location?: string;
  time?: string;
  attire?: string;
}

export type CoreEventType = 'traditional' | 'white_wedding' | 'reception' | 'engagement' | 'rehearsal';
export interface WeddingEvent {
  // Kept open for forward compatibility with backend-defined event types
  type: CoreEventType | string;
  date: string; // ISO date string
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

export interface CountdownConfig {
  enabled: boolean;
  target_date?: string;
  display_style: 'elegant' | 'modern' | 'minimal' | 'bold';
  show_seconds: boolean;
  show_labels: boolean;
  custom_message?: string;
  position: 'hero' | 'header' | 'floating';
}

export type WeddingStatus = 'active' | 'planning' | 'completed' | 'cancelled' | string;

export interface Wedding {
  id: string; // legacy id (landing site usage)
  _id?: string; // admin API sometimes provides _id
  slug: string;
  couple_names: string;
  date: string;
  events: WeddingEvent[];
  // Admin / operational fields
  assigned_planner_email?: string;
  assigned_planner_id?: string;
  venue?: string;
  guest_count?: number;
  total_budget?: number;
  status?: WeddingStatus;
  // Public site configuration
  rsvp_config?: RSVPConfig;
  registries?: RegistryItem[];
  faqs?: FAQItem[];
  theme_config?: ThemeConfig;
  featured_image?: string;
  our_story?: OurStory;
  wedding_party?: WeddingPartyMember[];
  countdown_config?: CountdownConfig;
  created_at?: string;
  [key: string]: any; // retained flexible index signature (consider narrowing in future)
}

export interface WeddingForm {
  couple_names: string;
  date: string;
  slug: string;
  assigned_planner_email?: string;
  venue?: string;
  status?: WeddingStatus;
  guest_count?: number;
  total_budget?: number;
  events: WeddingEvent[];
}

export interface WeddingTemplate {
  id: string;
  name: string;
  description: string;
  events: WeddingEvent[];
  status: WeddingStatus;
}

export type AssignmentFilter = 'all' | 'assigned' | 'unassigned';
export type DateFilter = 'all' | 'upcoming' | 'past' | 'this_month' | 'this_year';
