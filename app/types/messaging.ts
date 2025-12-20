export enum ParticipantRole {
  PLANNER = "planner",
  VENDOR = "vendor",
  COUPLE = "couple",
  WEDDING_PARTY = "wedding_party",
}

export enum ConversationChannel {
  CHAT = "chat",
  EMAIL = "email",
}

export interface MessageAttachment {
  type: string;
  reference_id?: string;
  title?: string;
  url?: string;
  metadata?: Record<string, any>;
}

export interface LinkedResource {
  resource_type: string;
  resource_id: string;
  title?: string;
}

export interface MessageResponse {
  message_id: string;
  conversation_id: string;
  sender_id?: string;
  sender_role: ParticipantRole;
  body: string;
  created_at: string; // Assuming datetime will be serialized as a string
  attachments: MessageAttachment[];
  linked_resource?: LinkedResource;
  delivery_status?: string;
}

export interface ConversationParticipant {
  user_id: string;
  role: ParticipantRole;
  joined_at: string; // Assuming datetime will be serialized as a string
  mute: boolean;
  last_read_at?: string; // Assuming datetime will be serialized as a string
}

export interface ConversationResponse {
  conversation_id: string;
  wedding_id?: string;
  channel: ConversationChannel;
  subject?: string;
  created_at: string; // Assuming datetime will be serialized as a string
  updated_at: string; // Assuming datetime will be serialized as a string
  last_message_at?: string; // Assuming datetime will be serialized as a string
  last_message_summary?: string;
  metadata: Record<string, any>;
  participants: ConversationParticipant[];
}
