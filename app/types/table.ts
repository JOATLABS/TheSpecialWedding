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
  email?: string;
  phone?: string;
  group_id?: string;
  table_id?: string | null;
  role?: string;
  plus_one_allowed?: boolean;
  rsvp_status?: string;
  dietary_restrictions?: string;
  notes?: string;
  // Seating constraint fields
  must_sit_with?: string[];
  must_sit_apart?: string[];
  accessibility_needs?: string;
  seating_preference?: string;
  age_group?: string;
  language_preference?: string;
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
