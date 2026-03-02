import { useState } from "react";
import * as d3 from "d3";

// ─── Color Palette ───────────────────────────────────────────────
const colors = {
  bg: "#0F172A",
  surface: "#1E293B",
  surfaceHover: "#273548",
  card: "#1E293B",
  border: "#334155",
  borderLight: "#475569",
  accent: "#3B82F6",
  accentLight: "#60A5FA",
  accentDark: "#2563EB",
  green: "#22C55E",
  greenLight: "#4ADE80",
  orange: "#F59E0B",
  red: "#EF4444",
  purple: "#A855F7",
  pink: "#EC4899",
  teal: "#14B8A6",
  text: "#F1F5F9",
  textMuted: "#94A3B8",
  textDim: "#64748B",
  whatsapp: "#25D366",
  sms: "#3B82F6",
  email: "#F59E0B",
  inapp: "#A855F7",
  system: "#64748B",
};

const channelIcons = {
  whatsapp: "📱",
  sms: "💬",
  email: "📧",
  in_app: "🖥",
  system: "🤖",
};

const channelColors = {
  whatsapp: colors.whatsapp,
  sms: colors.sms,
  email: colors.email,
  in_app: colors.inapp,
  system: colors.system,
};

// ─── Mock Data ───────────────────────────────────────────────────
const conversations = [
  {
    id: 1,
    name: "Sarah & James",
    role: "Couple",
    roleBadge: "💍",
    channel: "whatsapp",
    preview: "Can we add 3 more guests to the list?",
    time: "2 min ago",
    unread: 2,
    wedding: "Emmanuel & Peace",
  },
  {
    id: 2,
    name: "Mrs. Johnson",
    role: "Guest",
    roleBadge: "👤",
    channel: "sms",
    preview: "Is there parking at the venue?",
    time: "15 min ago",
    unread: 1,
    wedding: "Emmanuel & Peace",
  },
  {
    id: 3,
    name: "Bloom Florals",
    role: "Vendor",
    roleBadge: "🏪",
    channel: "email",
    preview: "Centerpiece mockup attached",
    time: "1 hour ago",
    unread: 0,
    wedding: "Emmanuel & Peace",
  },
  {
    id: 4,
    name: "Michael Brown",
    role: "Guest",
    roleBadge: "👤",
    channel: "system",
    preview: "✓ RSVP confirmed for all events",
    time: "3 hours ago",
    unread: 0,
    wedding: "Emmanuel & Peace",
  },
  {
    id: 5,
    name: "DJ Rhythms",
    role: "Vendor",
    roleBadge: "🏪",
    channel: "whatsapp",
    preview: "Playlist finalized, sending over now",
    time: "Yesterday",
    unread: 0,
    wedding: "Emmanuel & Peace",
  },
  {
    id: 6,
    name: "Bridal Party",
    role: "Group",
    roleBadge: "👥",
    channel: "in_app",
    preview: "Rehearsal dinner at 6pm confirmed",
    time: "Yesterday",
    unread: 3,
    wedding: "Emmanuel & Peace",
  },
];

const messages = [
  {
    id: 1,
    sender: "You",
    content: "Here's the updated guest list template for your review",
    channel: "email",
    time: "Yesterday, 2:30 PM",
    direction: "outbound",
    status: "read",
  },
  {
    id: 2,
    sender: "Sarah",
    content: "Thanks! We reviewed it and it looks great.",
    channel: "whatsapp",
    time: "Yesterday, 4:15 PM",
    direction: "inbound",
    status: "read",
  },
  {
    id: 3,
    sender: "System",
    content: "✓ Sarah & James confirmed RSVP for Traditional Ceremony, White Wedding, Reception",
    channel: "system",
    time: "Yesterday, 5:00 PM",
    direction: "system",
    status: "delivered",
  },
  {
    id: 4,
    sender: "James",
    content: "Quick question - is there a kids' area at the reception venue?",
    channel: "whatsapp",
    time: "Today, 9:20 AM",
    direction: "inbound",
    status: "delivered",
  },
  {
    id: 5,
    sender: "Sarah",
    content: "Also, can we add 3 more guests to the list? James's cousins just confirmed they can make it!",
    channel: "whatsapp",
    time: "Today, 9:22 AM",
    direction: "inbound",
    status: "delivered",
  },
];

