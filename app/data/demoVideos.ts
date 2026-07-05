import type { MarketingFeature } from './marketingFeatures';
import type { PublicDemoVideo, PublicDemoVideoStatus } from './publicDemoVideos';

export type DemoVideoStatus = PublicDemoVideoStatus;

export type DemoVideoPriority = 'hero' | 'phase-one' | 'phase-two';

export type DemoScriptStep = {
  timestamp: string;
  action: string;
  voiceover: string;
};

export type DemoVideo = {
  id: string;
  featureId?: MarketingFeature['id'];
  title: string;
  audience: string;
  durationSeconds: number;
  priority: DemoVideoPriority;
  status: DemoVideoStatus;
  assetUrl?: string;
  thumbnailUrl?: string;
  captionUrl?: string;
  transcriptUrl?: string;
  socialAssetUrl?: string;
  socialThumbnailUrl?: string;
  recordedAt?: string;
  appBuildLabel?: string;
  routePlan: readonly string[];
  seedRequirements: readonly string[];
  script: readonly DemoScriptStep[];
  recordingChecklist: readonly string[];
  captureNotes: string;
};

const defaultChecklist = [
  'Start from the product UI, not a mocked slide.',
  'Move through the flow with natural pauses, hover states, and visible saves.',
  'Keep private real customer data out of the frame.',
  'End on the activation action the viewer should remember.',
] as const;

const DEMO_VIDEO_RECORDED_AT = '2026-07-01';
const DEMO_VIDEO_APP_BUILD_LABEL = 'Public-safe browser walkthrough';
const DEMO_VIDEO_PUBLIC_ROOT = '/demo-videos';

function attachPublishedDemoAssets(demo: DemoVideo): DemoVideo {
  return {
    ...demo,
    status: 'published',
    assetUrl: `${DEMO_VIDEO_PUBLIC_ROOT}/exports/${demo.id}-16x9.mp4`,
    thumbnailUrl: `${DEMO_VIDEO_PUBLIC_ROOT}/thumbnails/${demo.id}-16x9.png`,
    captionUrl: `${DEMO_VIDEO_PUBLIC_ROOT}/captions/${demo.id}.json`,
    transcriptUrl: `${DEMO_VIDEO_PUBLIC_ROOT}/transcripts/${demo.id}.md`,
    socialAssetUrl: `${DEMO_VIDEO_PUBLIC_ROOT}/exports/${demo.id}-9x16.mp4`,
    socialThumbnailUrl: `${DEMO_VIDEO_PUBLIC_ROOT}/thumbnails/${demo.id}-9x16.png`,
    recordedAt: demo.recordedAt ?? DEMO_VIDEO_RECORDED_AT,
    appBuildLabel: demo.appBuildLabel ?? DEMO_VIDEO_APP_BUILD_LABEL,
  };
}

