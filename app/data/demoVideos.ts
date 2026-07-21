import type { MarketingFeature } from './marketingFeatures';
import type { PublicDemoVideo, PublicDemoVideoStatus } from './publicDemoVideos';

export type DemoVideoStatus = PublicDemoVideoStatus;

export type DemoVideoPriority = 'hero' | 'phase-one' | 'phase-two';

export type DemoVideoProductionChannel = 'website' | 'social';

export type DemoScriptStep = {
  timestamp: string;
  action: string;
  voiceover: string;
};

export type DemoCaptureCheckpoint = {
  label: string;
  route: string;
  action: string;
  visibleResult: string;
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
  recordedAt?: string;
  appBuildLabel?: string;
  appBuildCommit?: string;
  productionChannel?: DemoVideoProductionChannel;
  phaseOnePillar?: string;
  socialOutcome?: string;
  routePlan: readonly string[];
  captureCheckpoints?: readonly DemoCaptureCheckpoint[];
  seedRequirements: readonly string[];
  script: readonly DemoScriptStep[];
  recordingChecklist: readonly string[];
  captureNotes: string;
};

export type PhaseOneSocialVideo = DemoVideo & {
  productionChannel: 'social';
  phaseOnePillar: string;
  socialOutcome: string;
};

export type PublicDemoVideoPublicationApproval = {
  approval: 'approved';
  captureReceiptPath: string;
  playbackApprovalPath: string;
  appBuildCommit: string;
  appBuildLabel: string;
  recordedAt: string;
  assetUrl: string;
  thumbnailUrl: string;
  captionUrl: string;
  transcriptUrl: string;
  // Legacy fields stay readable only so stale website approvals fail closed.
  // Social stories publish through PhaseOneSocialVideoPublicationApproval.
  socialAssetUrl?: string;
  socialThumbnailUrl?: string;
};

export type PhaseOneSocialVideoPublicationApproval = {
  approval: 'approved';
  captureReceiptPath: string;
  playbackApprovalPath: string;
  appBuildCommit: string;
  appBuildLabel: string;
  recordedAt: string;
  assetUrl: string;
  thumbnailUrl: string;
  captionUrl: string;
  transcriptUrl: string;
};

const defaultChecklist = [
  'Start from the product UI, not a mocked slide.',
  'Move through the flow with natural pauses and verify each visible result.',
  'Keep private real customer data out of the frame.',
  'End on the activation action the viewer should remember.',
] as const;

/**
 * Publication is intentionally allowlisted. A rendered file becoming present under
 * `public/` is not approval, and adding a new demo definition must never publish it.
 * Add a complete entry only after the manual receipt and public playback review pass.
 */
export const APPROVED_PUBLIC_DEMO_VIDEO_PUBLICATIONS: Readonly<
  Partial<Record<string, PublicDemoVideoPublicationApproval>>
> = Object.freeze({
  'planner-command-center-walkthrough': {
    approval: 'approved',
    captureReceiptPath: 'output/demo-videos/receipts/planner-command-center-walkthrough.json',
    playbackApprovalPath: 'output/demo-videos/playback-approvals/planner-command-center-walkthrough.json',
    appBuildCommit: '93e8a1c2ff217876004df948eb44f77fc9f7d189',
    appBuildLabel: 'Phase 1 planner OS product proof',
    recordedAt: '2026-07-14T22:11:04Z',
    assetUrl: '/demo-videos/exports/planner-command-center-walkthrough-16x9.mp4',
    thumbnailUrl: '/demo-videos/thumbnails/planner-command-center-walkthrough-16x9.png',
    captionUrl: '/demo-videos/captions/planner-command-center-walkthrough.vtt',
    transcriptUrl: '/demo-videos/transcripts/planner-command-center-walkthrough.md',
  },
  'morning-view-demo': {
    approval: 'approved',
    captureReceiptPath: 'output/demo-videos/receipts/morning-view-demo.json',
    playbackApprovalPath: 'output/demo-videos/playback-approvals/morning-view-demo.json',
    appBuildCommit: '1c7f7dbdb90ff74f41f8bf46b7a9f9114df3b10f',
    appBuildLabel: 'Phase 1 planner OS product proof',
    recordedAt: '2026-07-14T23:55:29Z',
    assetUrl: '/demo-videos/exports/morning-view-demo-16x9.mp4',
    thumbnailUrl: '/demo-videos/thumbnails/morning-view-demo-16x9.png',
    captionUrl: '/demo-videos/captions/morning-view-demo.vtt',
    transcriptUrl: '/demo-videos/transcripts/morning-view-demo.md',
  },
  'couple-portal-demo': {
    approval: 'approved',
    captureReceiptPath: 'output/demo-videos/receipts/couple-portal-demo.json',
    playbackApprovalPath: 'output/demo-videos/playback-approvals/couple-portal-demo.json',
    appBuildCommit: '6c561739be8a7b7a21dc57701a2ca89731400885',
    appBuildLabel: 'Phase 1 planner OS product proof',
    recordedAt: '2026-07-15T01:03:37Z',
    assetUrl: '/demo-videos/exports/couple-portal-demo-16x9.mp4',
    thumbnailUrl: '/demo-videos/thumbnails/couple-portal-demo-16x9.png',
    captionUrl: '/demo-videos/captions/couple-portal-demo.vtt',
    transcriptUrl: '/demo-videos/transcripts/couple-portal-demo.md',
  },
  'microsite-auto-publishes-demo': {
    approval: 'approved',
    captureReceiptPath: 'output/demo-videos/receipts/microsite-auto-publishes-demo.json',
    playbackApprovalPath: 'output/demo-videos/playback-approvals/microsite-auto-publishes-demo.json',
    appBuildCommit: '1c7f7dbdb90ff74f41f8bf46b7a9f9114df3b10f',
    appBuildLabel: 'Phase 1 planner OS product proof',
    recordedAt: '2026-07-15T00:54:15Z',
    assetUrl: '/demo-videos/exports/microsite-auto-publishes-demo-16x9.mp4',
    thumbnailUrl: '/demo-videos/thumbnails/microsite-auto-publishes-demo-16x9.png',
    captionUrl: '/demo-videos/captions/microsite-auto-publishes-demo.vtt',
    transcriptUrl: '/demo-videos/transcripts/microsite-auto-publishes-demo.md',
  },
  'guest-management-demo': {
    approval: 'approved',
    captureReceiptPath: 'output/demo-videos/receipts/guest-management-demo.json',
    playbackApprovalPath: 'output/demo-videos/playback-approvals/guest-management-demo.json',
    appBuildCommit: '1c7f7dbdb90ff74f41f8bf46b7a9f9114df3b10f',
    appBuildLabel: 'Phase 1 planner OS product proof',
    recordedAt: '2026-07-15T00:58:58Z',
    assetUrl: '/demo-videos/exports/guest-management-demo-16x9.mp4',
    thumbnailUrl: '/demo-videos/thumbnails/guest-management-demo-16x9.png',
    captionUrl: '/demo-videos/captions/guest-management-demo.vtt',
    transcriptUrl: '/demo-videos/transcripts/guest-management-demo.md',
  },
  'seating-orchestrator-demo': {
    approval: 'approved',
    captureReceiptPath: 'output/demo-videos/receipts/seating-orchestrator-demo.json',
    playbackApprovalPath: 'output/demo-videos/playback-approvals/seating-orchestrator-demo.json',
    appBuildCommit: '952dfcdfc60e72cd249a5a776c67fe85a5d58a01',
    appBuildLabel: 'Phase 1 planner OS product proof',
    recordedAt: '2026-07-15T01:28:21Z',
    assetUrl: '/demo-videos/exports/seating-orchestrator-demo-16x9.mp4',
    thumbnailUrl: '/demo-videos/thumbnails/seating-orchestrator-demo-16x9.png',
    captionUrl: '/demo-videos/captions/seating-orchestrator-demo.vtt',
    transcriptUrl: '/demo-videos/transcripts/seating-orchestrator-demo.md',
  },
  'contract-sign-pay-demo': {
    approval: 'approved',
    captureReceiptPath: 'output/demo-videos/receipts/contract-sign-pay-demo.json',
    playbackApprovalPath: 'output/demo-videos/playback-approvals/contract-sign-pay-demo.json',
    appBuildCommit: '1c7f7dbdb90ff74f41f8bf46b7a9f9114df3b10f',
    appBuildLabel: 'Phase 1 planner OS product proof',
    recordedAt: '2026-07-15T00:54:15Z',
    assetUrl: '/demo-videos/exports/contract-sign-pay-demo-16x9.mp4',
    thumbnailUrl: '/demo-videos/thumbnails/contract-sign-pay-demo-16x9.png',
    captionUrl: '/demo-videos/captions/contract-sign-pay-demo.vtt',
    transcriptUrl: '/demo-videos/transcripts/contract-sign-pay-demo.md',
  },
  // vendor-directory-crm-demo was intentionally removed from this allowlist on
  // 2026-07-21: the approved take led with the public marketing directory (an
  // ad-acquisition surface) instead of the planner-owned vendor CRM the demo
  // sells. The rescripted planner-first story requires a fresh manual retake
  // before it can be re-approved here.
});

