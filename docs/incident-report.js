const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  Header, Footer, PageNumber, PageBreak, LevelFormat
} = require('docx');

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

function headerCell(text, width) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: "1a1a2e", type: ShadingType.CLEAR },
    margins: cellMargins,
    verticalAlign: "center",
    children: [new Paragraph({ children: [new TextRun({ text, bold: true, color: "FFFFFF", font: "Arial", size: 18 })] })]
  });
}

function cell(text, width, opts = {}) {
  const fill = opts.fill || undefined;
  const bold = opts.bold || false;
  const color = opts.color || "1a1a2e";
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: fill ? { fill, type: ShadingType.CLEAR } : undefined,
    margins: cellMargins,
    children: [new Paragraph({ children: [new TextRun({ text, font: "Arial", size: 18, bold, color })] })]
  });
}

function statusCell(status, width) {
  const colorMap = {
    "PASS": { fill: "d4edda", color: "155724" },
    "FAIL": { fill: "f8d7da", color: "721c24" },
    "WARN": { fill: "fff3cd", color: "856404" },
    "N/A":  { fill: "e2e3e5", color: "383d41" },
  };
  const c = colorMap[status] || colorMap["N/A"];
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: c.fill, type: ShadingType.CLEAR },
    margins: cellMargins,
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: status, font: "Arial", size: 18, bold: true, color: c.color })] })]
  });
}

// Issue verification data
const issues = [
  {
    id: "1", title: "Archival Query Missed Checkout-Expired & Suspended Subscriptions",
    severity: "CRITICAL", file: "billing_jobs.py", status: "PASS",
    findings: [
      "The $or query in process_subscription_archival now includes 4 clauses: cancelled (via cancelled_at), trial-expired (via trial_expired_at), checkout-expired (via expired_reason + updated_at), and suspended (via updated_at).",
      "The orphaned cleanup has_subscription check now queries without status filter \u2014 ANY subscription record (active, trial, cancelled, expired, suspended) prevents deletion.",
      "Invitation-sourced records (source: \"invitation\") are explicitly skipped in Part 1 of cleanup.",
      "Part 2 handles invitation cleanup separately via user_invitations collection."
    ]
  },
  {
    id: "2", title: "User Status Diverges When Checkout Expires",
    severity: "HIGH", file: "stripe_service.py", status: "PASS",
    findings: [
      "_handle_checkout_expired now updates users.subscription_status to \"expired\" when user status is \"pending_payment\" or \"pending\".",
      "checkout_expired_at timestamp is set on the user document.",
      "Guard clause (status in pending_payment/pending) prevents force-expiring active users \u2014 matches security check A2."
    ]
  },
  {
    id: "3", title: "Frontend-Backend Parameter Mismatch on Metrics History",
    severity: "CRITICAL", file: "admin_platform_metrics.py", status: "PASS",
    findings: [
      "get_metrics_history now declares start_date: Optional[str] = Query(None) alongside days: int = Query(7).",
      "When start_date is provided, it\u2019s parsed via datetime.fromisoformat() with Z-replacement. On ValueError, falls back to days parameter \u2014 no 500 error.",
      "When start_date is absent, days parameter is used as before (backward compatible)."
    ]
  },
  {
    id: "4", title: "Pydantic Schema Models Missing Database Fields",
    severity: "MEDIUM", file: "subscription.py", status: "PASS",
    findings: [
      "UserSubscriptionModel now declares all 7 missing fields: stripe_status (Optional[str]), trial_start_date (Optional[datetime]), trial_will_end_notified_at (Optional[datetime]), last_payment_date (Optional[datetime]), last_payment_attempt (Optional[datetime]), stripe_checkout_completed_at (Optional[datetime]), expired_reason (Optional[str]).",
      "SubscriptionPlanModel now declares: stripe_product_id (Optional[str]), stripe_price_id_monthly (Optional[str]), stripe_price_id_yearly (Optional[str]).",
      "All 10 fields have proper type annotations and Field descriptions."
    ]
  },
  {
    id: "5", title: "Pending Signup TTL Index Not Created at Startup",
    severity: "MEDIUM", file: "database_indexes.py", status: "PASS",
    findings: [
      "create_user_indexes() now creates idx_pending_payment_ttl with expireAfterSeconds=0 and partialFilterExpression: {subscription_status: \"pending_payment\", pending_expires_at: {$exists: true}}.",
      "create_user_indexes() is called from create_all_indexes() which runs at startup.",
      "The partialFilterExpression ensures only pending_payment users with pending_expires_at are affected (security check A7)."
    ]
  },
  {
    id: "6", title: "Invitation TTL Deleted Accepted Invitations",
    severity: "CRITICAL", file: "database_indexes.py + user_management_service.py", status: "PASS",
    findings: [
      "idx_invitation_expires_ttl now has partialFilterExpression: {status: \"pending\"} \u2014 only pending invitations are eligible for TTL deletion (security check A6).",
      "In complete_account_setup(), after marking invitation as \"completed\", expires_at is $unset. This is a belt-and-suspenders approach: even without the partial filter, the field removal would prevent TTL deletion.",
      "7-day grace period (expireAfterSeconds = 7 * 86400) gives pending invitations 14 days total before cleanup."
    ]
  },
  {
    id: "7", title: "Duplicate Stripe Customer on Invitation Acceptance",
    severity: "CRITICAL", file: "user_management_service.py", status: "PASS",
    findings: [
      "In invite_user(), the stripe_customers record is created with user_id: \"invitation_{token}\" and source: \"invitation\".",
      "In complete_account_setup(), after creating the user, stripe_customers is updated: the record matching stripe_customer_id gets user_id replaced with the real user_id.",
      "This happens BEFORE assign_subscription() is called, so get_or_create_customer() will find the existing record and NOT create a duplicate.",
      "The update uses stripe_customer_id as the query key (not user_id), ensuring it finds the invitation record regardless of the placeholder."
    ]
  },
  {
    id: "8", title: "Orphaned Cleanup Processes Invitation Records Incorrectly",
    severity: "MEDIUM", file: "billing_jobs.py", status: "PASS",
    findings: [
      "Part 1 of process_orphaned_customer_cleanup now checks record.get(\"source\") == \"invitation\" and skips (continues) those records.",
      "This prevents ObjectId() from throwing on \"invitation_{token}\" user_id values.",
      "Part 2 handles invitation-sourced Stripe customers via the user_invitations collection, checking if the customer was adopted (exists in stripe_customers with a real mapping) before deleting."
    ]
  },
  {
    id: "9", title: "Expired Invitations Metric Overcounts",
    severity: "MEDIUM", file: "admin_platform_metrics.py", status: "PASS",
    findings: [
      "The expired_invitations metric now queries with status: \"pending\" in addition to expires_at: {$lt: now}.",
      "This correctly excludes accepted/completed invitations from the expired count.",
      "Example: 100 invitations, 80 accepted (status: \"completed\") \u2192 only the 20 still-pending past-expiry invitations count."
    ]
  }
];

