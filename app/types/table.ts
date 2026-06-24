export interface Table {
  id: string;
  wedding_id: string;
  name: string;
  shape: 'round' | 'rectangle';
  capacity: number;
  x: number;
  y: number;
  guests?: Guest[]; // Optional for frontend state
}

export interface Guest {
  id: string;
  wedding_id: string;
  name: string;
  token?: string;
  email?: string;
  phone?: string;
  group_id?: string;
  table_id?: string | null;
  role?: string;
  // Plus-one fields
  plus_one_allowed?: boolean;
  number_of_plus_ones_allowed?: number;
  plus_one_submitted?: boolean;
  // Communication opt-in fields
  sms_opt_in?: boolean | null;
  sms_opt_in_date?: string | null;
  sms_opt_out_date?: string | null;
  phone_status?: string | null;
  phone_status_updated_at?: string | null;
  email_opt_in?: boolean | null;
  email_opt_in_date?: string | null;
  email_opt_out_date?: string | null;
  // Invite tracking
  invite_sent?: boolean;
  invite_sent_date?: string | null;
  // Seating constraint fields
  must_sit_with?: string[];
  must_sit_apart?: string[];
  accessibility_needs?: string;
  seating_preference?: string;
  age_group?: string;
  language_preference?: string;
  // Timestamps
  created_at?: string;
  updated_at?: string;
}

export interface SeatingConstraint {
  guest_1: { id: string; name: string };
  guest_2: { id: string; name: string };
}

export interface SeatingConstraintsResponse {
  wedding_id: string;
  must_sit_together: SeatingConstraint[];
  must_sit_apart: SeatingConstraint[];
  summary: {
    total_must_sit_together: number;
    total_must_sit_apart: number;
    guests_with_constraints: number;
  };
}

export interface CreateTableRequest {
  wedding_id: string;
  name: string;
  shape: 'round' | 'rectangle';
  capacity: number;
  x?: number;
  y?: number;
}

export interface UpdateTableRequest {
  name?: string;
  shape?: 'round' | 'rectangle';
  capacity?: number;
  x?: number;
  y?: number;
}

export interface AssignGuestsRequest {
  guest_ids: string[];
  table_id: string;
}

export interface VenueLayoutPoint {
  x: number;
  y: number;
}

export type VenueFixtureType =
  | 'dance_floor'
  | 'bar'
  | 'stage'
  | 'entrance'
  | 'restrooms'
  | 'kitchen'
  | 'vendor_path';

export interface VenueFixture {
  id: string;
  type: VenueFixtureType;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation?: number;
}

export interface VenueLayout {
  id?: string | null;
  wedding_id: string;
  canvas_width: number;
  canvas_height: number;
  outline: VenueLayoutPoint[];
  background_image_data_url?: string | null;
  background_image_name?: string | null;
  background_locked?: boolean;
  scale_pixels?: number | null;
  scale_distance?: number | null;
  scale_unit?: 'ft' | 'm';
  fixtures: VenueFixture[];
  updated_at?: string | null;
  updated_by?: string;
}

export interface UpdateVenueLayoutRequest {
  canvas_width: number;
  canvas_height: number;
  outline: VenueLayoutPoint[];
  background_image_data_url?: string | null;
  background_image_name?: string | null;
  background_locked?: boolean;
  scale_pixels?: number | null;
  scale_distance?: number | null;
  scale_unit?: 'ft' | 'm';
  fixtures: VenueFixture[];
}
