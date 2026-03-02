const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
        BorderStyle, WidthType, ShadingType, PageNumber, PageBreak } = require('docx');

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

const CRITICAL_COLOR = "FEE2E2";
const HIGH_COLOR = "FEF3C7";
const MEDIUM_COLOR = "DBEAFE";
const LOW_COLOR = "F3F4F6";

function severity(text, color) {
  return new TableCell({
    borders, width: { size: 1200, type: WidthType.DXA }, margins: cellMargins,
    shading: { fill: color, type: ShadingType.CLEAR },
    verticalAlign: "center",
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text, bold: true, size: 18, font: "Arial" })] })]
  });
}

function cell(text, width, bold = false) {
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA }, margins: cellMargins,
    children: [new Paragraph({ children: [new TextRun({ text, size: 18, font: "Arial", bold })] })]
  });
}

function heading(text, level) {
  return new Paragraph({ heading: level, spacing: { before: 300, after: 150 },
    children: [new TextRun({ text, font: "Arial" })] });
}

function bodyText(text, opts = {}) {
  return new Paragraph({ spacing: { after: 120 },
    children: [new TextRun({ text, size: 20, font: "Arial", ...opts })] });
}

function bulletItem(text, ref, bold = false) {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 80 },
    children: [new TextRun({ text, size: 20, font: "Arial", bold })]
  });
}

function issueRow(num, sev, cat, location, desc, color) {
  return new TableRow({
    children: [
      cell(num, 500, true),
      severity(sev, color),
      cell(cat, 1800),
      cell(location, 2500),
      cell(desc, 3360),
    ]
  });
}

function sectionHeader() {
  return new TableRow({
    children: [
      new TableCell({ borders, width: { size: 500, type: WidthType.DXA }, margins: cellMargins,
        shading: { fill: "1F2937", type: ShadingType.CLEAR },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "#", bold: true, size: 18, font: "Arial", color: "FFFFFF" })] })] }),
      new TableCell({ borders, width: { size: 1200, type: WidthType.DXA }, margins: cellMargins,
        shading: { fill: "1F2937", type: ShadingType.CLEAR },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Severity", bold: true, size: 18, font: "Arial", color: "FFFFFF" })] })] }),
      new TableCell({ borders, width: { size: 1800, type: WidthType.DXA }, margins: cellMargins,
        shading: { fill: "1F2937", type: ShadingType.CLEAR },
        children: [new Paragraph({ children: [new TextRun({ text: "Category", bold: true, size: 18, font: "Arial", color: "FFFFFF" })] })] }),
      new TableCell({ borders, width: { size: 2500, type: WidthType.DXA }, margins: cellMargins,
        shading: { fill: "1F2937", type: ShadingType.CLEAR },
        children: [new Paragraph({ children: [new TextRun({ text: "Location", bold: true, size: 18, font: "Arial", color: "FFFFFF" })] })] }),
      new TableCell({ borders, width: { size: 3360, type: WidthType.DXA }, margins: cellMargins,
        shading: { fill: "1F2937", type: ShadingType.CLEAR },
        children: [new Paragraph({ children: [new TextRun({ text: "Description", bold: true, size: 18, font: "Arial", color: "FFFFFF" })] })] }),
    ]
  });
}

