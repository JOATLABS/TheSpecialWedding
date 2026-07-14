import {
  getMarketingCaptureAsset,
  MARKETING_CAPTURE_MANIFEST,
  type MarketingCaptureAsset,
} from './marketingCaptureManifest';

type MarketingCaptureFeatureId = keyof typeof MARKETING_CAPTURE_MANIFEST;

function featureCapture(featureId: MarketingCaptureFeatureId): MarketingCaptureAsset {
  return getMarketingCaptureAsset(featureId, 'features');
}

export type MarketingFeature = {
  id: string;
  icon: string;
  title: string;
  category: string;
  image: MarketingCaptureAsset;
  tagline: string;
  description: string;
  ai: boolean;
  /**
   * Optional blog post slug in app/resources/blog/data.tsx. When present, the
   * landing card and /features showcase render a "Read the story →" link to
   * /resources/blog/{blogSlug}. Not every feature has a dedicated post.
   */
  blogSlug?: string;
};

// Phase 1 copy must describe the prepared state visible in approved product
// proof. Do not imply mutation, automatic publishing, vendor access, or
// cross-surface propagation unless an approved capture contract demonstrates it.
export const MARKETING_FEATURES: MarketingFeature[] = [
  {
    id: 'dashboard',
    icon: '📊',
    title: 'The Morning View',
    category: 'Operations',
    image: featureCapture('dashboard'),
    tagline: 'Compare active weddings by RSVP movement, recent activity, pending forms, and setup progress.',
    description:
      'Morning View gives planners a portfolio scan of populated status, progress, and next-action context. Open the wedding record when setup needs attention.',
    ai: true,
  },
  {
    id: 'real-time',
    icon: '🗓️',
    title: 'Wedding Timeline & Event Days',
    category: 'Operations',
    image: featureCapture('real-time'),
    tagline: 'Present rehearsal, ceremony, reception, brunch, and cultural-event details across planner, couple, and public views.',
    description:
      'Configure each event day with its date, venue, time, attire, and order of events. The planner record, couple timeline, and public schedule present the prepared details for their respective audiences.',
    ai: false,
  },
  {
    id: 'couple-portal',
    icon: '💍',
    title: 'A Guided Couple Portal',
    category: 'Planner Portal',
    image: featureCapture('couple-portal'),
    tagline: 'Share the schedule, payment context, forms, and next steps couples need while planner-only work stays private.',
    description:
      'Couples get a guided dashboard for their wedding overview, timeline, payment context, and assigned forms. Planner-only controls and internal operations remain outside the couple view.',
    ai: false,
  },
  {
    id: 'wedding-website',
    icon: '🌐',
    title: 'Planner Record → Public Microsite',
    category: 'Wedding Website',
    image: featureCapture('wedding-website'),
    tagline: 'Present the wedding story, schedule, and approved gallery in a polished guest-facing view without planner controls.',
    description:
      'Prepare the story, branding, event details, and gallery in the planner wedding record. The public microsite presents those approved details for guests while private planning work stays out of view.',
    ai: false,
  },
  {
    id: 'wedding-configuration',
    icon: '⚙️',
    title: 'Wedding Configuration',
    category: 'Planner Setup',
    image: featureCapture('wedding-configuration'),
    tagline: 'Review event days, RSVP rules, privacy, registry, FAQs, theme, story, and public-wedding settings in one planner record.',
    description:
      'The Configure screen groups the planner-owned details behind the wedding experience: event days, venue, time, attire, RSVP and privacy rules, registry, FAQs, theme, and story. Public and couple views present the prepared details for their audiences while planner controls remain private.',
    ai: false,
  },
  {
    id: 'gallery-management',
    icon: '🖼️',
    title: 'Gallery Management',
    category: 'Planner Media',
    image: featureCapture('gallery-management'),
    tagline: 'Review each wedding gallery and its approved media from the planner workspace.',
    description:
      'Select a wedding and review its populated gallery, image labels, folder category, and total count from one planner workspace. Uploading new media and reviewing Guest Memories remain separate, clearly labelled workflows.',
    ai: false,
  },
  {
    id: 'guest-management',
    icon: '👥',
    title: 'Guest Management',
    category: 'Guest Pipeline',
    image: featureCapture('guest-management'),
    tagline: 'Review invitation, RSVP, group, meal, and plus-one context from one planner page.',
    description:
      'Guest Management combines populated totals with filterable table and card views, so planners can inspect response and guest context without rebuilding a spreadsheet.',
    ai: false,
  },
  {
    id: 'seating-orchestrator',
    icon: '🪑',
    title: 'Seating Chart Orchestrator',
    category: 'Guest Pipeline',
    image: featureCapture('seating-orchestrator'),
    tagline: 'Build seating on top of the real venue layout, from room outline and fixtures to guest assignments and export-ready charts.',
    description:
      'This is the event-space-aware seating surface. Planners can map the room, upload a venue reference, add fixtures like stages and bars, place tables, drag one guest at a time onto the right table, and review layout checks before exporting the final chart. Guest records, meal counts, household context, and AI grouping suggestions still stay connected to the same source of truth.',
    ai: true,
  },
  {
    id: 'guest-memories',
    icon: '📷',
    title: 'Guest Memories',
    category: 'Planner Media',
    image: featureCapture('guest-memories'),
    tagline: 'QR on the table → guests upload → couple reviews in the portal → export as a ZIP.',
    description:
      "This is the guest-facing upload flow. The planner generates a QR sign, guests scan it from the reception, enter their name, choose the part of the celebration, and upload photos or videos from their phone with no account and no app install. The couple reviews every memory privately in their portal before anything becomes part of the gallery, then exports kept memories as a ZIP. The planner controls the link, QR rotation, and close date; the couple owns review and downloads.",
    ai: false,
  },
  {
    id: 'inbox',
    icon: '📨',
    title: 'Planner Communications',
    category: 'Planner Operations',
    image: featureCapture('inbox'),
    tagline: 'Message couples, guests, vendors, families, and RSVP groups from one planner-owned workspace.',
    description:
      "This is a planner communications workspace, not a couple-only inbox. The planner can answer couple messages, guest questions, family requests, vendor follow-ups, and support conversations from the same wedding record. The workspace includes Inbox, Reminders & Invites, RSVP messaging, individual messages, and message history. The composer can insert platform data such as the wedding URL, couple names, wedding details, RSVP links, and reminder context, then send to one person, a filtered guest group, a vendor, a family contact, or a mass audience without copying data out of the platform.",
    ai: false,
  },
  {
    id: 'book-the-client',
    icon: '📝',
    title: 'Vendor Contracts → Payment Milestones',
    category: 'Business Engine',
    image: featureCapture('book-the-client'),
    tagline: 'Keep vendor scope, agreement status, payment milestones, and budget context connected in one planner-owned workflow.',
    description:
      'A planner can keep each vendor agreement beside the operational record it belongs to. Review the vendor, contract value, status, key dates, scope, clauses, deliverables, and payment milestones, then return to the wedding budget to see the same commitment in context. Agreement details, milestone status, vendor notes, and budget totals remain connected instead of splitting across documents and side spreadsheets.',
    ai: true,
  },
  {
    id: 'payments-autopilot',
    icon: '💳',
    title: 'Scheduled Client Payments',
    category: 'Business Engine',
    image: featureCapture('payments-autopilot'),
    tagline: 'See collected retainers, scheduled milestones, upcoming due dates, and cash flow in one place.',
    description:
      "The Money workspace turns the package payment schedule into an operating view. A planner can see the retainer already collected, the design-lock and final-production milestones still scheduled, the next due dates, and net incoming cash without reconciling a side spreadsheet. The package, contract, couple, and payment record stay connected, so the financial picture uses the same client plan the studio is already managing.",
    ai: false,
  },
  {
    id: 'budget',
    icon: '💰',
    title: 'Budget & Quote Negotiation',
    category: 'Business Engine',
    image: featureCapture('budget'),
    tagline: "Category budgets that warn you before overruns, with AI that pressure-tests every vendor quote.",
    description:
      "Three quotes from three florists, three PDFs, and no easy way to compare whether $14,000 for centerpieces is market or a rip-off. Budget here isn't a spreadsheet — it's a quote-negotiation workflow. Apply a budget template to a wedding or let AI generate one from event type and guest count. Log vendor quotes against the right category; the `quotes/compare` endpoint pressure-tests them against historical data and flags the outlier. Planned-vs-actual spend reads from the same record as the contracts and payments it references, so overrun alerts fire before a line item ships — not after.",
    ai: true,
  },
  {
    id: 'vendor-network',
    icon: '🏛️',
    title: 'Vendor Directory & CRM',
    category: 'Business Engine',
    image: featureCapture('vendor-network'),
    tagline: 'Keep vendor discovery, private vendor records, notes, files, agreements, and payment status tied to the wedding.',
    description:
      "The vendor directory is the planner's source record for the people and companies behind each wedding. Browse public vendor listings, save private contacts to your studio rolodex, attach documents, record notes, compare quotes, and open a vendor agreement when scope, terms, and payment milestones need to be formalized. The directory is not just a list of names; it is the vendor memory that keeps agreements, files, milestone status, and collaboration history from disappearing into email.",
    ai: true,
  },
  {
    id: 'knowledge-base',
    icon: '📚',
    title: 'Knowledge Base',
    category: 'Operations',
    image: featureCapture('knowledge-base'),
    tagline: 'Searchable SOPs, platform guides, and planner playbooks live inside the workspace your team already uses.',
    description:
      "When a new assistant joins or a planner forgets the exact Stripe, seating, inbox, or guest-memory flow, they should not learn by Slack archaeology. The Knowledge Base gives the studio searchable operating procedures, support articles, and platform guides in the admin workspace. Root admins can publish and maintain articles, planners can search by category, and the team has one living source for how the studio runs each wedding.",
    ai: false,
  },
  {
    id: 'forms',
    icon: '📋',
    title: 'Forms Canvas',
    category: 'Planner Intake',
    image: featureCapture('forms'),
    tagline: 'Send wedding checklists, onboarding questionnaires, vendor intake, and approval forms that write back to the record.',
    description:
      "Forms are not just contact forms. A planner can build a wedding checklist, onboarding questionnaire, design-preference form, vendor intake, final-approval checklist, or post-event follow-up and send it to the couple, a vendor, or anyone who needs to provide information. The form canvas works like the contract canvas: drag fields, group sections, reuse templates, and collect structured answers directly on the wedding record. No Typeform bill, no Jotform export, no stale copies.",
    ai: true,
  },
  {
    id: 'team',
    icon: '🧑‍🤝‍🧑',
    title: 'Team, Permissions & Audit',
    category: 'Operations',
    image: featureCapture('team'),
    tagline: 'Invite teammates, scope them to specific weddings, and trace every action in the audit log.',
    description:
      "Your assistant joins in March and needs to run point on three weddings while staying out of the other eight. In HoneyBook that's a shared login and crossed fingers. Here you invite her, assign her to those three weddings, and set her permissions granularly across twelve+ areas: guests, budget, gallery, vendors, contracts, forms, memories, and more. Every action she takes — an edit, a send, a delete — writes to the activity audit log alongside your own. Your team scales without the nightmare of screenshots pasted into Slack.",
    ai: false,
  },
];