// Security checklist data
const securityChecks = [
  { id: "A1", desc: "Webhook validates stripe-signature header", status: "PASS", note: "stripe.Webhook.construct_event() with webhook_secret verifies signature; SignatureVerificationError returns 400." },
  { id: "A2", desc: "Expired update gated behind pending statuses", status: "PASS", note: "Guard: user.subscription_status in (\"pending_payment\", \"pending\") before setting expired." },
  { id: "A3", desc: "Archive endpoint requires require_root_admin", status: "PASS", note: "Depends(require_root_admin) on /billing/archive-inactive-subscriptions." },
  { id: "A4", desc: "Cleanup endpoint requires require_root_admin", status: "PASS", note: "Depends(require_root_admin) on /billing/cleanup-orphaned-customers." },
  { id: "A5", desc: "start_date parsed safely, no injection", status: "PASS", note: "datetime.fromisoformat() with ValueError fallback to days param." },
  { id: "A6", desc: "Invitation TTL: pending only", status: "PASS", note: "partialFilterExpression: {status: \"pending\"} on idx_invitation_expires_ttl." },
  { id: "A7", desc: "Pending payment TTL: pending_payment only", status: "PASS", note: "partialFilterExpression: {subscription_status: \"pending_payment\"} on idx_pending_payment_ttl." },
  { id: "A8", desc: "Archived sub TTL: archived_at exists only", status: "PASS", note: "partialFilterExpression: {archived_at: {$exists: true}} on idx_subscription_archived_ttl." },
  { id: "A9", desc: "Abandoned checkout TTL: expired + checkout reason only", status: "PASS", note: "partialFilterExpression: {status: \"expired\", expired_reason: \"checkout_session_expired\"} on idx_abandoned_checkout_ttl." },
];

// Remaining concerns
const concerns = [
  {
    id: "PRE-1", severity: "HIGH", title: "Double Stripe Subscription (Pre-existing)",
    desc: "complete_account_setup() creates a Stripe subscription at line ~593, then assign_subscription() creates another on the same customer. This predates this work and needs a separate ticket. Risk: double-billing on invited trial users."
  },
  {
    id: "NEW-1", severity: "LOW", title: "complete_account_setup Stripe customer mapping uses email key",
    desc: "At line 621, the stripe_customers update_one uses {email: invitation[\"email\"]} as the query, while invite_user stores the record with {stripe_customer_id: ...}. If a user has multiple invitation attempts, the email-based query could match a stale record. The stripe_customer_id-based update at line 675 is the correct one and runs afterward, but there's a brief window where the mapping could be inconsistent. Consider unifying both updates to use stripe_customer_id as the query key."
  },
];