const guestProfile = {
  name: "Sarah & James Carter",
  role: "Couple",
  rsvpStatus: "Confirmed",
  events: ["Traditional Ceremony", "White Wedding", "Reception"],
  dietary: "No restrictions",
  tableAssignment: "Head Table",
  phone: "+1 (555) 234-5678",
  email: "sarah.carter@email.com",
  whatsapp: "+1 (555) 234-5678",
  preferredChannel: "WhatsApp",
  optIns: { sms: true, email: true, whatsapp: true },
};

// ─── Components ──────────────────────────────────────────────────

function Badge({ text, color }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 9999,
        fontSize: 10,
        fontWeight: 600,
        background: color + "22",
        color: color,
        letterSpacing: 0.5,
      }}
    >
      {text}
    </span>
  );
}

function ChannelBadge({ channel, small }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: small ? "1px 5px" : "2px 8px",
        borderRadius: 9999,
        fontSize: small ? 9 : 10,
        fontWeight: 500,
        background: (channelColors[channel] || colors.textDim) + "20",
        color: channelColors[channel] || colors.textDim,
      }}
    >
      {channelIcons[channel]} {channel.replace("_", "-")}
    </span>
  );
}

function DeliveryStatus({ status }) {
  const icons = {
    pending: "○",
    sent: "✓",
    delivered: "✓✓",
    read: "✓✓",
    failed: "✗",
  };
  return (
    <span
      style={{
        fontSize: 10,
        color: status === "read" ? colors.accentLight : status === "failed" ? colors.red : colors.textDim,
        marginLeft: 4,
      }}
    >
      {icons[status]}
    </span>
  );
}

// ─── Unified Inbox Mockup ────────────────────────────────────────