const HERO_DEMO_VIDEO_DRAFT: DemoVideo = {
  id: 'planner-command-center-walkthrough',
  title: '2-minute planner walkthrough',
  audience: 'Professional planners evaluating whether the workspace is real before starting a trial.',
  durationSeconds: 120,
  priority: 'hero',
  status: 'scripted',
  routePlan: [
    '/admin/planner',
    '/admin/weddings',
    '/admin/weddings/[id]',
    '/[slug]',
    '/couple/dashboard',
    '/admin/guests',
    '/admin/weddings/[id]/seating',
    '/admin/vendors',
    '/admin/budget',
  ],
  seedRequirements: [
    'One paid demo planner with two active weddings and one incomplete setup.',
    'A featured wedding with events, guests, RSVP data, gallery assets, vendor records, contract/payment milestones, and couple portal access.',
    'A couple account with registry, FAQ, memories, messages, forms, and one visible contract/payment checkpoint.',
  ],
  script: [
    {
      timestamp: '0:00-0:15',
      action: 'Open Morning View and scan the active wedding cards.',
      voiceover: 'This is the planner command center: weddings, unread updates, payments, guests, and next actions in one place.',
    },
    {
      timestamp: '0:15-0:35',
      action: 'Open the featured wedding setup and edit one event detail.',
      voiceover: 'A planner changes the source record once. Timeline, couple portal, reminders, and the public site all read from this same record.',
    },
    {
      timestamp: '0:35-0:55',
      action: 'Open the public microsite and couple portal in sequence.',
      voiceover: 'The couple and their guests see the polished version of the same plan without a second website builder or spreadsheet.',
    },
    {
      timestamp: '0:55-1:20',
      action: 'Move from Guest Management to Seating and assign one guest.',
      voiceover: 'Guest data flows into RSVP tracking, meals, plus-ones, seating, and day-of exports instead of being patched in five places.',
    },
    {
      timestamp: '1:20-1:45',
      action: 'Open vendor CRM, contract canvas, and payment/budget checkpoint.',
      voiceover: 'Vendors, contracts, quotes, and payments stay tied to the wedding record, so the business side does not split off into a separate tool stack.',
    },
    {
      timestamp: '1:45-2:00',
      action: 'Return to the dashboard and show the trial CTA.',
      voiceover: 'The activation moment is simple: start one wedding, invite the couple, and let the workspace become the operating system.',
    },
  ],
  recordingChecklist: [
    'Record desktop first, then a short mobile proof pass for homepage and public microsite.',
    'Show at least one real save, one navigation transition, one public/couple surface, and one planner-only surface.',
    'Do not trigger live payments, SMS sends, or external vendor emails during capture.',
  ],
  captureNotes:
    'Hero footage should be recorded locally with seeded demo data, then packaged in Remotion with captions and a CTA outro.',
};

export const HERO_DEMO_VIDEO: DemoVideo = attachPublishedDemoAssets(HERO_DEMO_VIDEO_DRAFT);