// Build document
const children = [];

// Title
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 100 },
  children: [new TextRun({ text: "INCIDENT RESPONSE REPORT", font: "Arial", size: 36, bold: true, color: "1a1a2e" })]
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 100 },
  children: [new TextRun({ text: "TheSpecialWedding.io \u2014 Billing & Subscription Subsystem", font: "Arial", size: 24, color: "555555" })]
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 300 },
  children: [new TextRun({ text: "Date: February 28, 2026  |  Branch: feature-twilio-otp-improvement-final-submitted", font: "Arial", size: 20, color: "777777" })]
}));

// Executive Summary
children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 200 }, children: [new TextRun({ text: "1. Executive Summary", font: "Arial", size: 32, bold: true })] }));

children.push(new Paragraph({ spacing: { after: 150 }, children: [new TextRun({ text: "This report documents the code-level verification of 9 bug fixes across the billing, subscription, and user management subsystems of TheSpecialWedding.io SaaS platform. The fixes address issues ranging from data loss (silent subscription accumulation, audit trail deletion) to billing integrity (duplicate Stripe customers, orphaned records) and admin dashboard accuracy (metrics parameter mismatch, overcounting).", font: "Arial", size: 20 })] }));

children.push(new Paragraph({ spacing: { after: 150 }, children: [new TextRun({ text: "All 9 fixes have been verified as correctly implemented in the codebase. All 9 security checklist items (A1\u2013A9) pass. One pre-existing issue (double Stripe subscription creation) was identified as out-of-scope and flagged for a separate ticket.", font: "Arial", size: 20 })] }));

// Severity overview table
children.push(new Paragraph({ spacing: { before: 200, after: 100 }, children: [new TextRun({ text: "Severity Distribution:", font: "Arial", size: 20, bold: true })] }));

const sevCols = [2340, 2340, 2340, 2340];
children.push(new Table({
  width: { size: 100, type: WidthType.PERCENTAGE },
  columnWidths: sevCols,
  rows: [
    new TableRow({ children: [headerCell("CRITICAL", sevCols[0]), headerCell("HIGH", sevCols[1]), headerCell("MEDIUM", sevCols[2]), headerCell("Total", sevCols[3])] }),
    new TableRow({ children: [
      cell("4 issues", sevCols[0], { fill: "f8d7da", color: "721c24", bold: true }),
      cell("1 issue", sevCols[1], { fill: "fff3cd", color: "856404", bold: true }),
      cell("4 issues", sevCols[2], { fill: "d4edda", color: "155724", bold: true }),
      cell("9 issues", sevCols[3], { bold: true }),
    ] }),
  ]
}));

children.push(new Paragraph({ children: [new PageBreak()] }));

// Issue Verification
children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 200 }, children: [new TextRun({ text: "2. Issue Verification Details", font: "Arial", size: 32, bold: true })] }));

for (const issue of issues) {
  // Issue header
  const sevColor = issue.severity === "CRITICAL" ? "dc3545" : issue.severity === "HIGH" ? "fd7e14" : "28a745";
  children.push(new Paragraph({
    spacing: { before: 250, after: 80 },
    children: [
      new TextRun({ text: `Issue #${issue.id}: `, font: "Arial", size: 22, bold: true, color: "1a1a2e" }),
      new TextRun({ text: issue.title, font: "Arial", size: 22, bold: true, color: "1a1a2e" }),
    ]
  }));

  // Metadata line
  children.push(new Paragraph({
    spacing: { after: 100 },
    children: [
      new TextRun({ text: `Severity: `, font: "Arial", size: 18, color: "555555" }),
      new TextRun({ text: issue.severity, font: "Arial", size: 18, bold: true, color: sevColor }),
      new TextRun({ text: `  |  File: ${issue.file}  |  Verdict: `, font: "Arial", size: 18, color: "555555" }),
      new TextRun({ text: issue.status, font: "Arial", size: 18, bold: true, color: "155724" }),
    ]
  }));

  // Findings
  for (const finding of issue.findings) {
    children.push(new Paragraph({
      spacing: { after: 60 },
      indent: { left: 360 },
      children: [
        new TextRun({ text: "\u2022 ", font: "Arial", size: 18, color: "555555" }),
        new TextRun({ text: finding, font: "Arial", size: 18, color: "333333" }),
      ]
    }));
  }
}