export const APPROVED_PHASE_ONE_SOCIAL_VIDEO_PUBLICATIONS: Readonly<
  Partial<Record<string, PhaseOneSocialVideoPublicationApproval>>
> = Object.freeze({
  'connection-over-tools-social': {
    approval: 'approved',
    captureReceiptPath: 'output/demo-videos/receipts/connection-over-tools-social.json',
    playbackApprovalPath: 'output/demo-videos/playback-approvals/connection-over-tools-social.json',
    appBuildCommit: 'a494898bfadaf066356a8da7934bc3c110eaac0b',
    appBuildLabel: 'Phase 1 social product proof',
    recordedAt: '2026-07-15T03:51:56Z',
    assetUrl: '/demo-videos/exports/connection-over-tools-social-9x16.mp4',
    thumbnailUrl: '/demo-videos/thumbnails/connection-over-tools-social-9x16.png',
    captionUrl: '/demo-videos/captions/connection-over-tools-social.vtt',
    transcriptUrl: '/demo-videos/transcripts/connection-over-tools-social.md',
  },
  'disorganization-tax-social': {
    approval: 'approved',
    captureReceiptPath: 'output/demo-videos/receipts/disorganization-tax-social.json',
    playbackApprovalPath: 'output/demo-videos/playback-approvals/disorganization-tax-social.json',
    appBuildCommit: 'a494898bfadaf066356a8da7934bc3c110eaac0b',
    appBuildLabel: 'Phase 1 social product proof',
    recordedAt: '2026-07-15T04:01:06Z',
    assetUrl: '/demo-videos/exports/disorganization-tax-social-9x16.mp4',
    thumbnailUrl: '/demo-videos/thumbnails/disorganization-tax-social-9x16.png',
    captionUrl: '/demo-videos/captions/disorganization-tax-social.vtt',
    transcriptUrl: '/demo-videos/transcripts/disorganization-tax-social.md',
  },
  'couple-experience-boundaries-social': {
    approval: 'approved',
    captureReceiptPath: 'output/demo-videos/receipts/couple-experience-boundaries-social.json',
    playbackApprovalPath: 'output/demo-videos/playback-approvals/couple-experience-boundaries-social.json',
    appBuildCommit: 'a494898bfadaf066356a8da7934bc3c110eaac0b',
    appBuildLabel: 'Phase 1 social product proof',
    recordedAt: '2026-07-15T04:09:06Z',
    assetUrl: '/demo-videos/exports/couple-experience-boundaries-social-9x16.mp4',
    thumbnailUrl: '/demo-videos/thumbnails/couple-experience-boundaries-social-9x16.png',
    captionUrl: '/demo-videos/captions/couple-experience-boundaries-social.vtt',
    transcriptUrl: '/demo-videos/transcripts/couple-experience-boundaries-social.md',
  },
  'built-for-planners-social': {
    approval: 'approved',
    captureReceiptPath: 'output/demo-videos/receipts/built-for-planners-social.json',
    playbackApprovalPath: 'output/demo-videos/playback-approvals/built-for-planners-social.json',
    appBuildCommit: 'a494898bfadaf066356a8da7934bc3c110eaac0b',
    appBuildLabel: 'Phase 1 social product proof',
    recordedAt: '2026-07-15T04:15:25Z',
    assetUrl: '/demo-videos/exports/built-for-planners-social-9x16.mp4',
    thumbnailUrl: '/demo-videos/thumbnails/built-for-planners-social-9x16.png',
    captionUrl: '/demo-videos/captions/built-for-planners-social.vtt',
    transcriptUrl: '/demo-videos/transcripts/built-for-planners-social.md',
  },
});