const FEATURE_DEMO_VIDEO_DRAFTS: readonly DemoVideo[] = [
  {
    id: 'morning-view-demo',
    featureId: 'dashboard',
    title: 'Morning View',
    audience: 'Planners who want proof the dashboard replaces a morning spreadsheet sweep.',
    durationSeconds: 60,
    priority: 'phase-one',
    status: 'scripted',
    routePlan: ['/admin/planner'],
    seedRequirements: [
      'Two active weddings with contrasting setup progress.',
      'Unread couple message, overdue payment, upcoming event, and RSVP velocity sample data.',
    ],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open the planner dashboard and pause on the active wedding summary.',
        voiceover: 'This is the 8am view: every wedding that needs attention, without opening a spreadsheet.',
      },
      {
        timestamp: '0:12-0:36',
        action: 'Scroll through RSVP, payment, message, and milestone signals.',
        voiceover: 'The dashboard pulls from guests, payments, messages, setup progress, and activity so the planner sees what changed overnight.',
      },
      {
        timestamp: '0:36-1:00',
        action: 'Open the next setup action for the incomplete wedding.',
        voiceover: 'The workflow does not end at insight. It points the planner to the next action that moves a real wedding forward.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Keep the cursor slow enough for metric labels to be readable in the final 16:9 crop.',
  },
  {
    id: 'wedding-timeline-demo',
    featureId: 'real-time',
    title: 'Wedding Timeline & Event Days',
    audience: 'Planners comparing calendar/timeline workflows against generic project tools.',
    durationSeconds: 45,
    priority: 'phase-two',
    status: 'scripted',
    routePlan: ['/admin/weddings/[id]', '/couple/dashboard', '/[slug]'],
    seedRequirements: ['One wedding with rehearsal, ceremony, reception, and brunch events populated.'],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open event-day setup for the wedding.',
        voiceover: 'A wedding is not one calendar block. Each event day has its own venue, time, attire, and guest-facing details.',
      },
      {
        timestamp: '0:12-0:30',
        action: 'Edit the reception start time and save.',
        voiceover: 'The planner updates the source record once instead of resending a PDF timeline.',
      },
      {
        timestamp: '0:30-0:45',
        action: 'Show the updated time in the couple portal and public schedule.',
        voiceover: 'The couple and guests now see the same corrected schedule.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Use a small edit that does not require backend time travel or provider sync.',
  },
  {
    id: 'couple-portal-demo',
    featureId: 'couple-portal',
    title: 'Couple Portal',
    audience: 'Planners who need to see what clients experience after the invite.',
    durationSeconds: 60,
    priority: 'phase-one',
    status: 'scripted',
    routePlan: ['/couple/dashboard'],
    seedRequirements: [
      'Couple account with timeline, messages, registry entries, FAQs, forms, memories, and one contract/payment checkpoint.',
    ],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Log in as the couple and land on the dashboard.',
        voiceover: 'This is what the couple sees after the planner invites them: one guided portal, not another spreadsheet.',
      },
      {
        timestamp: '0:12-0:38',
        action: 'Open timeline, messages, registry, FAQ, and meetings sections.',
        voiceover: 'The questions couples usually text about live here, and updates stay tied to the planner record.',
      },
      {
        timestamp: '0:38-1:00',
        action: 'Open memories/forms/contracts and return to the dashboard.',
        voiceover: 'The couple can review, respond, and self-serve while planner-only operations remain private.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Use a demo couple identity and avoid exposing any real email addresses in the header.',
  },
  {
    id: 'microsite-auto-publishes-demo',
    featureId: 'wedding-website',
    title: 'Microsite Auto-Publishes',
    audience: 'Planners deciding whether they can stop maintaining a separate wedding website.',
    durationSeconds: 45,
    priority: 'phase-one',
    status: 'scripted',
    routePlan: ['/admin/weddings/[id]', '/[slug]', '/[slug]/gallery'],
    seedRequirements: [
      'Public demo wedding with story, theme, events, gallery photos, registry, FAQ, and RSVP enabled.',
    ],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open the wedding configuration page and show slug/theme/story fields.',
        voiceover: 'The public wedding website is built from the wedding record the planner already manages.',
      },
      {
        timestamp: '0:12-0:28',
        action: 'Save a small story or schedule update.',
        voiceover: 'A planner updates the record once, without opening Squarespace or The Knot.',
      },
      {
        timestamp: '0:28-0:45',
        action: 'Open the public slug and gallery.',
        voiceover: 'The guest-facing microsite reflects the latest plan: story, schedule, gallery, RSVP, and memory uploads.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Capture both top-of-page branding and a scroll to the event schedule.',
  },
  {
    id: 'wedding-configuration-demo',
    featureId: 'wedding-configuration',
    title: 'Wedding Configuration',
    audience: 'Planners who want to understand setup effort before trying the product.',
    durationSeconds: 45,
    priority: 'phase-two',
    status: 'scripted',
    routePlan: ['/admin/weddings/[id]'],
    seedRequirements: ['One wedding with setup progress intentionally at 3 of 4 essentials.'],
    script: [
      {
        timestamp: '0:00-0:15',
        action: 'Open wedding details and scan setup tabs.',
        voiceover: 'Configuration is the planner-friendly layer for schedule, access, RSVP, content, and couple portal readiness.',
      },
      {
        timestamp: '0:15-0:34',
        action: 'Complete one missing essential field and save.',
        voiceover: 'The guide points to the next setup action instead of forcing the planner through a long wizard.',
      },
      {
        timestamp: '0:34-0:45',
        action: 'Show progress state and public/couple implications.',
        voiceover: 'Setup progress tells the team when the wedding is ready to invite the couple or publish.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Keep the guide compact in frame; avoid making the capture feel like documentation.',
  },
  {
    id: 'gallery-management-demo',
    featureId: 'gallery-management',
    title: 'Gallery Management',
    audience: 'Planners evaluating public gallery and wedding-party media setup.',
    durationSeconds: 45,
    priority: 'phase-two',
    status: 'scripted',
    routePlan: ['/admin/gallery/upload', '/admin/weddings/[id]', '/[slug]/gallery'],
    seedRequirements: ['Wedding with public gallery images, story images, and wedding-party entries.'],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open gallery management and show organized assets.',
        voiceover: 'Gallery management keeps public images, story media, and wedding-party photos in one planner-owned place.',
      },
      {
        timestamp: '0:12-0:30',
        action: 'Assign or review a public-facing image.',
        voiceover: 'The planner decides what appears on the microsite instead of letting uploads go live by accident.',
      },
      {
        timestamp: '0:30-0:45',
        action: 'Open the public gallery output.',
        voiceover: 'The couple and guests see the polished gallery fed from the same media library.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Seed media should be polished and non-private; avoid local file picker capture unless necessary.',
  },
  {
    id: 'guest-management-demo',
    featureId: 'guest-management',
    title: 'Guest Management',
    audience: 'Planners who currently live in guest spreadsheets.',
    durationSeconds: 60,
    priority: 'phase-one',
    status: 'scripted',
    routePlan: ['/admin/guests'],
    seedRequirements: [
      'Guest list with confirmed, declined, pending, plus-one, meal, accessibility, and household examples.',
    ],
    script: [
      {
        timestamp: '0:00-0:14',
        action: 'Open Guest Management and filter by RSVP status.',
        voiceover: 'This is the planner guest operating table: not a static spreadsheet.',
      },
      {
        timestamp: '0:14-0:36',
        action: 'Open a guest profile and edit RSVP/meal/accessibility details.',
        voiceover: 'Each guest record carries the details that seating, reminders, catering counts, and day-of exports need.',
      },
      {
        timestamp: '0:36-1:00',
        action: 'Show plus-one or group context and return to the table.',
        voiceover: 'When one guest changes, the platform updates the rest of the workflow instead of creating another manual reconciliation task.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Use demo guest names and show one visible save confirmation.',
  },
  {
    id: 'seating-orchestrator-demo',
    featureId: 'seating-orchestrator',
    title: 'Seating Chart Orchestrator',
    audience: 'Planners who need floor-plan-aware seating, not only table lists.',
    durationSeconds: 60,
    priority: 'phase-one',
    status: 'scripted',
    routePlan: ['/admin/weddings/[id]/seating'],
    seedRequirements: [
      'Venue layout with room outline, fixtures, at least six tables, and unassigned guests.',
    ],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open seating and show the room outline with fixtures.',
        voiceover: 'Seating starts with the actual room, not a blank grid.',
      },
      {
        timestamp: '0:12-0:36',
        action: 'Drag one guest to a table and show assignment state.',
        voiceover: 'Guest records, meal context, and household notes stay connected while the planner places people.',
      },
      {
        timestamp: '0:36-1:00',
        action: 'Open layout checks or preview/export view.',
        voiceover: 'The chart becomes an export-ready day-of artifact with venue context intact.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Capture pointer movement slowly; seating demos need to feel tactile and deliberate.',
  },
  {
    id: 'guest-memories-demo',
    featureId: 'guest-memories',
    title: 'Guest Memories',
    audience: 'Planners and couples evaluating QR photo collection.',
    durationSeconds: 45,
    priority: 'phase-two',
    status: 'scripted',
    routePlan: ['/[slug]/upload/[uploadToken]', '/couple/dashboard'],
    seedRequirements: ['Active memory upload link, sample pending memories, and couple review queue.'],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open the guest upload link as a guest.',
        voiceover: 'Guests scan a QR code and upload memories without an app or account.',
      },
      {
        timestamp: '0:12-0:28',
        action: 'Show the upload flow with a preselected safe demo file.',
        voiceover: 'The flow captures who uploaded it and which part of the celebration it belongs to.',
      },
      {
        timestamp: '0:28-0:45',
        action: 'Switch to couple review and approve one memory.',
        voiceover: 'The couple reviews uploads privately before anything becomes part of the gallery.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Use a prepared demo media asset; do not show Finder paths with personal filenames.',
  },
  {
    id: 'planner-communications-demo',
    featureId: 'inbox',
    title: 'Planner Communications',
    audience: 'Planners who need to see guest, couple, vendor, and reminder messaging in one workspace.',
    durationSeconds: 45,
    priority: 'phase-two',
    status: 'scripted',
    routePlan: ['/admin/communications', '/admin/communications/reminders', '/admin/communications/inbox'],
    seedRequirements: ['Wedding with guest groups, one couple thread, one support thread, and reminder templates.'],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open communications and choose a recipient group.',
        voiceover: 'Planner communications are scoped to the wedding record, not scattered across email and texts.',
      },
      {
        timestamp: '0:12-0:30',
        action: 'Insert a platform variable into a reminder message.',
        voiceover: 'The composer can use real wedding data instead of forcing the planner to copy and paste.',
      },
      {
        timestamp: '0:30-0:45',
        action: 'Open message history or inbox thread.',
        voiceover: 'Every send and reply stays attached to the wedding, ready for the team to inspect.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Do not send real SMS or email during capture; use local/test transport only.',
  },
  {
    id: 'contract-sign-pay-demo',
    featureId: 'book-the-client',
    title: 'Contract Canvas -> Sign -> Pay',
    audience: 'Planners comparing contract/payment workflows against DocuSign plus Stripe plus spreadsheets.',
    durationSeconds: 60,
    priority: 'phase-one',
    status: 'scripted',
    routePlan: ['/admin/vendors', '/admin/vendors/contracts/new', '/vendor-contract/[id]/[token]', '/admin/budget'],
    seedRequirements: [
      'Vendor record with service details, draft contract, public signing token, and test payment milestone.',
    ],
    script: [
      {
        timestamp: '0:00-0:15',
        action: 'Open vendor record and start or preview a contract.',
        voiceover: 'A vendor agreement starts from the record the planner already owns.',
      },
      {
        timestamp: '0:15-0:36',
        action: 'Show contract canvas clauses, scope, and payment milestones.',
        voiceover: 'Scope, clauses, deliverables, and payment terms stay connected instead of splitting into another document tool.',
      },
      {
        timestamp: '0:36-1:00',
        action: 'Open the public signing link and return to planner payment status.',
        voiceover: 'The signed contract and payment checkpoint flow back into the planner workspace.',
      },
    ],
    recordingChecklist: [
      ...defaultChecklist,
      'Use Stripe test mode only and stop before any irreversible external payment confirmation.',
    ],
    captureNotes: 'If the public signing flow is not seeded, record the planner contract preview and label public signing as the next capture checkpoint.',
  },
  {
    id: 'payment-autopilot-demo',
    featureId: 'payments-autopilot',
    title: 'Payment Autopilot',
    audience: 'Planners who want confidence payment follow-up is operationally visible.',
    durationSeconds: 45,
    priority: 'phase-two',
    status: 'scripted',
    routePlan: ['/admin/planner/billing', '/admin/budget'],
    seedRequirements: ['Payment schedule with upcoming, paid, and failed/retry-safe test milestones.'],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open payment schedule/status.',
        voiceover: 'Payment Autopilot keeps milestone charges and follow-up visible before the planner has to chase.',
      },
      {
        timestamp: '0:12-0:30',
        action: 'Show retry or failed-payment status without charging.',
        voiceover: 'Failed payments surface as workflow state, not a surprise buried in Stripe.',
      },
      {
        timestamp: '0:30-0:45',
        action: 'Show related budget/payment summary.',
        voiceover: 'The planner sees how the payment schedule connects back to the wedding budget.',
      },
    ],
    recordingChecklist: [
      ...defaultChecklist,
      'Do not confirm or schedule real financial transactions during capture.',
    ],
    captureNotes: 'Use a static seeded retry state; avoid advancing real payment jobs for a marketing recording.',
  },
  {
    id: 'budget-quote-demo',
    featureId: 'budget',
    title: 'Budget & Quote Negotiation',
    audience: 'Planners comparing vendor quotes and budget overrun workflows.',
    durationSeconds: 60,
    priority: 'phase-two',
    status: 'scripted',
    routePlan: ['/admin/budget', '/admin/budget/quotes'],
    seedRequirements: ['Budget template, three vendor quotes, one overrun warning, and one AI comparison response fixture.'],
    script: [
      {
        timestamp: '0:00-0:15',
        action: 'Open budget categories and planned versus actual spend.',
        voiceover: 'Budget is not a spreadsheet here. It is tied to the wedding, vendor quotes, contracts, and payments.',
      },
      {
        timestamp: '0:15-0:40',
        action: 'Open quote comparison for competing vendors.',
        voiceover: 'The planner can compare quotes and spot outliers before the couple overcommits.',
      },
      {
        timestamp: '0:40-1:00',
        action: 'Return to the budget summary and show warning state.',
        voiceover: 'Overrun risk is visible before a contract is signed, not after the money is gone.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Use cached AI/fixture output for predictable recording; do not depend on live provider latency.',
  },
  {
    id: 'vendor-directory-crm-demo',
    featureId: 'vendor-network',
    title: 'Vendor Directory & CRM',
    audience: 'Planners deciding whether vendor discovery and private vendor records can live together.',
    durationSeconds: 60,
    priority: 'phase-one',
    status: 'scripted',
    routePlan: ['/vendors', '/admin/vendors', '/portal/[token]'],
    seedRequirements: [
      'Public vendor directory with mixed categories, one saved private vendor record, one contract vendor token portal.',
    ],
    script: [
      {
        timestamp: '0:00-0:15',
        action: 'Open the public vendor directory and filter by category.',
        voiceover: 'Vendor discovery can start in the public directory without leaving the platform.',
      },
      {
        timestamp: '0:15-0:40',
        action: 'Open the planner-side vendor CRM record with notes, files, and contract state.',
        voiceover: 'Once a vendor belongs to a wedding, the private CRM record carries the notes, documents, quotes, contracts, and payout history.',
      },
      {
        timestamp: '0:40-1:00',
        action: 'Open a token vendor portal or contract workspace.',
        voiceover: 'Vendors can collaborate through scoped portals while the planner keeps the source record.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Make directory and CRM distinction visible; this is a key competitive proof point.',
  },
  {
    id: 'knowledge-base-demo',
    featureId: 'knowledge-base',
    title: 'Knowledge Base',
    audience: 'Studio owners who need repeatable process for assistants and teams.',
    durationSeconds: 30,
    priority: 'phase-two',
    status: 'scripted',
    routePlan: ['/admin/support'],
    seedRequirements: ['Knowledge base articles for seating, payments, guest reminders, and setup.'],
    script: [
      {
        timestamp: '0:00-0:10',
        action: 'Open the knowledge base inside the admin workspace.',
        voiceover: 'The operating manual lives where planners are already working.',
      },
      {
        timestamp: '0:10-0:22',
        action: 'Search for a seating or payment SOP.',
        voiceover: 'Assistants can find the studio playbook without Slack archaeology.',
      },
      {
        timestamp: '0:22-0:30',
        action: 'Open the article and show actionable steps.',
        voiceover: 'Guidance stays tied to the product workflows that need it.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Use concise article titles that read clearly at 1080p.',
  },
  {
    id: 'forms-canvas-demo',
    featureId: 'forms',
    title: 'Forms Canvas',
    audience: 'Planners using Typeform/Jotform for couple and vendor intake.',
    durationSeconds: 45,
    priority: 'phase-two',
    status: 'scripted',
    routePlan: ['/admin/forms', '/forms/[id]', '/couple/forms/[formId]'],
    seedRequirements: ['Reusable form template, public form link, couple form assignment, and one submitted response.'],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open forms and preview a wedding intake template.',
        voiceover: 'Forms are reusable workflows, not one-off documents.',
      },
      {
        timestamp: '0:12-0:30',
        action: 'Show sending or opening a public/couple form.',
        voiceover: 'The same canvas can collect information from couples, vendors, or guests.',
      },
      {
        timestamp: '0:30-0:45',
        action: 'Open responses inside the planner workspace.',
        voiceover: 'Answers write back into the wedding record instead of becoming another export.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Avoid personally identifying answers; use short demo responses.',
  },
  {
    id: 'team-permissions-audit-demo',
    featureId: 'team',
    title: 'Team, Permissions & Audit',
    audience: 'Studio owners scaling beyond one planner login.',
    durationSeconds: 45,
    priority: 'phase-two',
    status: 'scripted',
    routePlan: ['/admin/planner/team', '/admin/planner/activity-log'],
    seedRequirements: ['Team member with scoped wedding permissions and recent audit events.'],
    script: [
      {
        timestamp: '0:00-0:15',
        action: 'Open team management and inspect one assistant.',
        voiceover: 'A studio can give assistants access to the weddings and actions they actually own.',
      },
      {
        timestamp: '0:15-0:30',
        action: 'Show permission scopes across guests, budget, gallery, contracts, and team areas.',
        voiceover: 'Role checks are not enough; access is scoped to the wedding work.',
      },
      {
        timestamp: '0:30-0:45',
        action: 'Open activity log and filter recent writes.',
        voiceover: 'Every important action leaves a trail, so the studio can see who changed what.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Use a demo team member name; do not expose real staff accounts.',
  },
];

export const DEMO_VIDEO_PLAYLIST: readonly DemoVideo[] = [
  HERO_DEMO_VIDEO,
  ...FEATURE_DEMO_VIDEO_DRAFTS.map(attachPublishedDemoAssets),
];

export const FEATURE_DEMO_VIDEOS = DEMO_VIDEO_PLAYLIST.filter(
  (demo): demo is DemoVideo & { featureId: MarketingFeature['id'] } =>
    typeof demo.featureId === 'string',
);

const demoByFeatureId = new Map(
  FEATURE_DEMO_VIDEOS.map((demo) => [demo.featureId, demo] as const),
);

export function getDemoVideoByFeatureId(featureId: string): DemoVideo | undefined {
  return demoByFeatureId.get(featureId);
}

export function toPublicDemoVideo(demo: DemoVideo): PublicDemoVideo {
  return {
    id: demo.id,
    featureId: demo.featureId,
    title: demo.title,
    audience: demo.audience,
    durationSeconds: demo.durationSeconds,
    status: demo.status,
    assetUrl: demo.assetUrl,
    thumbnailUrl: demo.thumbnailUrl,
    captionUrl: demo.captionUrl,
    transcriptUrl: demo.transcriptUrl,
    socialAssetUrl: demo.socialAssetUrl,
    socialThumbnailUrl: demo.socialThumbnailUrl,
    recordedAt: demo.recordedAt,
  };
}

export function getPublicDemoVideoByFeatureId(featureId: string): PublicDemoVideo | undefined {
  const demo = getDemoVideoByFeatureId(featureId);
  return demo ? toPublicDemoVideo(demo) : undefined;
}

export function getDemoVideoStatusLabel(status: DemoVideoStatus): string {
  if (status === 'published') return 'Watch demo';
  if (status === 'recording') return 'Recording in progress';
  return 'Preview demo';
}