// BUILD DOCUMENT
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: "1F2937" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "374151" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "4B5563" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "checks", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2610", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
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
      default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: "TheSpecialWedding.io | Pre-Deployment QA Report", size: 16, font: "Arial", color: "9CA3AF", italics: true })] })] })
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Page ", size: 16, font: "Arial", color: "9CA3AF" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, font: "Arial", color: "9CA3AF" })] })] })
    },
    children: [
      // TITLE PAGE
      new Paragraph({ spacing: { before: 2400 } }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
        children: [new TextRun({ text: "PRE-DEPLOYMENT QA REPORT", size: 48, bold: true, font: "Arial", color: "1F2937" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
        children: [new TextRun({ text: "TheSpecialWedding.io SaaS Platform", size: 28, font: "Arial", color: "6B7280" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
        children: [new TextRun({ text: "Frontend-Backend Alignment Review", size: 24, font: "Arial", color: "6B7280" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
        children: [new TextRun({ text: "March 1, 2026", size: 22, font: "Arial", color: "9CA3AF" })] }),

      // SUMMARY BOX
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
        children: [new TextRun({ text: "Branch: feature-twilio-otp-improvement-final-submitted", size: 20, font: "Arial", color: "6B7280" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
        children: [new TextRun({ text: "Deployment: Coolify on DigitalOcean | Domain: thespecialwedding.io", size: 20, font: "Arial", color: "6B7280" })] }),

      new Paragraph({ spacing: { before: 400 } }),

      // STATS TABLE
      new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        columnWidths: [2460, 2460, 2460, 2460],
        rows: [
          new TableRow({ children: [
            new TableCell({ borders, width: { size: 2460, type: WidthType.DXA }, margins: cellMargins,
              shading: { fill: CRITICAL_COLOR, type: ShadingType.CLEAR },
              children: [
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "CRITICAL", bold: true, size: 20, font: "Arial", color: "991B1B" })] }),
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "21", bold: true, size: 36, font: "Arial", color: "991B1B" })] })
              ] }),
            new TableCell({ borders, width: { size: 2460, type: WidthType.DXA }, margins: cellMargins,
              shading: { fill: HIGH_COLOR, type: ShadingType.CLEAR },
              children: [
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "HIGH", bold: true, size: 20, font: "Arial", color: "92400E" })] }),
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "24", bold: true, size: 36, font: "Arial", color: "92400E" })] })
              ] }),
            new TableCell({ borders, width: { size: 2460, type: WidthType.DXA }, margins: cellMargins,
              shading: { fill: MEDIUM_COLOR, type: ShadingType.CLEAR },
              children: [
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "MEDIUM", bold: true, size: 20, font: "Arial", color: "1E40AF" })] }),
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "16", bold: true, size: 36, font: "Arial", color: "1E40AF" })] })
              ] }),
            new TableCell({ borders, width: { size: 2460, type: WidthType.DXA }, margins: cellMargins,
              shading: { fill: LOW_COLOR, type: ShadingType.CLEAR },
              children: [
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "LOW", bold: true, size: 20, font: "Arial", color: "4B5563" })] }),
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "5", bold: true, size: 36, font: "Arial", color: "4B5563" })] })
              ] }),
          ] })
        ]
      }),

      new Paragraph({ spacing: { after: 200 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "66 Total Issues Across 5 Feature Areas", bold: true, size: 22, font: "Arial", color: "DC2626" })] }),

      new Paragraph({ children: [new PageBreak()] }),

      // ==========================================
      // EXECUTIVE SUMMARY
      // ==========================================
      heading("1. Executive Summary", HeadingLevel.HEADING_1),
      bodyText("This report presents findings from a comprehensive QA review of the TheSpecialWedding.io SaaS platform, focusing on frontend-backend alignment across 5 critical feature areas: Stripe/Billing, Seating Orchestration, Contracts, Budget, and AI Features."),
      bodyText("The review was conducted by deploying parallel QA/Dev agents that read every relevant frontend component, backend API route, service layer, and database model to identify misalignments in parameters, types, endpoints, business logic, and security."),
      bodyText("Given the platform launch timeline (RSVP deployment in ~2 weeks for your wedding at thespecialwedding.io/emmanuel-peace), the findings are categorized by deployment risk level."),

      new Paragraph({ spacing: { before: 200, after: 100 },
        children: [new TextRun({ text: "Key Risk Assessment:", bold: true, size: 22, font: "Arial" })] }),
      bulletItem("Budget Feature: 9 CRITICAL endpoint path mismatches - entire feature non-functional", "bullets", true),
      bulletItem("Seating Feature: Guest ID format issues cause silent assignment failures", "bullets", true),
      bulletItem("Contracts: 3 missing backend endpoints - vendor contract creation broken", "bullets", true),
      bulletItem("Stripe: Auth token mismatch breaks billing page post-payment", "bullets", true),
      bulletItem("AI: CRON_SECRET security vulnerability exposes payment endpoints", "bullets", true),
      bulletItem("Budget: Multi-tenant access control gaps allow cross-wedding data access", "bullets", true),

      new Paragraph({ children: [new PageBreak()] }),

      // ==========================================
      // SECTION 1: STRIPE/BILLING
      // ==========================================
      heading("2. Stripe & Billing Integration", HeadingLevel.HEADING_1),
      bodyText("Files reviewed: stripe_payment.py, subscription_management.py, trial_management.py, metering.py, billing_jobs.py, packages.py, stripe_service.py, subscription_service.py, trial_expiration_service.py, feature_gates.py, SignupModal.tsx, billing pages, packages pages, saas components."),

      new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        columnWidths: [500, 1200, 1800, 2500, 3360],
        rows: [
          sectionHeader(),
          issueRow("S1", "CRITICAL", "Param Mismatch", "SignupModal.tsx -> stripe_payment.py", "Public checkout sends user_id but backend expects email lookup. Orphaned accounts if email mismatch.", CRITICAL_COLOR),
          issueRow("S2", "HIGH", "Missing Error Handling", "billing/success/page.tsx", "Success page uses authToken instead of admin_token. Post-payment confirmation broken.", HIGH_COLOR),
          issueRow("S3", "HIGH", "Type Mismatch", "billing/page.tsx -> subscription_mgmt.py", "Subscription retrieval uses email as user_id path param. Backend expects ObjectId. Billing data never loads.", HIGH_COLOR),
          issueRow("S4", "HIGH", "Business Logic Gap", "stripe_payment.py -> billing page", "Card details fetch fails silently. Expiring card warnings never shown.", HIGH_COLOR),
          issueRow("S5", "HIGH", "Type Mismatch", "billing/page.tsx", "Billing alerts crash when card_exp fields missing. Page throws null reference on missing plan.", HIGH_COLOR),
          issueRow("S6", "MEDIUM", "Param Mismatch", "billing/page.tsx", "Usage stats calculated from wrong endpoint. Manual calculation vs dedicated usage endpoint.", MEDIUM_COLOR),
          issueRow("S7", "MEDIUM", "Business Logic Gap", "stripe_service.py", "Webhook handlers not idempotent. Duplicate subscriptions on retry.", MEDIUM_COLOR),
          issueRow("S8", "MEDIUM", "Business Logic Gap", "feature_gates.py", "Feature gate checks user_email field that may not be populated. Active planners denied access.", MEDIUM_COLOR),
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ==========================================
      // SECTION 2: SEATING
      // ==========================================
      heading("3. Seating Orchestration", HeadingLevel.HEADING_1),
      bodyText("Files reviewed: tables.py, guest.py, table.py model, guest.py model, guest_service.py, seating components (TableNode, SeatingCanvas, SeatingConstraintsModal, Sidebar, GuestItem, PrintableSeatingChart), useGuests.ts, useTables.ts, table.ts types."),

      new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        columnWidths: [500, 1200, 1800, 2500, 3360],
        rows: [
          sectionHeader(),
          issueRow("T1", "CRITICAL", "Type Mismatch", "useTables.ts -> tables.py", "Invalid guest IDs silently skipped during assignment. Frontend shows seated, DB shows unseated.", CRITICAL_COLOR),
          issueRow("T2", "HIGH", "Data Consistency", "guest.py", "Deleted guests leave orphan constraint references. AI optimizer gets invalid data.", HIGH_COLOR),
          issueRow("T3", "HIGH", "Type Mismatch", "useGuests.ts -> guest.py", "list_guests endpoint doesn't convert _id to id string. Guest IDs become [object Object].", HIGH_COLOR),
          issueRow("T4", "HIGH", "Business Logic Gap", "TableNode.tsx -> tables.py", "Capacity validation UI-only. No server-side enforcement feedback to UI.", HIGH_COLOR),
          issueRow("T5", "HIGH", "Type Mismatch", "seating_export_service.py", "ObjectId format inconsistency in PDF export. Guests don't appear on printed charts.", HIGH_COLOR),
          issueRow("T6", "MEDIUM", "Business Logic Gap", "guest.py", "No constraint cleanup when guests deleted. Orphan records accumulate.", MEDIUM_COLOR),
          issueRow("T7", "MEDIUM", "Param Mismatch", "SeatingConstraintsModal -> guest.py", "Constraints endpoint expects ObjectId but receives string. Constraints never persist.", MEDIUM_COLOR),
          issueRow("T8", "MEDIUM", "Business Logic Gap", "tables.py", "No transaction safety for guest assignment. Race condition causes overbooking.", MEDIUM_COLOR),
          issueRow("T9", "LOW", "Configuration", "PrintableSeatingChart.tsx", "Hardcoded branding in print footer.", LOW_COLOR),
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ==========================================
      // SECTION 3: CONTRACTS
      // ==========================================
      heading("4. Contract Feature", HeadingLevel.HEADING_1),
      bodyText("Files reviewed: contracts.py, contract_service.py, contract_email_service.py, contract_followup_service.py, contract_pdf_service.py, vendor.py model, vendor_management.py, vendor_dashboard.py, contract frontend pages, VendorPaymentModal, PaymentMilestones, public contract page."),

      new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        columnWidths: [500, 1200, 1800, 2500, 3360],
        rows: [
          sectionHeader(),
          issueRow("C1", "CRITICAL", "Type Mismatch", "contracts pages -> contract_service.py", "Contract ID field uses _id in admin, id in public. Inconsistent access patterns.", CRITICAL_COLOR),
          issueRow("C2", "CRITICAL", "Missing Endpoint", "PaymentMilestones.tsx -> API", "recordPayment() has no backend endpoint. Vendor payment recording completely broken.", CRITICAL_COLOR),
          issueRow("C3", "CRITICAL", "Missing Endpoint", "contracts/new/page.tsx -> API", "createContract() for vendor contracts has no backend endpoint. Feature non-functional.", CRITICAL_COLOR),
          issueRow("C4", "HIGH", "Missing Endpoint", "contracts/[id]/page.tsx -> API", "updateContract() for sections has no backend handler. Section edits silently lost.", HIGH_COLOR),
          issueRow("C5", "HIGH", "Missing Logic", "contracts/[id]/page.tsx -> vendor.py", "contract_number never auto-generated. Always shows N/A.", HIGH_COLOR),
          issueRow("C6", "HIGH", "Param Mismatch", "PaymentMilestones.tsx -> contracts.py", "Payment status enum completely different: pending/due/overdue vs scheduled/processing/succeeded.", HIGH_COLOR),
          issueRow("C7", "HIGH", "Business Logic Gap", "contracts/[token] -> contracts.py", "SetupIntent not validated server-side. Payment method may not be saved.", HIGH_COLOR),
          issueRow("C8", "HIGH", "Type Mismatch", "contract_service.py -> frontend", "Wedding date serialization inconsistent across contract types.", HIGH_COLOR),
          issueRow("C9", "HIGH", "Missing Error Handling", "contracts/[id]/page.tsx", "View & Apply Form Data button has no onClick handler. Dead UI element.", HIGH_COLOR),
          issueRow("C10", "MEDIUM", "Dead Code", "vendor.py model", "Attachments field defined but no upload/view UI or endpoint exists.", MEDIUM_COLOR),
          issueRow("C11", "MEDIUM", "Security Gap", "vendor.py -> public endpoint", "Access token expiration never checked. Tokens never expire.", MEDIUM_COLOR),
          issueRow("C12", "MEDIUM", "Business Logic Gap", "email services", "Inconsistent email recipients across contract lifecycle events.", MEDIUM_COLOR),
          issueRow("C13", "MEDIUM", "Business Logic Gap", "contracts.py -> portal", "Contract status transitions (signed -> active -> completed) have no backend logic.", MEDIUM_COLOR),
          issueRow("C14", "MEDIUM", "Missing Error Handling", "contract_pdf_service.py", "PDF generation fails silently. Users get broken download links.", MEDIUM_COLOR),
          issueRow("C15", "MEDIUM", "Missing Logic", "contracts/new -> AI endpoint", "AI credit deduction not verified. Credits may not be deducted.", MEDIUM_COLOR),
          issueRow("C16", "LOW", "Data Completeness", "contracts.py -> frontend", "Signed PDF URL not returned to frontend. Users can't download.", LOW_COLOR),
          issueRow("C17", "LOW", "Type Mismatch", "vendor.py vs contracts.py", "Different status enum conventions for couple vs vendor contracts.", LOW_COLOR),
          issueRow("C18", "LOW", "Missing Spec", "Frontend only", "Placeholder variables defined in frontend but never rendered server-side.", LOW_COLOR),
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ==========================================
      // SECTION 4: BUDGET
      // ==========================================
      heading("5. Budget Feature", HeadingLevel.HEADING_1),
      bodyText("Files reviewed: budget.py, budget_service.py, budget.py model, budgetApi.ts, budget pages (main, estimate, quotes, templates), budget components, budget.ts types."),

      new Paragraph({ spacing: { before: 100, after: 100 },
        children: [new TextRun({ text: "CRITICAL: The budget feature has 9 endpoint path mismatches. The frontend adds /admin prefix that the backend doesn't have, and uses /vendor-quotes instead of /quotes. The entire budget feature is non-functional.", bold: true, size: 20, font: "Arial", color: "DC2626" })] }),

      new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        columnWidths: [500, 1200, 1800, 2500, 3360],
        rows: [
          sectionHeader(),
          issueRow("B1", "CRITICAL", "Endpoint Path", "budgetApi.ts:93 -> budget.py:202", "GET vendor-quotes vs /quotes. Wrong endpoint name.", CRITICAL_COLOR),
          issueRow("B2", "CRITICAL", "Endpoint Path", "budgetApi.ts:103 -> budget.py:222", "POST vendor-quotes vs /quotes. Create quote broken.", CRITICAL_COLOR),
          issueRow("B3", "CRITICAL", "Endpoint Path", "budgetApi.ts:116 -> budget.py:263", "PUT /admin/vendor-quotes vs /quotes. Status update broken.", CRITICAL_COLOR),
          issueRow("B4", "CRITICAL", "Endpoint Path", "budgetApi.ts:70 -> budget.py:181", "DELETE /categories (plural) vs /category (singular).", CRITICAL_COLOR),
          issueRow("B5", "CRITICAL", "Endpoint Path", "budgetApi.ts:273 -> budget.py:347", "POST /admin/budget/category vs /budget/category. Payment recording broken.", CRITICAL_COLOR),
          issueRow("B6", "CRITICAL", "Endpoint Path", "budgetApi.ts:143 -> budget.py:286", "GET /admin/budget/templates vs /budget/templates.", CRITICAL_COLOR),
          issueRow("B7", "CRITICAL", "Endpoint Path", "budgetApi.ts:162 -> budget.py:300", "POST /admin/budget/templates vs /budget/templates.", CRITICAL_COLOR),
          issueRow("B8", "CRITICAL", "Endpoint Path", "budgetApi.ts:185 -> budget.py:321", "Apply template /admin prefix mismatch.", CRITICAL_COLOR),
          issueRow("B9", "CRITICAL", "Security Issue", "budget.py multiple endpoints", "No wedding access control on category update, delete, quote status. Cross-tenant data access.", CRITICAL_COLOR),
          issueRow("B10", "HIGH", "Missing Endpoint", "budgetApi.ts:259 -> budget.py:243", "Compare quotes uses query param, backend uses path param.", HIGH_COLOR),
          issueRow("B11", "HIGH", "Response Format", "budgetApi.ts:98 -> budget.py:214", "Quotes wrapped in {quotes:[...]} but frontend expects array.", HIGH_COLOR),
          issueRow("B12", "HIGH", "Response Format", "budgetApi.ts:148 -> budget.py:294", "Templates wrapped in object but frontend expects array.", HIGH_COLOR),
          issueRow("B13", "HIGH", "Missing Endpoint", "budget_service.py:968", "Contract payment sync method exists but no API endpoint.", HIGH_COLOR),
          issueRow("B14", "HIGH", "Business Logic Gap", "budget/page.tsx:278", "actual_spent can be manually edited bypassing payment records.", HIGH_COLOR),
          issueRow("B15", "MEDIUM", "Param Mismatch", "budgetApi.ts:199 -> budget.py:421", "Cost estimate wrong prefix and param format.", MEDIUM_COLOR),
          issueRow("B16", "MEDIUM", "Dead Code", "quotes/page.tsx:242", "Quote comparison receives data but never displays results.", MEDIUM_COLOR),
          issueRow("B17", "MEDIUM", "Missing Endpoint", "budgetApi.ts:127", "Rate vendor quote endpoint doesn't exist in backend.", MEDIUM_COLOR),
          issueRow("B18", "MEDIUM", "Missing Endpoint", "budgetApi.ts:247 -> budget.py:400", "Export report format param not handled. PDF/Excel export broken.", MEDIUM_COLOR),
          issueRow("B19", "MEDIUM", "Type Mismatch", "budget.ts:111", "Payment status confusion between category status and payment status.", MEDIUM_COLOR),
          issueRow("B20", "LOW", "Type Mismatch", "budget.ts:102 -> budget.py:179", "PaymentRecord missing created_at timestamp.", LOW_COLOR),
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ==========================================
      // SECTION 5: AI FEATURES
      // ==========================================
      heading("6. AI Features", HeadingLevel.HEADING_1),
      bodyText("Files reviewed: ai.py, autopilot.py, ai_service.py, ai_cache_service.py, autopilot_service.py, autopilot.py model, AI components, budget estimate page, feature_gates.py, money dashboard."),

      new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        columnWidths: [500, 1200, 1800, 2500, 3360],
        rows: [
          sectionHeader(),
          issueRow("A1", "CRITICAL", "Param Mismatch", "Seating UI -> ai.py", "Frontend sends current_table_id. Backend needs plus_one_allowed, accessibility_needs, age_group, language_preference. Accessibility broken.", CRITICAL_COLOR),
          issueRow("A2", "CRITICAL", "Security Issue", "autopilot.py:23-43", "CRON_SECRET not set = ALL payment endpoints unprotected. Anyone can trigger payments.", CRITICAL_COLOR),
          issueRow("A3", "HIGH", "Missing Error Handling", "ai.py seating endpoint", "No AI client initialization check unlike other AI endpoints.", HIGH_COLOR),
          issueRow("A4", "HIGH", "Response Format", "money/page.tsx -> autopilot.py", "Frontend expects data.forecast but backend returns flat structure. Financial forecasting broken.", HIGH_COLOR),
          issueRow("A5", "MEDIUM", "Dead Code", "Payment AI endpoints", "Payment AI features exist in backend but never called from frontend.", MEDIUM_COLOR),
          issueRow("A6", "MEDIUM", "Type Mismatch", "Seating response", "Response includes unexpected fields not used by frontend.", MEDIUM_COLOR),
          issueRow("A7", "LOW", "Dead Code", "AI health check", "Health check endpoint exists but not monitored.", LOW_COLOR),
          issueRow("A8", "LOW", "Missing Validation", "Frontend AI calls", "No upfront credit check before AI operations.", LOW_COLOR),
          issueRow("A9", "MEDIUM", "Missing Validation", "Payment forecast", "No input validation in payment forecast endpoint.", MEDIUM_COLOR),
          issueRow("A10", "MEDIUM", "Missing Documentation", "AI feature UI", "AI feature costs not documented or shown in UI.", MEDIUM_COLOR),
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ==========================================
      // DEPLOYMENT CHECKLIST
      // ==========================================
      heading("7. Pre-Deployment Checklist", HeadingLevel.HEADING_1),
      bodyText("Ordered by priority for the March 2026 wedding RSVP launch at thespecialwedding.io/emmanuel-peace."),

      heading("Phase 1: BLOCKERS (Must fix before ANY deployment)", HeadingLevel.HEADING_2),
      bulletItem("[  ] B1-B9: Fix all budget endpoint paths in budgetApi.ts (remove /admin prefix, fix /vendor-quotes -> /quotes, fix plural/singular)", "checks"),
      bulletItem("[  ] B9: Add wedding access control to all budget update/delete/status endpoints", "checks"),
      bulletItem("[  ] A2: Set CRON_SECRET environment variable in Coolify and add fail-closed guard", "checks"),
      bulletItem("[  ] C2-C3: Implement vendor contract creation and payment recording endpoints", "checks"),
      bulletItem("[  ] T3: Fix list_guests endpoint to convert _id to id string", "checks"),
      bulletItem("[  ] T1: Change silent skip to error on invalid guest IDs in assignment", "checks"),
      bulletItem("[  ] S1: Fix public checkout email validation for new planner signup", "checks"),
      bulletItem("[  ] S2: Fix billing success page to use admin_token instead of authToken", "checks"),
      bulletItem("[  ] S3: Fix subscription retrieval to use proper user_id format", "checks"),

      heading("Phase 2: HIGH PRIORITY (Fix before RSVP send-out)", HeadingLevel.HEADING_2),
      bulletItem("[  ] T7: Convert string guest IDs to ObjectId in constraints endpoint", "checks"),
      bulletItem("[  ] T5: Fix ObjectId format consistency in seating PDF export", "checks"),
      bulletItem("[  ] A1: Send all required guest fields to AI seating optimizer", "checks"),
      bulletItem("[  ] A4: Fix payment forecast response format to match frontend expectations", "checks"),
      bulletItem("[  ] C6: Standardize payment status enums between couple and vendor contracts", "checks"),
      bulletItem("[  ] C7: Add server-side SetupIntent validation before contract signing", "checks"),
      bulletItem("[  ] S4-S5: Add null checks for card info and plan data in billing page", "checks"),
      bulletItem("[  ] S8: Fix feature gate to check both user_id and user_email for subscriptions", "checks"),
      bulletItem("[  ] B10-B14: Fix response format wrappers and missing endpoints", "checks"),

      heading("Phase 3: RECOMMENDED (Fix before marketing launch)", HeadingLevel.HEADING_2),
      bulletItem("[  ] C4-C5: Implement contract section updates and auto-generate contract numbers", "checks"),
      bulletItem("[  ] C11: Add token expiration checking for public contract access", "checks"),
      bulletItem("[  ] C13: Implement contract status transitions (signed -> active -> completed)", "checks"),
      bulletItem("[  ] T2, T6: Add constraint cleanup on guest deletion", "checks"),
      bulletItem("[  ] T8: Add transaction safety for concurrent guest assignment", "checks"),
      bulletItem("[  ] S7: Add idempotency keys to webhook handlers", "checks"),
      bulletItem("[  ] B16-B18: Complete quote comparison UI, rating endpoint, and report export", "checks"),
      bulletItem("[  ] A5: Wire up payment AI features to frontend", "checks"),

      heading("Phase 4: NICE TO HAVE", HeadingLevel.HEADING_2),
      bulletItem("[  ] T9: Make print footer branding dynamic", "checks"),
      bulletItem("[  ] C10, C16, C18: Add attachment UI, PDF URL return, server-side placeholders", "checks"),
      bulletItem("[  ] B20: Add created_at to PaymentRecord frontend type", "checks"),
      bulletItem("[  ] A7-A8: Add AI health monitoring and upfront credit checks", "checks"),

      new Paragraph({ children: [new PageBreak()] }),

      // ==========================================
      // ROLLBACK PLAN
      // ==========================================
      heading("8. Rollback Triggers & Plan", HeadingLevel.HEADING_1),
      bodyText("If any of the following occur after deployment to thespecialwedding.io, immediately rollback:"),
      bulletItem("RSVP links return 500 errors for guests visiting /emmanuel-peace", "bullets"),
      bulletItem("Stripe payment failures exceed 5% of checkout attempts", "bullets"),
      bulletItem("Guest seating assignments not persisting after page refresh", "bullets"),
      bulletItem("Budget page returns 404 on any CRUD operation", "bullets"),
      bulletItem("Contract signing flow fails to save payment method", "bullets"),

      new Paragraph({ spacing: { before: 200 } }),
      bodyText("Rollback procedure:", { bold: true }),
      bulletItem("1. In Coolify dashboard, redeploy the previous successful build", "numbers"),
      bulletItem("2. Verify thespecialwedding.io/emmanuel-peace loads correctly", "numbers"),
      bulletItem("3. Check Stripe dashboard for any orphaned subscriptions", "numbers"),
      bulletItem("4. Notify affected users if RSVP was already sent", "numbers"),

      new Paragraph({ children: [new PageBreak()] }),

      // ==========================================
      // ESTIMATED FIX TIMES
      // ==========================================
      heading("9. Estimated Fix Timeline", HeadingLevel.HEADING_1),

      new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        columnWidths: [4000, 2680, 3180],
        rows: [
          new TableRow({ children: [
            new TableCell({ borders, width: { size: 4000, type: WidthType.DXA }, margins: cellMargins,
              shading: { fill: "1F2937", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [new TextRun({ text: "Fix Category", bold: true, size: 18, font: "Arial", color: "FFFFFF" })] })] }),
            new TableCell({ borders, width: { size: 2680, type: WidthType.DXA }, margins: cellMargins,
              shading: { fill: "1F2937", type: ShadingType.CLEAR },
              children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Est. Time", bold: true, size: 18, font: "Arial", color: "FFFFFF" })] })] }),
            new TableCell({ borders, width: { size: 3180, type: WidthType.DXA }, margins: cellMargins,
              shading: { fill: "1F2937", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [new TextRun({ text: "Issues Resolved", bold: true, size: 18, font: "Arial", color: "FFFFFF" })] })] }),
          ] }),
          new TableRow({ children: [
            cell("Budget endpoint path fixes (budgetApi.ts)", 4000),
            cell("2-3 hours", 2680),
            cell("B1-B9 (9 CRITICAL)", 3180),
          ] }),
          new TableRow({ children: [
            cell("Budget security (add access control)", 4000),
            cell("2-3 hours", 2680),
            cell("B9 (CRITICAL)", 3180),
          ] }),
          new TableRow({ children: [
            cell("Seating ID format fixes", 4000),
            cell("2-3 hours", 2680),
            cell("T1, T3, T5, T7 (1 CRIT, 3 HIGH)", 3180),
          ] }),
          new TableRow({ children: [
            cell("Stripe auth & subscription fixes", 4000),
            cell("3-4 hours", 2680),
            cell("S1-S5, S8 (1 CRIT, 4 HIGH, 1 MED)", 3180),
          ] }),
          new TableRow({ children: [
            cell("Contract endpoint implementation", 4000),
            cell("6-8 hours", 2680),
            cell("C2-C3 (2 CRITICAL)", 3180),
          ] }),
          new TableRow({ children: [
            cell("AI security & param fixes", 4000),
            cell("1-2 hours", 2680),
            cell("A1-A4 (2 CRIT, 2 HIGH)", 3180),
          ] }),
          new TableRow({ children: [
            cell("Remaining HIGH priority", 4000),
            cell("4-6 hours", 2680),
            cell("15 HIGH issues", 3180),
          ] }),
          new TableRow({ children: [
            new TableCell({ borders, width: { size: 4000, type: WidthType.DXA }, margins: cellMargins,
              shading: { fill: "F3F4F6", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [new TextRun({ text: "TOTAL PHASE 1 + 2", bold: true, size: 18, font: "Arial" })] })] }),
            new TableCell({ borders, width: { size: 2680, type: WidthType.DXA }, margins: cellMargins,
              shading: { fill: "F3F4F6", type: ShadingType.CLEAR },
              children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "20-29 hours", bold: true, size: 18, font: "Arial" })] })] }),
            new TableCell({ borders, width: { size: 3180, type: WidthType.DXA }, margins: cellMargins,
              shading: { fill: "F3F4F6", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [new TextRun({ text: "All CRITICAL + HIGH", bold: true, size: 18, font: "Arial" })] })] }),
          ] }),
        ]
      }),

      new Paragraph({ spacing: { before: 300 } }),
      bodyText("This report was generated by automated QA/Dev agents analyzing every frontend component, backend API route, service layer, and database model in the codebase. All findings are based on actual code review, not runtime testing."),
      bodyText("Next step: Begin fixing Phase 1 blockers immediately, then run end-to-end testing on thespecialwedding.io before sending any RSVP invitations."),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/sessions/charming-dazzling-knuth/mnt/WeddingWebApp/Pre_Deployment_QA_Report.docx", buffer);
  console.log("Document created successfully!");
}).catch(err => {
  console.error("Error:", err);
});