export function isCompletePublicationApproval(
  approval: PublicDemoVideoPublicationApproval | undefined,
  demoId: string,
): approval is PublicDemoVideoPublicationApproval {
  if (!approval || approval.approval !== 'approved') return false;

  return /^[0-9a-f]{40}$/i.test(approval.appBuildCommit)
    && approval.captureReceiptPath === `output/demo-videos/receipts/${demoId}.json`
    && approval.playbackApprovalPath === `output/demo-videos/playback-approvals/${demoId}.json`
    && approval.assetUrl === `/demo-videos/exports/${demoId}-16x9.mp4`
    && approval.thumbnailUrl === `/demo-videos/thumbnails/${demoId}-16x9.png`
    && approval.captionUrl === `/demo-videos/captions/${demoId}.vtt`
    && approval.transcriptUrl === `/demo-videos/transcripts/${demoId}.md`
    && approval.socialAssetUrl === undefined
    && approval.socialThumbnailUrl === undefined
    && Number.isFinite(Date.parse(approval.recordedAt))
    && approval.appBuildLabel.trim().length > 0;
}

export function applyDemoVideoPublicationApproval(demo: DemoVideo): DemoVideo {
  const approval = APPROVED_PUBLIC_DEMO_VIDEO_PUBLICATIONS[demo.id];
  if (!isCompletePublicationApproval(approval, demo.id)) {
    return {
      ...demo,
      status: 'recording',
      assetUrl: undefined,
      thumbnailUrl: undefined,
      captionUrl: undefined,
      transcriptUrl: undefined,
      recordedAt: undefined,
      appBuildCommit: undefined,
      appBuildLabel: 'Public retake required',
    };
  }

  return {
    ...demo,
    status: 'published',
    assetUrl: approval.assetUrl,
    thumbnailUrl: approval.thumbnailUrl,
    captionUrl: approval.captionUrl,
    transcriptUrl: approval.transcriptUrl,
    recordedAt: approval.recordedAt,
    appBuildCommit: approval.appBuildCommit,
    appBuildLabel: approval.appBuildLabel,
  };
}

export function isCompletePhaseOneSocialVideoPublicationApproval(
  approval: PhaseOneSocialVideoPublicationApproval | undefined,
  story: PhaseOneSocialVideo,
): approval is PhaseOneSocialVideoPublicationApproval {
  if (!approval || approval.approval !== 'approved') return false;

  return /^[0-9a-f]{40}$/i.test(approval.appBuildCommit)
    && approval.captureReceiptPath === `output/demo-videos/receipts/${story.id}.json`
    && approval.playbackApprovalPath === `output/demo-videos/playback-approvals/${story.id}.json`
    && approval.assetUrl === `/demo-videos/exports/${story.id}-9x16.mp4`
    && approval.thumbnailUrl === `/demo-videos/thumbnails/${story.id}-9x16.png`
    && approval.captionUrl === `/demo-videos/captions/${story.id}.vtt`
    && approval.transcriptUrl === `/demo-videos/transcripts/${story.id}.md`
    && Number.isFinite(Date.parse(approval.recordedAt))
    && approval.appBuildLabel.trim().length > 0;
}

export function applyPhaseOneSocialVideoPublicationApproval(
  story: PhaseOneSocialVideo,
): PhaseOneSocialVideo {
  const approval = APPROVED_PHASE_ONE_SOCIAL_VIDEO_PUBLICATIONS[story.id];
  if (!isCompletePhaseOneSocialVideoPublicationApproval(approval, story)) {
    return {
      ...story,
      status: 'recording',
      assetUrl: undefined,
      thumbnailUrl: undefined,
      captionUrl: undefined,
      transcriptUrl: undefined,
      recordedAt: undefined,
      appBuildCommit: undefined,
      appBuildLabel: 'Public social cut not approved',
    };
  }

  return {
    ...story,
    status: 'published',
    assetUrl: approval.assetUrl,
    thumbnailUrl: approval.thumbnailUrl,
    captionUrl: approval.captionUrl,
    transcriptUrl: approval.transcriptUrl,
    recordedAt: approval.recordedAt,
    appBuildCommit: approval.appBuildCommit,
    appBuildLabel: approval.appBuildLabel,
  };
}

