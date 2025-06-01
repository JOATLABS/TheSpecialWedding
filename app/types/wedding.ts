// types/wedding.ts

export interface Wedding {
  id: string;
  slug: string;
  couple_names: string;
  date: string;
  events: {
    type: 'traditional' | 'white_wedding' | 'reception';
    date: string;
  }[];
  [key: string]: any; // for flexibility (additional fields)
}