function UnifiedInbox() {
  const [selected, setSelected] = useState(0);
  const [filter, setFilter] = useState("all");
  const [showContext, setShowContext] = useState(true);
  const [msgInput, setMsgInput] = useState("");
  const [selChannel, setSelChannel] = useState("whatsapp");

  const filtered = filter === "all" ? conversations : filter === "unread" ? conversations.filter((c) => c.unread > 0) : conversations.filter((c) => c.channel === filter);

  return (
    <div style={{ display: "flex", height: 600, background: colors.bg, borderRadius: 12, overflow: "hidden", border: `1px solid ${colors.border}` }}>
      {/* ── Left: Conversation List ── */}
      <div style={{ width: 300, borderRight: `1px solid ${colors.border}`, display: "flex", flexDirection: "column" }}>
        {/* Header */}
        <div style={{ padding: "16px 16px 8px", borderBottom: `1px solid ${colors.border}` }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ color: colors.text, margin: 0, fontSize: 16, fontWeight: 700 }}>Messages</h3>
            <span
              style={{
                background: colors.accent,
                color: "#fff",
                borderRadius: 9999,
                padding: "2px 8px",
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              6
            </span>
          </div>
          {/* Filters */}
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {["all", "unread", "whatsapp", "sms", "email"].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  padding: "3px 10px",
                  borderRadius: 9999,
                  border: "none",
                  fontSize: 10,
                  fontWeight: 500,
                  cursor: "pointer",
                  background: filter === f ? colors.accent : colors.surface,
                  color: filter === f ? "#fff" : colors.textMuted,
                  transition: "all 0.15s",
                }}
              >
                {f === "all" ? "All" : f === "unread" ? "Unread" : channelIcons[f] + " " + f}
              </button>
            ))}
          </div>
        </div>
        {/* Conversation List */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {filtered.map((c, i) => (
            <div
              key={c.id}
              onClick={() => setSelected(i)}
              style={{
                padding: "12px 16px",
                cursor: "pointer",
                background: selected === i ? colors.surfaceHover : "transparent",
                borderBottom: `1px solid ${colors.border}22`,
                transition: "background 0.15s",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 14 }}>{c.roleBadge}</span>
                  <span style={{ color: colors.text, fontSize: 13, fontWeight: c.unread ? 700 : 500 }}>{c.name}</span>
                </div>
                <span style={{ fontSize: 10, color: colors.textDim }}>{c.time}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flex: 1, minWidth: 0 }}>
                  <ChannelBadge channel={c.channel} small />
                  <span
                    style={{
                      fontSize: 11,
                      color: c.unread ? colors.text : colors.textMuted,
                      fontWeight: c.unread ? 500 : 400,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {c.preview}
                  </span>
                </div>
                {c.unread > 0 && (
                  <span
                    style={{
                      background: colors.accent,
                      color: "#fff",
                      borderRadius: 9999,
                      minWidth: 18,
                      height: 18,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 10,
                      fontWeight: 700,
                      marginLeft: 8,
                    }}
                  >
                    {c.unread}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Center: Message Thread ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {/* Thread Header */}
        <div
          style={{
            padding: "12px 20px",
            borderBottom: `1px solid ${colors.border}`,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: colors.text, fontSize: 15, fontWeight: 700 }}>Sarah & James</span>
              <Badge text="COUPLE" color={colors.pink} />
              <Badge text="Emmanuel & Peace" color={colors.accent} />
            </div>
            <span style={{ fontSize: 11, color: colors.textDim }}>WhatsApp session active \u2022 Expires in 23h 38m</span>
          </div>
          <button
            onClick={() => setShowContext(!showContext)}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              border: `1px solid ${colors.border}`,
              background: showContext ? colors.accent + "20" : "transparent",
              color: showContext ? colors.accentLight : colors.textMuted,
              fontSize: 11,
              cursor: "pointer",
            }}
          >
            {showContext ? "Hide" : "Show"} Profile
          </button>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
          {messages.map((m) => {
            if (m.direction === "system") {
              return (
                <div key={m.id} style={{ textAlign: "center", margin: "16px 0" }}>
                  <span
                    style={{
                      background: colors.surface,
                      color: colors.textDim,
                      padding: "6px 16px",
                      borderRadius: 9999,
                      fontSize: 11,
                      display: "inline-block",
                    }}
                  >
                    {m.content}
                  </span>
                  <div style={{ fontSize: 9, color: colors.textDim, marginTop: 4 }}>{m.time}</div>
                </div>
              );
            }
            const isOutbound = m.direction === "outbound";
            return (
              <div key={m.id} style={{ display: "flex", justifyContent: isOutbound ? "flex-end" : "flex-start", marginBottom: 12 }}>
                <div
                  style={{
                    maxWidth: "70%",
                    background: isOutbound ? colors.accentDark + "40" : colors.surface,
                    borderRadius: 12,
                    borderTopRightRadius: isOutbound ? 2 : 12,
                    borderTopLeftRadius: isOutbound ? 12 : 2,
                    padding: "10px 14px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: isOutbound ? colors.accentLight : colors.green }}>{m.sender}</span>
                    <ChannelBadge channel={m.channel} small />
                  </div>
                  <p style={{ margin: 0, fontSize: 13, color: colors.text, lineHeight: 1.5 }}>{m.content}</p>
                  <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", marginTop: 4, gap: 4 }}>
                    <span style={{ fontSize: 9, color: colors.textDim }}>{m.time}</span>
                    {isOutbound && <DeliveryStatus status={m.status} />}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Compose */}
        <div style={{ padding: "12px 20px", borderTop: `1px solid ${colors.border}`, background: colors.surface }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <select
              value={selChannel}
              onChange={(e) => setSelChannel(e.target.value)}
              style={{
                padding: "8px 12px",
                borderRadius: 8,
                border: `1px solid ${colors.border}`,
                background: colors.bg,
                color: colors.text,
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              <option value="whatsapp">📱 WhatsApp</option>
              <option value="sms">💬 SMS</option>
              <option value="email">📧 Email</option>
              <option value="in_app">🖥 In-App</option>
            </select>
            <input
              type="text"
              value={msgInput}
              onChange={(e) => setMsgInput(e.target.value)}
              placeholder="Type a message..."
              style={{
                flex: 1,
                padding: "8px 14px",
                borderRadius: 8,
                border: `1px solid ${colors.border}`,
                background: colors.bg,
                color: colors.text,
                fontSize: 13,
                outline: "none",
              }}
            />
            <button
              style={{
                padding: "8px 12px",
                borderRadius: 8,
                border: "none",
                background: colors.surface,
                color: colors.textMuted,
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              📎
            </button>
            <button
              style={{
                padding: "8px 12px",
                borderRadius: 8,
                border: "none",
                background: colors.surface,
                color: colors.textMuted,
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              📝
            </button>
            <button
              style={{
                padding: "8px 20px",
                borderRadius: 8,
                border: "none",
                background: colors.accent,
                color: "#fff",
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Send
            </button>
          </div>
        </div>
      </div>

      {/* ── Right: Context Panel ── */}
      {showContext && (
        <div style={{ width: 280, borderLeft: `1px solid ${colors.border}`, overflowY: "auto", padding: 16 }}>
          <div style={{ textAlign: "center", marginBottom: 16 }}>
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: 9999,
                background: `linear-gradient(135deg, ${colors.pink}, ${colors.purple})`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 24,
                margin: "0 auto 8px",
              }}
            >
              💍
            </div>
            <h4 style={{ color: colors.text, margin: "0 0 4px", fontSize: 14 }}>{guestProfile.name}</h4>
            <Badge text={guestProfile.role} color={colors.pink} />
          </div>

          {/* RSVP */}
          <div style={{ background: colors.bg, borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <div style={{ fontSize: 10, color: colors.textDim, fontWeight: 600, marginBottom: 8, letterSpacing: 0.5 }}>RSVP STATUS</div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: 9999, background: colors.green }} />
              <span style={{ color: colors.green, fontSize: 13, fontWeight: 600 }}>{guestProfile.rsvpStatus}</span>
            </div>
            {guestProfile.events.map((e) => (
              <div key={e} style={{ fontSize: 11, color: colors.textMuted, padding: "2px 0" }}>
                ✓ {e}
              </div>
            ))}
          </div>

          {/* Details */}
          <div style={{ background: colors.bg, borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <div style={{ fontSize: 10, color: colors.textDim, fontWeight: 600, marginBottom: 8, letterSpacing: 0.5 }}>DETAILS</div>
            {[
              ["Dietary", guestProfile.dietary],
              ["Table", guestProfile.tableAssignment],
              ["Preferred", guestProfile.preferredChannel],
            ].map(([label, val]) => (
              <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                <span style={{ fontSize: 11, color: colors.textDim }}>{label}</span>
                <span style={{ fontSize: 11, color: colors.text }}>{val}</span>
              </div>
            ))}
          </div>

          {/* Contact */}
          <div style={{ background: colors.bg, borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <div style={{ fontSize: 10, color: colors.textDim, fontWeight: 600, marginBottom: 8, letterSpacing: 0.5 }}>CONTACT</div>
            <div style={{ fontSize: 11, color: colors.text, padding: "2px 0" }}>📱 {guestProfile.phone}</div>
            <div style={{ fontSize: 11, color: colors.text, padding: "2px 0" }}>📧 {guestProfile.email}</div>
          </div>

          {/* Opt-in */}
          <div style={{ background: colors.bg, borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <div style={{ fontSize: 10, color: colors.textDim, fontWeight: 600, marginBottom: 8, letterSpacing: 0.5 }}>CHANNEL OPT-IN</div>
            {Object.entries(guestProfile.optIns).map(([ch, v]) => (
              <div key={ch} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}>
                <span style={{ fontSize: 11, color: colors.textMuted }}>{ch.toUpperCase()}</span>
                <span style={{ fontSize: 11, color: v ? colors.green : colors.red }}>{v ? "Opted In" : "Opted Out"}</span>
              </div>
            ))}
          </div>

          {/* Quick Actions */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {["Update RSVP", "Edit Dietary Info", "Change Seating"].map((a) => (
              <button
                key={a}
                style={{
                  padding: "8px 12px",
                  borderRadius: 6,
                  border: `1px solid ${colors.border}`,
                  background: "transparent",
                  color: colors.accentLight,
                  fontSize: 11,
                  cursor: "pointer",
                  textAlign: "left",
                }}
              >
                {a}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Tech Stack Diagram ──────────────────────────────────────────

function TechStackDiagram() {
  const layers = [
    {
      label: "CLIENT LAYER",
      color: colors.accent,
      items: [
        { name: "Planner Dashboard", tech: "Next.js + React", desc: "Unified Inbox UI" },
        { name: "Couple Portal", tech: "Next.js", desc: "/{slug}/messages" },
        { name: "Guest Interface", tech: "SMS / WhatsApp / Email", desc: "External channels" },
      ],
    },
    {
      label: "REAL-TIME LAYER",
      color: colors.teal,
      items: [
        { name: "SSE / WebSocket", tech: "Server-Sent Events", desc: "New message push" },
        { name: "Redis Pub/Sub", tech: "Redis", desc: "Cross-instance fan-out" },
      ],
    },
    {
      label: "API LAYER",
      color: colors.green,
      items: [
        { name: "Conversation API", tech: "FastAPI", desc: "CRUD + search" },
        { name: "Message Router", tech: "FastAPI", desc: "Inbound routing engine" },
        { name: "Webhook Handlers", tech: "FastAPI", desc: "Twilio / Resend callbacks" },
      ],
    },
    {
      label: "CHANNEL ABSTRACTION",
      color: colors.orange,
      items: [
        { name: "Twilio SMS", tech: "Twilio API", desc: "Bidirectional SMS" },
        { name: "Twilio WhatsApp", tech: "WhatsApp Business API", desc: "Templates + sessions" },
        { name: "Resend Email", tech: "Resend API + Inbound", desc: "Bidirectional email" },
        { name: "In-App", tech: "Internal", desc: "Direct delivery" },
      ],
    },
    {
      label: "DATA LAYER",
      color: colors.purple,
      items: [
        { name: "MongoDB", tech: "conversations, messages", desc: "Primary datastore" },
        { name: "Cloudflare R2", tech: "Media storage", desc: "Attachments + thumbnails" },
        { name: "Redis", tech: "Cache + Pub/Sub", desc: "Sessions + real-time" },
      ],
    },
    {
      label: "INFRASTRUCTURE",
      color: colors.red,
      items: [
        { name: "Coolify", tech: "DigitalOcean Droplet", desc: "Container orchestration" },
        { name: "Cloudflare", tech: "DNS + CDN + R2", desc: "Edge + storage" },
        { name: "Stripe", tech: "Billing", desc: "SaaS subscriptions" },
      ],
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      {layers.map((layer, li) => (
        <div key={li} style={{ marginBottom: 16 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginBottom: 8,
            }}
          >
            <span
              style={{
                display: "inline-block",
                width: 4,
                height: 20,
                borderRadius: 2,
                background: layer.color,
              }}
            />
            <span style={{ fontSize: 10, fontWeight: 700, color: layer.color, letterSpacing: 1.5 }}>{layer.label}</span>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", paddingLeft: 16 }}>
            {layer.items.map((item, ii) => (
              <div
                key={ii}
                style={{
                  flex: "1 1 180px",
                  background: colors.surface,
                  border: `1px solid ${layer.color}30`,
                  borderRadius: 8,
                  padding: "10px 14px",
                  minWidth: 160,
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600, color: colors.text, marginBottom: 2 }}>{item.name}</div>
                <div style={{ fontSize: 10, color: layer.color, marginBottom: 2 }}>{item.tech}</div>
                <div style={{ fontSize: 10, color: colors.textDim }}>{item.desc}</div>
              </div>
            ))}
          </div>
          {li < layers.length - 1 && (
            <div style={{ textAlign: "center", padding: "6px 0", color: colors.textDim, fontSize: 14 }}>↓</div>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Workflow Diagrams ───────────────────────────────────────────

function FlowDiagram({ title, steps, color }) {
  return (
    <div style={{ marginBottom: 32 }}>
      <h4 style={{ color: color, fontSize: 14, fontWeight: 700, margin: "0 0 16px", display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 8, height: 8, borderRadius: 9999, background: color }} />
        {title}
      </h4>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 0, overflowX: "auto", paddingBottom: 8 }}>
        {steps.map((step, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center" }}>
            <div
              style={{
                minWidth: step.wide ? 180 : 140,
                background: step.highlight ? color + "20" : colors.surface,
                border: `1px solid ${step.highlight ? color : colors.border}`,
                borderRadius: step.type === "decision" ? 0 : 8,
                transform: step.type === "decision" ? "rotate(0deg)" : "none",
                padding: "10px 12px",
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 600, color: step.highlight ? color : colors.text, marginBottom: 2 }}>{step.label}</div>
              <div style={{ fontSize: 9, color: colors.textDim, lineHeight: 1.3 }}>{step.desc}</div>
            </div>
            {i < steps.length - 1 && (
              <div style={{ display: "flex", alignItems: "center", padding: "0 2px" }}>
                <div style={{ width: 20, height: 1, background: colors.textDim }} />
                <span style={{ color: colors.textDim, fontSize: 10 }}>→</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function WorkflowDiagrams() {
  return (
    <div style={{ padding: 24 }}>
      <FlowDiagram
        title="Outbound Message Flow"
        color={colors.accent}
        steps={[
          { label: "Planner Composes", desc: "Types message, selects channel", highlight: true },
          { label: "Resolve Channel", desc: "Check preferred channel + opt-in" },
          { label: "Abstraction Layer", desc: "Normalize to common format", highlight: true },
          { label: "Dispatch", desc: "Twilio / Resend / In-App", wide: true },
          { label: "Webhook Status", desc: "sent → delivered → read" },
          { label: "Update Thread", desc: "Store + notify in real-time", highlight: true },
        ]}
      />

      <FlowDiagram
        title="Inbound Message Flow (SMS / WhatsApp)"
        color={colors.whatsapp}
        steps={[
          { label: "Twilio Webhook", desc: "Incoming SMS/WA message", highlight: true },
          { label: "Normalize", desc: "Extract sender, content, media" },
          { label: "Route", desc: "Match phone → guest → wedding", highlight: true, type: "decision" },
          { label: "Find Conversation", desc: "Existing thread or create new" },
          { label: "Store Message", desc: "Append to thread + R2 media" },
          { label: "Notify Planner", desc: "SSE push + unread count", highlight: true },
        ]}
      />

      <FlowDiagram
        title="Inbound Email Flow"
        color={colors.email}
        steps={[
          { label: "Email Reply", desc: "Guest replies to conv-{id}@", highlight: true },
          { label: "Inbound Webhook", desc: "Resend / Mailgun parse" },
          { label: "Extract conv_id", desc: "From reply-to address", highlight: true },
          { label: "Strip Signatures", desc: "Remove quoted text + disclaimers" },
          { label: "Append to Thread", desc: "Store with email metadata" },
          { label: "Notify Planner", desc: "SSE push + badge update", highlight: true },
        ]}
      />

      <FlowDiagram
        title="RSVP → Conversation Integration"
        color={colors.green}
        steps={[
          { label: "Send RSVP Invite", desc: "Via Reminders page (bulk)", highlight: true },
          { label: "Record in Thread", desc: "Outbound msg in guest conversation" },
          { label: "Guest Responds", desc: "SMS reply or web form" },
          { label: "Update RSVP", desc: "Profile auto-updated", highlight: true },
          { label: "System Message", desc: "\"RSVP confirmed\" in thread" },
          { label: "Planner Context", desc: "Full history visible", highlight: true },
        ]}
      />

      <FlowDiagram
        title="Ambiguous Message Routing"
        color={colors.orange}
        steps={[
          { label: "Inbound Message", desc: "Unknown or multi-wedding phone", highlight: true },
          { label: "Check 24h Active", desc: "Recent conversation with sender?" },
          { label: "Check Reply Context", desc: "Reply to specific outbound?", type: "decision" },
          { label: "Ambiguous?", desc: "Flag for planner triage", highlight: true, type: "decision" },
          { label: "Planner Assigns", desc: "Manual wedding + thread assignment" },
          { label: "Thread Created", desc: "Future messages auto-route", highlight: true },
        ]}
      />
    </div>
  );
}

// ─── Main App ────────────────────────────────────────────────────

export default function App() {
  const [tab, setTab] = useState("inbox");

  const tabs = [
    { id: "inbox", label: "Unified Inbox", icon: "💬" },
    { id: "stack", label: "Tech Stack", icon: "🏗" },
    { id: "flows", label: "Workflow Diagrams", icon: "🔄" },
  ];

  return (
    <div style={{ background: colors.bg, minHeight: "100vh", color: colors.text, fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" }}>
      {/* Header */}
      <div style={{ padding: "20px 24px 0", borderBottom: `1px solid ${colors.border}` }}>
        <div style={{ marginBottom: 16 }}>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: colors.text }}>Unified Messaging Hub</h1>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: colors.textMuted }}>The Special Wedding \u2014 Interactive Mockups & Architecture</p>
        </div>
        <div style={{ display: "flex", gap: 0 }}>
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                padding: "10px 20px",
                border: "none",
                borderBottom: `2px solid ${tab === t.id ? colors.accent : "transparent"}`,
                background: "transparent",
                color: tab === t.id ? colors.text : colors.textMuted,
                fontSize: 13,
                fontWeight: tab === t.id ? 600 : 400,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 6,
                transition: "all 0.15s",
              }}
            >
              <span>{t.icon}</span> {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{ padding: 24 }}>
        {tab === "inbox" && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <h2 style={{ margin: "0 0 4px", fontSize: 16, fontWeight: 700 }}>Planner Unified Inbox</h2>
              <p style={{ margin: 0, fontSize: 12, color: colors.textMuted }}>Three-panel layout: Conversation List | Message Thread | Participant Context</p>
            </div>
            <UnifiedInbox />
            <div style={{ marginTop: 16, padding: 16, background: colors.surface, borderRadius: 8, border: `1px solid ${colors.border}` }}>
              <h4 style={{ margin: "0 0 8px", fontSize: 13, color: colors.accentLight }}>Key UI Features</h4>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {[
                  ["Channel Badges", "Each message tagged with its origin channel (WhatsApp, SMS, Email, In-App)"],
                  ["Delivery Status", "Real-time tracking: sent \u2192 delivered \u2192 read with visual indicators"],
                  ["Context Panel", "Guest/vendor profile with RSVP status, dietary info, seating \u2014 plus quick action buttons"],
                  ["Smart Filters", "Filter by wedding, channel, participant type, unread status"],
                  ["System Messages", "Automated events (RSVP confirmations, reminders) appear inline in the thread"],
                  ["Channel Selector", "Pick delivery channel per message, defaults to participant\u2019s preferred"],
                ].map(([title, desc], i) => (
                  <div key={i} style={{ fontSize: 11 }}>
                    <span style={{ fontWeight: 600, color: colors.text }}>{title}: </span>
                    <span style={{ color: colors.textMuted }}>{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === "stack" && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <h2 style={{ margin: "0 0 4px", fontSize: 16, fontWeight: 700 }}>Technical Architecture</h2>
              <p style={{ margin: 0, fontSize: 12, color: colors.textMuted }}>Full stack from client to infrastructure, layered by responsibility</p>
            </div>
            <div style={{ background: colors.surface, borderRadius: 12, border: `1px solid ${colors.border}`, overflow: "hidden" }}>
              <TechStackDiagram />
            </div>
            <div style={{ marginTop: 16, padding: 16, background: colors.surface, borderRadius: 8, border: `1px solid ${colors.border}` }}>
              <h4 style={{ margin: "0 0 8px", fontSize: 13, color: colors.accentLight }}>Architecture Decisions</h4>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {[
                  ["Channel Abstraction", "Common message format normalizes all channels, making it trivial to add new channels later"],
                  ["Twilio for WhatsApp", "Lowest friction path since the platform already uses Twilio for SMS"],
                  ["SSE \u2192 WebSocket", "Phase 1 starts with SSE for simplicity; Phase 3 upgrades to WebSocket for typing indicators"],
                  ["Redis Pub/Sub", "Enables cross-instance real-time delivery as the platform scales beyond a single server"],
                  ["MongoDB", "Existing datastore; conversation/message models fit naturally with the document model"],
                  ["Cloudflare R2", "Already used for media storage; extends naturally to message attachments"],
                ].map(([title, desc], i) => (
                  <div key={i} style={{ fontSize: 11 }}>
                    <span style={{ fontWeight: 600, color: colors.text }}>{title}: </span>
                    <span style={{ color: colors.textMuted }}>{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === "flows" && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <h2 style={{ margin: "0 0 4px", fontSize: 16, fontWeight: 700 }}>Message Flow Workflows</h2>
              <p style={{ margin: 0, fontSize: 12, color: colors.textMuted }}>How messages travel through the system for each scenario</p>
            </div>
            <div style={{ background: colors.surface, borderRadius: 12, border: `1px solid ${colors.border}`, overflow: "hidden" }}>
              <WorkflowDiagrams />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