const HERO_DEMO_VIDEO_DRAFT: DemoVideo = {
  id: 'planner-command-center-walkthrough',
  title: 'Planner command center walkthrough',
  audience: 'Professional planners who want to see one wedding record stay coherent across planner, public, couple, and guest-response views.',
  durationSeconds: 75,
  priority: 'hero',
  status: 'scripted',
  routePlan: [
    '/admin/planner',
    '/admin/weddings/wedding_marketing_capture_sofia_daniel',
    '/sofia-and-daniel',
    '/couple/dashboard',
    '/admin/guests',
  ],
  captureCheckpoints: [
    {
      label: 'Planner command center',
      route: '/admin/planner',
      action: 'Scan both active wedding cards, then choose Manage for Sofia & Daniel.',
      visibleResult:
        'Two active weddings show populated progress and Sofia & Daniel is the connected story to follow.',
    },
    {
      label: 'Wedding event source',
      route: '/admin/weddings/wedding_marketing_capture_sofia_daniel',
      action: 'Open Events and inspect the Traditional event venue and 4:00 PM start time.',
      visibleResult:
        'The planner source record shows The Glasshouse at Riverbend and the 4:00 PM event time.',
    },
    {
      label: 'Public event plan',
      route: '/sofia-and-daniel',
      action: 'Manually switch to the prepared public tab and inspect the same event details.',
      visibleResult:
        'The public schedule shows The Glasshouse at Riverbend and 4:00 PM without planner controls.',
    },
    {
      label: 'Couple timeline',
      route: '/couple/dashboard',
      action: 'Manually switch to the prepared couple tab, open Timeline, and inspect the same event.',
      visibleResult:
        'The couple Timeline shows the same Glasshouse venue and 4:00 PM plan in its guided portal.',
    },
    {
      label: 'Guest response context',
      route: '/admin/guests',
      action: 'Return to the planner tab, open Guests, and filter the seeded table to Declined.',
      visibleResult:
        'The planner sees the Declined slice as operational context for the same wedding.',
    },
    {
      label: 'Return to command center',
      route: '/admin/planner',
      action: 'Return to the planner command center and pause on the connected portfolio.',
      visibleResult: 'The two active weddings and their next actions remain visible.',
    },
  ],
  seedRequirements: [
    'One paid demo planner with two active weddings and one incomplete setup.',
    'A featured wedding with matching event details across the planner record, public microsite, and couple timeline.',
    'A couple account plus seeded guest responses visible in the planner-owned guest workspace.',
  ],
  script: [
    {
      timestamp: '0:00-0:10',
      action: 'Scan the planner portfolio and choose Manage for Sofia & Daniel.',
      voiceover: 'Start with one wedding in the planner command center, then follow its plan instead of touring disconnected tools.',
    },
    {
      timestamp: '0:10-0:30',
      action: 'Open Events and inspect the Glasshouse venue and 4:00 PM start time.',
      voiceover: 'The wedding record is the source: The Glasshouse at Riverbend, four o’clock, captured once in the planner plan.',
    },
    {
      timestamp: '0:30-0:40',
      action: 'Manually switch to the public tab and inspect the matching event details.',
      voiceover: 'The guest-facing microsite presents that same venue and time without exposing planner operations.',
    },
    {
      timestamp: '0:40-0:50',
      action: 'Manually switch to the couple tab, open Timeline, and inspect the matching plan.',
      voiceover: 'The couple gets a guided view of the same venue and time while planner-only controls remain private.',
    },
    {
      timestamp: '0:50-1:05',
      action: 'Return to the planner, open Guests, and filter the table to Declined.',
      voiceover: 'Back in the planner workspace, isolate the declined list as operational context without reconciling another sheet.',
    },
    {
      timestamp: '1:05-1:15',
      action: 'Return to the command center, then hold for the five-second outro.',
      voiceover: 'One planner-owned workspace. Start with one wedding.',
    },
  ],
  recordingChecklist: [
    'Prepare authenticated planner and couple tabs plus the public microsite before recording; switch tabs manually during capture.',
    'Use visible planner navigation to reach Guests and return to the command center naturally.',
    'Do not change wedding, guest, or communication data during capture.',
    'End paused on the planner command center; the CTA is added by the Remotion composition.',
  ],
  captureNotes:
    'Record one connected 75-second outcome story: one planner source, two client-facing views, and one guest-response state visible in planner operations. The raw capture ends on the command center with no scripted browser control.',
};

export const HERO_DEMO_VIDEO: DemoVideo = applyDemoVideoPublicationApproval(HERO_DEMO_VIDEO_DRAFT);

