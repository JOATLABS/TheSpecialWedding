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
  group_id?: string;
  table_id?: string | null;
  role?: string;
  plus_one_allowed?: boolean;
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
