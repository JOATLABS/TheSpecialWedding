# COMPREHENSIVE INTERACTIVE ELEMENTS INVENTORY
Generated: Thu Sep 18 05:40:31 PM CDT 2025

## SUMMARY STATISTICS

- Total TSX files: 100
- Files with interactive elements: 64
- Total interactive elements: 1687

## CURRENT ROUTE OWNERSHIP NOTE (2026-04-07)

This inventory snapshot predates the planner communications IA refactor. The current canonical planner messaging surfaces live under:

- `app/admin/communications/inbox/page.tsx`
- `app/admin/communications/invites/page.tsx`
- `app/admin/communications/reminders/page.tsx`
- `app/admin/communications/individual/page.tsx`
- `app/admin/communications/history/page.tsx`
- `app/admin/communications/components/CommunicationsInboxView.tsx`
- `app/admin/communications/components/CommunicationsRemindersView.tsx`

Legacy planner routes remain only as wrappers or redirects:

- `app/admin/inbox/page.tsx`
- `app/admin/reminders/page.tsx`

## PRIORITY 1: UI COMPONENT LIBRARY

### Base Components (`app/components/ui/`)

- **dialog**: 5 elements
  - File: `app/components/ui/dialog.tsx`
  - Line 75:      <button
  - Line 81:      </button>

- **textarea**: 2 elements
  - File: `app/components/ui/textarea.tsx`
  - Line 9:      <textarea
  - Line 11:          'flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',

- **button**: 2 elements
  - File: `app/components/ui/button.tsx`
  - Line 12:      <button
  - Line 18:            'border border-input bg-background hover:bg-accent hover:text-accent-foreground': variant === 'outline',

- **Button**: 1 elements
  - File: `app/components/ui/Button.tsx`
  - Line 12:  return <button {...props} className={`${base} ${style} ${className}`} />;

- **select**: 5 elements
  - File: `app/components/ui/select.tsx`
  - Line 44:    <button
  - Line 46:        'flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
  - Line 53:    </button>

- **tabs**: 3 elements
  - File: `app/components/ui/tabs.tsx`
  - Line 59:    <button
  - Line 70:    </button>

- **input**: 2 elements
  - File: `app/components/ui/input.tsx`
  - Line 9:      <input
  - Line 12:          'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',

- **switch**: 5 elements
  - File: `app/components/ui/switch.tsx`
  - Line 15:      <button
  - Line 16:        type="button"
  - Line 23:          checked ? 'bg-primary' : 'bg-input',

## PRIORITY 2: ADMIN INTERFACE

### Admin Pages (High Priority)

- **saas/page**: 123 elements
  - File: `app/admin/saas/page.tsx`
- **[id]/page**: 120 elements
  - File: `app/admin/weddings/[id]/page.tsx`
- **reminders/page**: 104 elements
  - File: `app/admin/reminders/page.tsx`
  - Note: legacy planner route reference from the pre-communications snapshot; canonical runtime ownership now lives under `app/admin/communications/*`
- **guests/page**: 84 elements
  - File: `app/admin/guests/page.tsx`
- **weddings/page**: 81 elements
  - File: `app/admin/weddings/page.tsx`
- **quotes/page**: 68 elements
  - File: `app/admin/budget/quotes/page.tsx`
- **profile/page**: 59 elements
  - File: `app/admin/profile/page.tsx`
- **responses/page**: 56 elements
  - File: `app/admin/forms/[id]/responses/page.tsx`
- **upload/page**: 51 elements
  - File: `app/admin/gallery/upload/page.tsx`
- **support/page**: 43 elements
  - File: `app/admin/support/page.tsx`

### Admin Components

- **AdminSidebar**: 12 elements
  - File: `app/admin/components/AdminSidebar.tsx`
- **AdminHeader**: 3 elements
  - File: `app/admin/components/AdminHeader.tsx`
- **ContentEditModal**: 38 elements
  - File: `app/admin/components/ContentEditModal.tsx`

## PRIORITY 3: PUBLIC FEATURES & FORMS

### Form Components

- **page**: 32 elements
  - File: `app/forms/[id]/page.tsx`
- **page**: 34 elements
  - File: `app/admin/forms/page.tsx`
- **page**: 16 elements
  - File: `app/admin/forms/[id]/edit/page.tsx`
- **page**: 12 elements
  - File: `app/admin/forms/[id]/analytics/page.tsx`
- **page**: 56 elements
  - File: `app/admin/forms/[id]/responses/page.tsx`
- **page**: 43 elements
  - File: `app/admin/forms/[id]/send/page.tsx`
- **FormPreview**: 34 elements
  - File: `app/components/forms/FormPreview.tsx`
- **FormBuilder**: 59 elements
  - File: `app/components/forms/FormBuilder.tsx`
- **RSVPForm**: 14 elements
  - File: `app/components/RSVPForm.tsx`
- **ContactFormSection**: 20 elements
  - File: `app/components/saas/ContactFormSection.tsx`
- **SmsOptInForm**: 9 elements
  - File: `app/components/SmsOptInForm.tsx`

### Landing Page Components

- **EventLocationSection**: 27 elements
  - File: `app/components/landing-page/EventLocationSection.tsx`
- **LandingLayout**: 7 elements
  - File: `app/components/landing-page/LandingLayout.tsx`

## PRIORITY 4: NAVIGATION & INFRASTRUCTURE

### Navigation & Layout


### Modal & Dialog Components

- **dialog**: 5 elements
  - File: `app/components/ui/dialog.tsx`

## ELEMENTS NEEDING SPECIAL ATTENTION

### High-Density Files (>30 elements)

app/admin/saas/page.tsx: 123 elements
app/admin/weddings/[id]/page.tsx: 120 elements
app/admin/reminders/page.tsx: 104 elements (legacy route snapshot; canonical runtime ownership now lives under app/admin/communications/*)
app/admin/guests/page.tsx: 84 elements
app/admin/weddings/page.tsx: 81 elements
app/admin/budget/quotes/page.tsx: 68 elements
app/components/forms/FormBuilder.tsx: 59 elements
app/admin/profile/page.tsx: 59 elements
app/admin/forms/[id]/responses/page.tsx: 56 elements
app/admin/gallery/upload/page.tsx: 51 elements
app/admin/support/page.tsx: 43 elements
app/admin/forms/[id]/send/page.tsx: 43 elements
app/admin/budget/page.tsx: 41 elements
app/admin/budget/estimate/page.tsx: 39 elements
app/admin/components/ContentEditModal.tsx: 38 elements
app/components/forms/FormPreview.tsx: 34 elements
app/admin/vendors/page.tsx: 34 elements
app/admin/forms/page.tsx: 34 elements
app/forms/[id]/page.tsx: 32 elements
app/components/GalleryGrid.tsx: 32 elements
app/components/saas/SignupModal.tsx: 31 elements

---
*Generated by inventory-interactive-elements.sh*