const FEATURE_DEMO_VIDEO_DRAFTS: readonly DemoVideo[] = [
  {
    id: 'morning-view-demo',
    featureId: 'dashboard',
    title: 'Morning View',
    audience: 'Planners who want proof the dashboard replaces a morning spreadsheet sweep.',
    durationSeconds: 60,
    priority: 'phase-one',
    status: 'scripted',
    routePlan: [
      '/admin/planner',
      '/admin/weddings/wedding_marketing_capture_avery_morgan',
    ],
    captureCheckpoints: [
      {
        label: 'Portfolio overview',
        route: '/admin/planner',
        action: 'Scan both active wedding cards and compare their setup progress.',
        visibleResult:
          'Sofia & Daniel and Avery & Morgan show populated status, progress, and next-action context.',
      },
      {
        label: 'Attention signals',
        route: '/admin/planner',
        action: 'Review the visible RSVP, recent-activity, and pending-form signals across the portfolio.',
        visibleResult:
          'The seeded RSVP and setup signals distinguish the wedding that is moving from the one that needs attention.',
      },
      {
        label: 'Incomplete wedding guidance',
        route: '/admin/weddings/wedding_marketing_capture_avery_morgan',
        action: "Open Avery & Morgan's source record and inspect its incomplete setup guidance.",
        visibleResult:
          'The source record identifies the remaining setup work without changing wedding data.',
      },
    ],
    seedRequirements: [
      'Two active weddings with contrasting setup progress.',
      'Seeded RSVP response, recent-activity, and pending-form signals that are visible on the planner dashboard.',
    ],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open the planner dashboard and pause on the active wedding summary.',
        voiceover: 'This is the 8am view: every wedding that needs attention, without opening a spreadsheet.',
      },
      {
        timestamp: '0:12-0:36',
        action: 'Compare the visible RSVP, activity, and pending-form signals on the two wedding cards.',
        voiceover: 'RSVP movement, recent activity, pending forms, and setup progress distinguish what is moving from what needs attention.',
      },
      {
        timestamp: '0:36-1:00',
        action: "Open Avery & Morgan's source record and inspect the remaining setup guidance.",
        voiceover: 'The workflow does not end at insight. It points the planner to the next action that moves a real wedding forward.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Keep the complete 1440x900 product window visible and pause long enough for each status chip to be read without cropping.',
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
    captureCheckpoints: [
      {
        label: 'Couple dashboard',
        route: '/couple/dashboard',
        action: 'Inspect the wedding overview, guest snapshot, countdown, and guided next steps.',
        visibleResult:
          'Sofia & Daniel see their wedding context and current planning state without planner-only controls.',
      },
      {
        label: 'Shared timeline',
        route: '/couple/dashboard',
        action: 'Open Timeline, expand Traditional Ceremony, and inspect its three-item run of show.',
        visibleResult:
          'The couple-facing timeline shows the ceremony time, venue, and seeded processional, cocktail-hour, and reception-door cues.',
      },
      {
        label: 'Payment schedule',
        route: '/couple/dashboard',
        action: 'Open Payments and inspect the package and payment schedule without using payment controls.',
        visibleResult:
          'The couple can see the current contract and payment context while planner operations remain private.',
      },
      {
        label: 'Assigned forms',
        route: '/couple/dashboard',
        action: 'Open Forms and inspect the seeded questionnaire and its current completion status.',
        visibleResult:
          'The assigned questionnaire is visible inside the same guided wedding portal.',
      },
    ],
    seedRequirements: [
      'Couple account with timeline, messages, registry entries, FAQs, forms, memories, and one contract/payment checkpoint.',
    ],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Begin on the seeded couple dashboard and inspect the wedding overview.',
        voiceover: 'This is what the couple sees after the planner invites them: one guided portal, not another spreadsheet.',
      },
      {
        timestamp: '0:12-0:38',
        action: 'Open Timeline, expand Traditional Ceremony, then open Payments and inspect the shared financial context.',
        voiceover: 'The schedule and payment context couples usually ask about stay tied to the wedding record they already share with the planner.',
      },
      {
        timestamp: '0:38-1:00',
        action: 'Open Forms, inspect the assigned questionnaire, and return to the dashboard.',
        voiceover: 'The couple can review and self-serve while planner-only operations remain private.',
      },
    ],
    recordingChecklist: defaultChecklist,
    captureNotes: 'Use a demo couple identity and avoid exposing any real email addresses in the header.',
  },
  {
    id: 'microsite-auto-publishes-demo',
    featureId: 'wedding-website',
    title: 'Planner Record → Public Microsite',
    audience: 'Planners who want one coherent source for the wedding details they present to guests.',
    durationSeconds: 45,
    priority: 'phase-one',
    status: 'scripted',
    routePlan: [
      '/admin/weddings/wedding_marketing_capture_sofia_daniel',
      '/sofia-and-daniel',
      '/sofia-and-daniel/gallery',
    ],
    captureCheckpoints: [
      {
        label: 'Planner source record',
        route: '/admin/weddings/wedding_marketing_capture_sofia_daniel',
        action: 'Inspect the seeded story, theme, and privacy settings without changing any fields.',
        visibleResult:
          'The planner source record contains the public story, branding, and guest-access configuration.',
      },
      {
        label: 'Public wedding view',
        route: '/sofia-and-daniel',
        action: 'Manually switch to the prepared public microsite and inspect its story, venue, and event-day presentation.',
        visibleResult:
          'The guest-facing microsite presents Sofia & Daniel with the seeded story, approved venue, and event-day details.',
      },
      {
        label: 'Public gallery',
        route: '/sofia-and-daniel/gallery',
        action: 'Open the public gallery and inspect the approved seeded wedding images.',
        visibleResult:
          'The gallery shows the approved ceremony, portrait, and reception imagery without planner controls.',
      },
    ],
    seedRequirements: [
      'Public demo wedding with story, theme, events, gallery photos, registry, FAQ, and RSVP enabled.',
    ],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open the wedding source record and inspect its theme, story, and privacy settings.',
        voiceover: 'Begin with the planner-owned wedding record: its public story, branding, and guest-access settings.',
      },
      {
        timestamp: '0:12-0:28',
        action: 'Manually switch to the prepared public microsite and inspect its story, venue, and event-day presentation.',
        voiceover: 'The guest view presents the seeded public content in a polished experience without planner controls.',
      },
      {
        timestamp: '0:28-0:45',
        action: 'Open the public gallery and inspect the approved wedding images.',
        voiceover: 'The gallery completes the guest-facing view while the private planning workspace stays out of sight.',
      },
    ],
    recordingChecklist: [
      ...defaultChecklist,
      'Prepare the authenticated planner record and public microsite in separate clean tabs, then switch tabs manually with the browser address bar hidden.',
    ],
    captureNotes: 'Capture the planner story, theme, and privacy settings before the public story, venue, event details, and gallery; do not imply an edit or publishing event that is not shown.',
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
    captureCheckpoints: [
      {
        label: 'Guest operations summary',
        route: '/admin/guests',
        action: 'Inspect the seeded guest totals, invitation state, RSVP response, and plus-one metrics.',
        visibleResult:
          'The guest workspace shows populated invitation, response, attendance, and plus-one counts.',
      },
      {
        label: 'RSVP table slice',
        route: '/admin/guests',
        action: 'Filter the seeded table to Declined and inspect the visible RSVP, group, and plus-one columns.',
        visibleResult:
          'The table narrows to declined guests while keeping their group and plus-one state visible.',
      },
      {
        label: 'Guest card context',
        route: '/admin/guests',
        action: 'Clear the RSVP filter, switch to Card View, and inspect the collapsed Priya Shah card without opening any card actions.',
        visibleResult:
          'Priya Shah shows Confirmed, Friends, Vegetarian, and one submitted plus-one without exposing private controls.',
      },
    ],
    seedRequirements: [
      'Guest list with confirmed, declined, and pending examples plus a Priya Shah card seeded as Friends, Vegetarian, and one submitted plus-one.',
    ],
    script: [
      {
        timestamp: '0:00-0:14',
        action: 'Open Guest Management and inspect invitation, response, attendance, and plus-one totals.',
        voiceover: 'This is the planner guest operating table: invitation, response, attendance, and plus-one state in one view.',
      },
      {
        timestamp: '0:14-0:36',
        action: 'Filter to Declined and inspect the RSVP, group, and plus-one columns preserved in the table.',
        voiceover: 'The declined slice narrows the work without stripping away the visible guest context a planner still needs.',
      },
      {
        timestamp: '0:36-1:00',
        action: 'Clear the RSVP filter, switch to Card View, and inspect the collapsed Priya Shah card.',
        voiceover: 'Priya’s card brings her confirmed response, Friends group, vegetarian meal, and submitted plus-one into one readable planner view.',
      },
    ],
    recordingChecklist: [
      ...defaultChecklist,
      'Keep every guest card collapsed; do not open Details, Edit, QR, reminder, or delete controls.',
    ],
    captureNotes: 'Use demo guest names and keep the pass to the summary, Declined table filter, then the unfiltered collapsed Priya Shah card only.',
  },
  {
    id: 'seating-orchestrator-demo',
    featureId: 'seating-orchestrator',
    title: 'Seating Chart Orchestrator',
    audience: 'Planners who need floor-plan-aware seating, not only table lists.',
    durationSeconds: 60,
    priority: 'phase-one',
    status: 'scripted',
    routePlan: ['/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel'],
    captureCheckpoints: [
      {
        label: 'Venue-aware floor plan',
        route: '/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel',
        action: 'Use the in-product Zoom out control twice until it reads 70%, then inspect the seeded room outline, fixtures, and six positioned tables.',
        visibleResult:
          'The seating canvas uses the seeded venue plan instead of an empty generic grid.',
      },
      {
        label: 'Existing guest assignments',
        route: '/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel',
        action: 'Inspect the populated tables and existing guest assignments without moving anyone.',
        visibleResult:
          'Seeded guests are already connected to named tables with capacity context visible.',
      },
      {
        label: 'Day-of readiness checks',
        route: '/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel',
        action: 'Inspect the assigned totals, floor-plan status, and visible layout checks beside the canvas.',
        visibleResult:
          'The planner can review seating readiness and venue-layout warnings without changing the chart.',
      },
    ],
    seedRequirements: [
      'Venue layout with room outline, fixtures, at least six tables, and unassigned guests.',
    ],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open Seating, use the in-product Zoom out control twice to reach 70%, and show the room outline with fixtures.',
        voiceover: 'Seating starts with the actual room, not a blank grid.',
      },
      {
        timestamp: '0:12-0:36',
        action: 'Inspect the populated tables and existing guest assignments without moving anyone.',
        voiceover: 'Guest records, meal context, and household notes stay connected while the planner places people.',
      },
      {
        timestamp: '0:36-1:00',
        action: 'Inspect assigned totals, floor-plan status, and the visible layout checks.',
        voiceover: 'The chart becomes an export-ready day-of artifact with venue context intact.',
      },
    ],
    recordingChecklist: [
      ...defaultChecklist,
      'Use the seating canvas Zoom out control twice so its visible readout is 70%; keep browser page zoom at 100%.',
    ],
    captureNotes: 'Stage the in-product canvas at 70%, pan across existing assignments slowly, and do not drag guests, tables, fixtures, or floor-plan points.',
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
    title: 'Vendor Contracts -> Payment Milestones',
    audience: 'Planners who need vendor agreements, payment milestones, and wedding budget context in one workflow.',
    durationSeconds: 50,
    priority: 'phase-one',
    status: 'scripted',
    routePlan: [
      '/admin/vendors/contracts/67c100000000000000000001',
      '/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel',
    ],
    captureCheckpoints: [
      {
        label: 'Planner contract record',
        route: '/admin/vendors/contracts/67c100000000000000000001',
        action: 'Inspect the existing agreement, vendor, amount, status, and key dates in the planner workspace.',
        visibleResult:
          'The seeded Photography Services Agreement shows its vendor, value, status, version, and dates.',
      },
      {
        label: 'Contract canvas output',
        route: '/admin/vendors/contracts/67c100000000000000000001',
        action: 'Open Contract Sections and inspect the rendered scope, clauses, and terms in the read-only view.',
        visibleResult:
          'The read-only contract canvas presents the seeded agreement sections and legal terms.',
      },
      {
        label: 'Vendor payment milestones',
        route: '/admin/vendors/contracts/67c100000000000000000001',
        action: 'Open Payments and inspect the seeded deposit and remaining contract milestones.',
        visibleResult:
          'Payment Milestones shows the existing schedule and status without initiating a transaction.',
      },
      {
        label: 'Wedding budget context',
        route: '/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel',
        action: 'Return to the wedding budget and inspect the recorded vendor spend and category totals.',
        visibleResult:
          'The budget shows populated planned-versus-actual vendor spend for the same wedding workspace.',
      },
    ],
    seedRequirements: [
      'Vendor record with service details, populated agreement sections, status history, and payment milestones.',
      'Wedding budget with the same vendor commitment represented in its category totals.',
    ],
    script: [
      {
        timestamp: '0:00-0:12',
        action: 'Open the existing planner contract and inspect its details and status.',
        voiceover: 'A vendor agreement starts from the record the planner already owns.',
      },
      {
        timestamp: '0:12-0:30',
        action: 'Open Contract Sections, then Payments, and inspect the seeded clauses and milestones.',
        voiceover: 'Scope, clauses, deliverables, and payment terms stay connected instead of splitting into another document tool.',
      },
      {
        timestamp: '0:30-0:50',
        action: 'Return to the wedding budget and inspect the vendor commitment in its category context.',
        voiceover: 'The wedding budget carries that same vendor commitment into the planner\'s complete financial picture.',
      },
    ],
    recordingChecklist: [
      ...defaultChecklist,
      'Do not open payment-method or transaction controls; this recording is status inspection only.',
    ],
    captureNotes: 'Keep the story on the planner-owned vendor agreement, its payment milestones, and the connected wedding budget.',
  },
  {
    id: 'payment-autopilot-demo',
    featureId: 'payments-autopilot',
    title: 'Payment Autopilot',
    audience: 'Planners who want confidence payment follow-up is operationally visible.',
    durationSeconds: 45,
    priority: 'phase-two',
    status: 'scripted',
    routePlan: ['/admin/planner/billing', '/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel'],
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
    routePlan: ['/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel', '/admin/budget/quotes'],
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
    audience: 'Planners who want their studio’s vendor relationships, contracts, and payment status in one private workspace.',
    durationSeconds: 60,
    priority: 'phase-one',
    status: 'scripted',
    routePlan: [
      '/admin/vendors',
    ],
    captureCheckpoints: [
      {
        label: 'Vendor management overview',
        route: '/admin/vendors',
        action: 'Open Planner Vendor Management on the Overview tab and inspect vendor, contract, paid, and outstanding totals.',
        visibleResult:
          'The planner overview summarizes the seeded vendor book with its contract and payment totals.',
      },
      {
        label: 'Private vendor directory',
        route: '/admin/vendors',
        action: 'Open the Vendor Directory tab and inspect the saved studio contacts, categories, and wedding counts.',
        visibleResult:
          'The planner-owned directory shows the seeded contacts, including Luna Meridian Photography, with private operational context.',
      },
      {
        label: 'Planner contract context',
        route: '/admin/vendors',
        action: 'Open the Contracts tab and inspect the existing agreement amounts and statuses.',
        visibleResult:
          'The seeded agreements stay attached to the planner vendor workspace with visible status and value.',
      },
      {
        label: 'Vendor payment status',
        route: '/admin/vendors',
        action: 'Open the Payments tab and inspect the recorded milestone history without opening any transaction controls.',
        visibleResult:
          'The planner sees paid and outstanding context for the same vendor book without initiating a transaction.',
      },
    ],
    seedRequirements: [
      'Planner vendor workspace seeded with six saved contacts including Luna Meridian Photography, four agreements with mixed statuses, and populated paid and outstanding totals.',
    ],
    script: [
      {
        timestamp: '0:00-0:15',
        action: 'Open Planner Vendor Management and inspect the vendor, contract, paid, and outstanding totals.',
        voiceover: 'This is the planner’s private vendor CRM: the studio’s vendor book, contracts, and payment context in one workspace.',
      },
      {
        timestamp: '0:15-0:40',
        action: 'Open the Vendor Directory tab and inspect the saved studio contacts and their wedding history.',
        voiceover: 'The directory is the planner’s own working list — the vendors a studio rebooks wedding after wedding, with contact context that stays with the business.',
      },
      {
        timestamp: '0:40-1:00',
        action: 'Open the Contracts tab, then the Payments tab, and inspect the agreement amounts and recorded status.',
        voiceover: 'Every vendor stays connected to its agreements and payment status, so the relationship and the money live in one planner-owned record.',
      },
    ],
    recordingChecklist: [
      'Prepare one authenticated planner tab on Vendor Management with the address bar hidden before recording.',
      ...defaultChecklist,
      'Stay inside the planner workspace for the entire take; the public marketing directory is not part of this story.',
      'Do not open vendor edit, delete, or transaction controls; this recording is status inspection only.',
    ],
    captureNotes:
      'Tell the story entirely inside the planner-owned Vendor Management workspace: overview totals, the private directory, contracts, then payments. The public marketing directory is intentionally excluded — it is an advertising acquisition surface, not the planner CRM this demo proves.',
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

const PHASE_ONE_SOCIAL_VIDEO_STORY_DRAFTS = [
  {
    id: 'connection-over-tools-social',
    title: 'One plan. Three clear views.',
    audience: 'Wedding planners replacing disconnected planner, couple, and guest tools.',
    durationSeconds: 30,
    priority: 'phase-one',
    status: 'scripted',
    productionChannel: 'social',
    phaseOnePillar: 'Connection Over Tools',
    socialOutcome:
      'Keep planner, couple, and guest context connected without exposing planner controls.',
    routePlan: [
      '/admin/weddings/wedding_marketing_capture_sofia_daniel',
      '/sofia-and-daniel',
      '/couple/dashboard',
    ],
    captureCheckpoints: [
      {
        label: 'Connection planner source',
        route: '/admin/weddings/wedding_marketing_capture_sofia_daniel',
        action: 'Open Events and hold on The Glasshouse at Riverbend at 4:00 PM.',
        visibleResult:
          'The planner-owned event record shows The Glasshouse at Riverbend and the 4:00 PM start.',
      },
      {
        label: 'Connection guest view',
        route: '/sofia-and-daniel',
        action: 'Switch manually to the public schedule and hold on the same venue and time.',
        visibleResult:
          'The public wedding schedule shows the Glasshouse venue and 4:00 PM without planner controls.',
      },
      {
        label: 'Connection couple view',
        route: '/couple/dashboard',
        action: 'Switch manually to the couple Timeline and hold on the matching event plan.',
        visibleResult:
          'The couple Timeline presents the same Glasshouse event inside the guided couple workspace.',
      },
    ],
    seedRequirements: [
      'The Sofia & Daniel event must match across the planner record, public schedule, and couple Timeline.',
      'Prepared planner, public, and couple tabs must use only the isolated marketing-capture identities.',
    ],
    script: [
      {
        timestamp: '0:00-0:08',
        action: 'Hold on the planner event source at The Glasshouse at Riverbend and 4:00 PM.',
        voiceover: 'Connection matters more than adding another tool. Start with one planner-owned event plan.',
      },
      {
        timestamp: '0:08-0:17',
        action: 'Switch manually to the public wedding schedule with the same venue and time.',
        voiceover: 'Guests get the details they need without seeing the work behind them.',
      },
      {
        timestamp: '0:17-0:25',
        action: 'Switch manually to the couple Timeline and hold on the matching event.',
        voiceover: 'The couple sees the same plan in a guided workspace. One wedding, three clear views.',
      },
    ],
    recordingChecklist: [
      ...defaultChecklist,
      'Prepare planner, public, and couple tabs before recording, then switch between them manually.',
      'Do not edit event data or expose the local origin during the take.',
    ],
    captureNotes:
      'Record a distinct 25-second product story plus the five-second social outro; do not reuse or crop the website walkthrough.',
  },
  {
    id: 'disorganization-tax-social',
    title: 'Stop rebuilding context every morning.',
    audience: 'Wedding planners losing time across spreadsheets, inboxes, and disconnected finance tools.',
    durationSeconds: 25,
    priority: 'phase-one',
    status: 'scripted',
    productionChannel: 'social',
    phaseOnePillar: 'Disorganization Tax',
    socialOutcome:
      'See what needs attention across active weddings before another sheet or inbox steals the day.',
    routePlan: [
      '/admin/planner',
      '/admin/communications/inbox',
      '/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel',
    ],
    captureCheckpoints: [
      {
        label: 'Disorganization morning view',
        route: '/admin/planner',
        action: 'Scan the two populated wedding cards and their attention signals.',
        visibleResult:
          'Morning View distinguishes two active weddings through current progress and next-action context.',
      },
      {
        label: 'Disorganization conversation queue',
        route: '/admin/communications/inbox',
        action: 'Open the seeded planner inbox and hold on the wedding-scoped conversation queue.',
        visibleResult:
          'Guest, couple, and support conversations appear in one planner-owned operational inbox.',
      },
      {
        label: 'Disorganization budget context',
        route: '/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel',
        action: 'Open the Sofia & Daniel budget and hold on category spend and remaining funds.',
        visibleResult:
          'The populated wedding budget keeps current spend and remaining funds visible in the same workspace.',
      },
    ],
    seedRequirements: [
      'Two populated active weddings with contrasting attention signals in Morning View.',
      'A seeded planner inbox and Sofia & Daniel budget with publicly safe fictional content.',
    ],
    script: [
      {
        timestamp: '0:00-0:07',
        action: 'Scan Morning View and pause on the contrasting wedding signals.',
        voiceover: 'Disorganization charges interest every morning you rebuild context from scratch.',
      },
      {
        timestamp: '0:07-0:14',
        action: 'Open the planner inbox and hold on the unified wedding conversation queue.',
        voiceover: 'Messages stay tied to the wedding work instead of disappearing across personal inboxes.',
      },
      {
        timestamp: '0:14-0:20',
        action: 'Open the wedding budget and hold on current category spend.',
        voiceover: 'The financial context is already there when the planner needs to act.',
      },
    ],
    recordingChecklist: [
      ...defaultChecklist,
      'Use read-only seeded states; do not send a message or change a budget item.',
      'Keep the full product window visible through every manual route change.',
    ],
    captureNotes:
      'Record a distinct 20-second product story plus the five-second social outro; the point is recovered context, not a feature montage.',
  },
  {
    id: 'couple-experience-boundaries-social',
    title: 'A clear couple experience. Planner-owned boundaries.',
    audience: 'Wedding planners who want clients informed without exposing internal operations.',
    durationSeconds: 20,
    priority: 'phase-one',
    status: 'scripted',
    productionChannel: 'social',
    phaseOnePillar: 'Couple Experience + Boundaries',
    socialOutcome:
      'Give couples guided forms and the payment context they need while planner operations stay private.',
    routePlan: [
      '/admin/forms/form_marketing_capture_couple_intake/edit',
      '/couple/dashboard',
    ],
    captureCheckpoints: [
      {
        label: 'Boundaries planner intake',
        route: '/admin/forms/form_marketing_capture_couple_intake/edit',
        action: 'Hold on the planner-controlled couple intake form and its structured questions.',
        visibleResult:
          'The planner owns the intake workflow and the information requested from the couple.',
      },
      {
        label: 'Boundaries couple form',
        route: '/couple/dashboard',
        action: 'Switch manually to the couple portal Forms view and inspect the assigned intake.',
        visibleResult:
          'The couple sees its assigned questionnaire and completion context without planner editing controls.',
      },
      {
        label: 'Boundaries couple payments',
        route: '/couple/dashboard',
        action: 'Open Payments and hold on the package and schedule without using payment controls.',
        visibleResult:
          'The couple sees shared payment context while planner finance operations remain private.',
      },
    ],
    seedRequirements: [
      'A planner-owned couple intake form assigned to Sofia & Daniel.',
      'A couple portal with populated Forms and Payments views and no planner-only controls.',
    ],
    script: [
      {
        timestamp: '0:00-0:05',
        action: 'Hold on the planner-controlled couple intake form.',
        voiceover: 'Clear boundaries start with a workflow the planner owns.',
      },
      {
        timestamp: '0:05-0:10',
        action: 'Switch manually to the assigned form in the couple portal.',
        voiceover: 'The couple gets a guided next step, not the planner’s internal controls.',
      },
      {
        timestamp: '0:10-0:15',
        action: 'Open the couple Payments view and hold on the shared schedule.',
        voiceover: 'The answers clients need stay available without another midnight text.',
      },
    ],
    recordingChecklist: [
      ...defaultChecklist,
      'Prepare the planner form and couple portal in separate tabs and switch manually.',
      'Do not submit the form, open transaction controls, or expose planner-only details.',
    ],
    captureNotes:
      'Record a distinct 15-second product story plus the five-second social outro; make the role boundary visually obvious.',
  },
  {
    id: 'built-for-planners-social',
    title: 'Wedding work deserves wedding-native systems.',
    audience: 'Professional wedding planners comparing wedding-specific operations with generic event software.',
    durationSeconds: 35,
    priority: 'phase-one',
    status: 'scripted',
    productionChannel: 'social',
    phaseOnePillar: 'Built for Planners',
    socialOutcome:
      'Run RSVP, seating, and vendor workflows generic event tools were never designed to understand.',
    routePlan: [
      '/admin/guests',
      '/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel',
      '/admin/vendors',
    ],
    captureCheckpoints: [
      {
        label: 'Planner-native guest context',
        route: '/admin/guests',
        action: 'Filter the seeded guest table to Declined and hold on RSVP, group, and plus-one context.',
        visibleResult:
          'The planner sees the declined slice without losing group, meal, and plus-one context.',
      },
      {
        label: 'Planner-native room plan',
        route: '/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel',
        action: 'Use the in-product Zoom out control to reach 70% and hold on the venue-aware room plan.',
        visibleResult:
          'The seating canvas shows the room outline, fixtures, tables, and existing assignments together.',
      },
      {
        label: 'Planner-native vendor records',
        route: '/admin/vendors',
        action: 'Open Planner Vendor Management and hold on private contacts, contracts, and payment status.',
        visibleResult:
          'The planner vendor workspace keeps wedding-business context private and operational.',
      },
    ],
    seedRequirements: [
      'Guests with realistic RSVP, group, meal, and plus-one states.',
      'A venue-aware seating plan plus populated private planner vendor records.',
    ],
    script: [
      {
        timestamp: '0:00-0:10',
        action: 'Filter Guest Management to Declined and hold on the preserved guest context.',
        voiceover: 'Generic event tools see names. Wedding planners need RSVP, household, meal, and plus-one context.',
      },
      {
        timestamp: '0:10-0:20',
        action: 'Open the venue-aware seating plan and hold on fixtures, tables, and assignments.',
        voiceover: 'Seating starts with the actual room and the people already connected to it.',
      },
      {
        timestamp: '0:20-0:30',
        action: 'Open Planner Vendor Management and hold on the private operational record.',
        voiceover: 'Vendor relationships, contracts, and status stay inside the planner’s operating system.',
      },
    ],
    recordingChecklist: [
      ...defaultChecklist,
      'Keep guest cards collapsed and avoid guest actions, edits, messages, signatures, or payments.',
      'Use only the in-product seating zoom control and do not move guests, tables, or fixtures.',
    ],
    captureNotes:
      'Record a distinct 30-second product story plus the five-second social outro; show wedding-native depth without turning it into a generic feature list.',
  },
] as const satisfies readonly PhaseOneSocialVideo[];

export const PHASE_ONE_SOCIAL_VIDEO_STORIES: readonly PhaseOneSocialVideo[] =
  PHASE_ONE_SOCIAL_VIDEO_STORY_DRAFTS.map(applyPhaseOneSocialVideoPublicationApproval);

export const DEMO_VIDEO_PLAYLIST: readonly DemoVideo[] = [
  HERO_DEMO_VIDEO,
  ...FEATURE_DEMO_VIDEO_DRAFTS.map(applyDemoVideoPublicationApproval),
];

export const DEMO_VIDEO_PRODUCTION_CATALOG: readonly DemoVideo[] = [
  ...DEMO_VIDEO_PLAYLIST,
  ...PHASE_ONE_SOCIAL_VIDEO_STORIES,
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