children.push(new Paragraph({ children: [new PageBreak()] }));

// Security Checklist
children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 200 }, children: [new TextRun({ text: "3. Security Verification (A1\u2013A9)", font: "Arial", size: 32, bold: true })] }));

const secCols = [800, 3500, 900, 4160];
const secRows = [
  new TableRow({ children: [headerCell("ID", secCols[0]), headerCell("Check", secCols[1]), headerCell("Status", secCols[2]), headerCell("Evidence", secCols[3])] })
];
for (const check of securityChecks) {
  secRows.push(new TableRow({ children: [
    cell(check.id, secCols[0], { bold: true }),
    cell(check.desc, secCols[1]),
    statusCell(check.status, secCols[2]),
    cell(check.note, secCols[3]),
  ] }));
}
children.push(new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, columnWidths: secCols, rows: secRows }));

children.push(new Paragraph({ children: [new PageBreak()] }));

// Remaining Concerns
children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 200 }, children: [new TextRun({ text: "4. Remaining Concerns & Recommendations", font: "Arial", size: 32, bold: true })] }));

for (const concern of concerns) {
  const cColor = concern.severity === "HIGH" ? "fd7e14" : "17a2b8";
  children.push(new Paragraph({
    spacing: { before: 200, after: 80 },
    children: [
      new TextRun({ text: `[${concern.severity}] ${concern.id}: `, font: "Arial", size: 20, bold: true, color: cColor }),
      new TextRun({ text: concern.title, font: "Arial", size: 20, bold: true, color: "1a1a2e" }),
    ]
  }));
  children.push(new Paragraph({
    spacing: { after: 100 },
    indent: { left: 360 },
    children: [new TextRun({ text: concern.desc, font: "Arial", size: 18, color: "333333" })]
  }));
}

// QA Readiness
children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 200 }, children: [new TextRun({ text: "5. QA Readiness Assessment", font: "Arial", size: 32, bold: true })] }));

children.push(new Paragraph({ spacing: { after: 150 }, children: [new TextRun({ text: "Based on the code review, all 9 fixes are correctly implemented. The codebase is ready for integration testing against the QA verification checklist (sections B through E in the original spec). Key areas requiring manual/integration testing:", font: "Arial", size: 20 })] }));

const qaItems = [
  "End-to-end invitation flow: invite \u2192 accept \u2192 trial \u2192 convert \u2192 cancel \u2192 archive (D1)",
  "Abandoned checkout flow: invite \u2192 accept \u2192 abandon \u2192 expired status sync \u2192 archival (D2)",
  "Expired invitation TTL: verify pending invitations are deleted after 14 days, completed ones persist (D3)",
  "Admin dashboard time range selection: verify network requests include start_date parameter (C1\u2013C3)",
  "Stripe webhook integration: simulate checkout.session.expired and verify both collections update (B2)",
  "Orphaned cleanup safety: run cleanup job and verify invitation records are not deleted prematurely (B8)",
  "Pre-existing double subscription: file separate ticket for complete_account_setup + assign_subscription overlap",
];

for (const item of qaItems) {
  children.push(new Paragraph({
    spacing: { after: 60 },
    indent: { left: 360 },
    children: [
      new TextRun({ text: "\u2022 ", font: "Arial", size: 18, color: "555555" }),
      new TextRun({ text: item, font: "Arial", size: 18, color: "333333" }),
    ]
  }));
}

// Conclusion
children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 200 }, children: [new TextRun({ text: "6. Conclusion", font: "Arial", size: 32, bold: true })] }));

children.push(new Paragraph({ spacing: { after: 150 }, children: [new TextRun({ text: "The 9 fixes address critical gaps in the billing lifecycle that would have caused data accumulation, audit trail loss, duplicate billing, and misleading admin metrics. The code changes are well-structured with appropriate guard clauses, TTL partial filters, and belt-and-suspenders safety. The platform is ready to proceed to integration testing ahead of the RSVP launch on thespecialwedding.io.", font: "Arial", size: 20 })] }));

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: "1a1a2e" },
        paragraph: { spacing: { before: 300, after: 200 }, outlineLevel: 0 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1200, right: 1200, bottom: 1200, left: 1200 }
      }
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "TheSpecialWedding.io \u2014 Incident Report", font: "Arial", size: 16, color: "999999", italics: true })]
        })]
      })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "Page ", font: "Arial", size: 16, color: "999999" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: "999999" }),
          ]
        })]
      })
    },
    children
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/sessions/lucid-loving-gauss/mnt/WeddingWebApp/incident-report.docx", buffer);
  console.log("Report generated successfully");
});
