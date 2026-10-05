// Kiểu dữ liệu chat — khớp apps/api/app/chat/router.py & repo.py.

export type MessageKind = "text" | "image" | "listing" | "system";

export type ImageRef = { id: string; w: number; h: number };

export type ListingSnapshot = {
  listing_id: number;
  title: string;
  price: number | null;
  area: number | null;
  district: string | null;
  address: string | null;
  image: string | null;
  minutes_khu2: number | null;
};

export type Message = {
  id: number;
  conversation_id: number;
  sender_id: number | null; // null = tin hệ thống
  kind: MessageKind;
  body: string | null;
  payload: { images?: ImageRef[] } | ListingSnapshot | null;
  client_id: string | null;
  created_at: string;
  // chỉ có ở FE (optimistic)
  status?: "sending" | "failed";
  local_images?: string[]; // object URL xem trước khi đang upload
  retry?: () => void;
};

export type Partner = {
  id: number;
  name: string;
  avatar_url: string | null;
  don_vi: string | null;
  is_simulated: boolean;
  last_seen_at: string | null;
  online?: boolean;
};

export type Conversation = {
  id: number;
  created_at: string;
  last_message_at: string;
  score: number | null;
  unread: number;
  user_message_count: number;
  my_last_read: number;
  partner_last_read: number;
  partner: Partner;
  last_message: Pick<Message, "id" | "sender_id" | "kind" | "body" | "payload" | "created_at"> | null;
};

export type RoommateProfile = {
  user_id: number;
  name: string;
  avatar_url: string | null;
  email_verified: boolean | null;
  gender: string | null;
  don_vi: string | null;
  bio: string | null;
  sleep_time: number | null;
  wake_time: number | null;
  cleanliness: number | null;
  smoke: boolean | null;
  smoke_in_room: boolean | null;
  noise_tolerance: number | null;
  budget_band: number | null;
  is_simulated: boolean;
};

// T3 — liên hệ chỉ có khi CẢ HAI bên đồng ý (chat/repo.py:_CONTACT_SQL)
export type ContactPartner = {
  user_id: number;
  name: string;
  email: string | null;
  phone: string | null;
  zalo_url: string | null;
};

export type ContactState = {
  mine: boolean;
  theirs: boolean;
  unlocked: boolean;
  waiting_for_other: boolean;
  partner: ContactPartner | null;
};

export type ConversationDetail = Conversation & {
  partner_profile: RoommateProfile | null;
  shared_listings: { id: number; sender_id: number; payload: ListingSnapshot; created_at: string }[];
  contact?: ContactState | null;
};

// invite_id/note: "thích" đến từ lời mời kèm lời nhắn (POST /matching/invite)
export type Like = RoommateProfile & { liked_at: string; invite_id?: number | null; note?: string | null };

export type ChatEvent =
  | { type: "hello"; user_id: number; online: number[] }
  | { type: "pong" }
  | { type: "message.new"; conversation_id: number; message: Message }
  | { type: "read"; conversation_id: number; user_id: number; message_id: number }
  | { type: "typing"; conversation_id: number; user_id: number; is_typing: boolean }
  | { type: "presence"; user_id: number; online: boolean; last_seen_at?: string }
  | { type: "match.new"; conversation_id: number }
  | { type: "like.new" }
  | { type: "conversation.removed"; conversation_id: number; by_user_id: number }
  // T3: chỉ là TÍN HIỆU "bên kia vừa đồng ý" — cố ý không mang email/SĐT. Liên hệ
  // chỉ lấy được qua endpoint có cổng khoá trong SQL (chat/repo.py:_CONTACT_SQL).
  | { type: "contact.consent"; conversation_id: number; user_id: number; unlocked: boolean };

export type Me = { id: number; name: string };
