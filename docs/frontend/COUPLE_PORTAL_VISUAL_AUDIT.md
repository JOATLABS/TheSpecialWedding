# Couple Portal Visual Audit — Parity with Planner Portal

**Date**: March 24, 2026
**Status**: Active — fixes pending
**Scope**: Every visual element in `/couple/` vs the admin/planner portal

---

## Executive Summary

The couple-facing portal (`/couple/`) was built as a separate visual system instead of reusing the platform's shared design tokens, components, and patterns. This audit documents every difference between the planner (admin) portal and the couple portal, organized by page/component.

**Key problems**:
- Hardcoded colors (`#1e3a5f`, `#d4af37`) instead of Tailwind theme tokens (`primary-*`, `wedding-navy`)
- `font-serif` instead of `font-heading` (Playfair Display)
- Solid cards instead of `GlassCard` on setup/login-adjacent pages
- Center-aligned page layout vs platform's left-aligned sidebar content
- No `PageHeader` component usage
- Missing AI Chat widget
- `text-lg` title vs platform's `text-xl`
- No user avatar/dropdown in TopHeader

---

## 1. Login Page

**Admin**: `app/admin/login/page.tsx`
**Couple**: `app/couple/login/page.tsx`

| Element | Admin (Reference) | Couple (Current) | Fix Needed |
|---------|-------------------|-------------------|------------|
| Portal label | `"Planner portal"` — `text-xs font-medium uppercase tracking-[0.3em]` | `"Wedding portal"` — same classes | Content-only — OK |
| Main heading | `"Welcome back"` — `text-[1.6rem] sm:text-[1.8rem] font-semibold text-wedding-navy` | Same | ✅ Matches |
| Subtitle | `text-[0.9rem] text-wedding-navy/70` | Same | ✅ Matches |
| Card | `GlassCard depth="near" blur="xl"` | Same | ✅ Matches |
| Input fields | `rounded-xl border border-white/40 bg-white/60 px-4 py-3 text-base` | Same | ✅ Matches |
| Password field padding | `pr-12` | `pr-16` | ❌ Mismatched |
| Show/hide button | `inset-y-0 right-0 flex items-center rounded-r-xl px-4` | `absolute right-3 top-1/2 -translate-y-1/2` | ❌ Different positioning |
| Error message | `rounded-lg border border-wedding-rose/40 bg-wedding-rose/10 text-sm text-wedding-rose` | `rounded-xl bg-red-50 text-sm text-red-700` | ❌ Different tokens |
| Remember Me | Present | Absent | ❌ Missing |
| Showcase icon | Custom SVG user icon | Lucide `Heart` icon | Intentional difference — OK |
| Background gradient | `from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff]` | Same | ✅ Matches |

---

## 2. Setup / Account Creation Page

**Admin**: `app/setup-account/page.tsx`
**Couple**: `app/couple/setup/page.tsx`

| Element | Admin (Reference) | Couple (Current) | Fix Needed |
|---------|-------------------|-------------------|------------|
| Background | `bg-gradient-to-br from-indigo-50 via-white to-emerald-50` | None (inherits from layout) | ❌ Missing gradient |
| Card | `GlassCard depth="mid"` + `max-w-md mx-auto p-8` | `bg-white rounded-2xl shadow-lg border border-gray-100 p-8` | ❌ Should use GlassCard |
| Title font | `text-2xl font-bold text-gray-900` (uses theme font stack) | `text-3xl font-serif text-[#1e3a5f]` | ❌ Hardcoded `font-serif` and color |
| Title color | Uses theme tokens | Hardcoded `#1e3a5f` | ❌ Should use `text-wedding-navy` |
| Icon | SVG in indigo-600 | `Heart` in `bg-[#1e3a5f]` circle, `text-[#d4af37]` | ❌ Hardcoded colors |
| Input fields | `px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500` | `pl-11 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f]` | ❌ Hardcoded focus colors |
| Input icons | None | Lock icon on left | Style divergence |
| Button | `bg-indigo-600 hover:bg-indigo-700 rounded-lg` | `bg-[#1e3a5f] hover:bg-[#2a4a6f] rounded-xl` | ❌ Hardcoded colors |
| Password requirements | Visual checklist with checkmarks | Toast validation only | ❌ Missing UX |
| Form layout | Grid `grid-cols-2 gap-4` for name fields | Single column only | Different scope — OK |
| Error state | Inline error display | Toast-based | Style divergence |
| Page centering | `flex items-center justify-center` | `flex items-center justify-center` | Same — OK for auth pages |

---

## 3. Layout

**Admin**: `app/admin/layout.tsx`
**Couple**: `app/couple/components/CoupleLayoutClient.tsx` + `app/couple/dashboard/page.tsx`

| Element | Admin (Reference) | Couple (Current) | Fix Needed |
|---------|-------------------|-------------------|------------|
| Root wrapper | `min-h-screen overflow-x-hidden bg-light-bg dark:bg-dark-bg text-light-text dark:text-dark-text font-sans` | Dashboard page: `min-h-screen overflow-x-hidden` (missing bg/text/font) | ❌ Fixed (Mar 24) |
| Content z-index | `relative z-10 flex flex-col min-h-screen` | Was missing `relative z-10` | ❌ Fixed (Mar 24) |
| Mesh gradient | `fixed inset-0 z-0 opacity-40 dark:opacity-20` | Present in CoupleLayoutClient | ✅ Matches |
| Sidebar integration | Layout wraps Sidebar + TopHeader centrally | Dashboard page manages its own Sidebar/Header | ❌ Architecture mismatch |
| Main content padding | `p-4 sm:p-6 lg:p-8 space-y-6 overflow-x-hidden` | `p-4 sm:p-6 lg:p-8 space-y-6 overflow-x-hidden` | ✅ Matches |
| Providers | ThemeProvider + AdminProvider + SSEProvider + ConfirmDialogProvider | ThemeProvider only | Expected — different scope |
| AI Chat Widget | `<AIChatWidget />` on all admin pages | Absent | ❌ Missing (user confirmed it's needed) |
| TrialBanner | Present | Not applicable | OK |
| ErrorBoundary | Present wrapping children | Absent in couple | ❌ Missing |

---

## 4. Sidebar

**Admin**: `app/admin/components/Sidebar.tsx`
**Couple**: `app/couple/components/CoupleSidebar.tsx`

| Element | Admin (Reference) | Couple (Current) | Fix Needed |
|---------|-------------------|-------------------|------------|
| Container classes | `bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-r border-slate-200/50 dark:border-slate-700/50` | Same | ✅ Matches |
| Width | `18rem` / `5rem` | Same | ✅ Matches |
| Logo section | `h-16 px-3 border-b` | Same | ✅ Matches |
| Nav item border-radius | `rounded-lg` | `rounded-xl` | ❌ Mismatch |
| Active state colors | `bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400` | Same tokens | ✅ Matches |
| Inactive hover | `hover:bg-slate-100 dark:hover:bg-slate-800` | Same | ✅ Matches |
| Mobile overlay | `bg-black/50 z-40 lg:hidden` | Same | ✅ Matches |
| Badge styling | `text-[10px] font-bold text-white bg-red-500 rounded-full` | Same | ✅ Matches |
| Logout section | `p-3 border-t` with hover red | Same | ✅ Matches |

**Minor fix**: Change couple nav items from `rounded-xl` to `rounded-lg` to match admin.

---

## 5. TopHeader

**Admin**: `app/admin/components/TopHeader.tsx`
**Couple**: `app/couple/components/CoupleTopHeader.tsx`

| Element | Admin (Reference) | Couple (Current) | Fix Needed |
|---------|-------------------|-------------------|------------|
| Container | `sticky top-0 z-30 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-b border-slate-200/50 dark:border-slate-700/50` | Same | ✅ Matches |
| Height/padding | `h-16 px-4 sm:px-6 lg:px-8` | Same | ✅ Matches |
| Page title size | `text-xl font-heading font-semibold` | `text-lg font-heading font-semibold` | ❌ `text-lg` should be `text-xl` |
| Theme toggle | Sun `text-amber-500`, Moon `text-slate-600` | Same | ✅ Matches |
| Menu button | `p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 lg:hidden` | Same | ✅ Matches |
| User profile avatar | `w-8 h-8 rounded-full bg-gradient-to-br from-primary-400 to-secondary-400` with initials | Absent — shows Heart icon + couple name | ❌ Missing avatar |
| Notifications bell | Present with badge count | Absent | ❌ Missing |
| Logout | Inside dropdown menu with settings | Direct button in header | ❌ Different UX pattern |
| Dropdown menu | `w-48 bg-white dark:bg-slate-800 rounded-lg shadow-lg` | Absent | ❌ Missing |

---

## 6. Dashboard Content

**Admin**: `app/admin/planner/page.tsx` — uses `PageHeader` component
**Couple**: `app/couple/dashboard/page.tsx` — inline content

| Element | Admin (Reference) | Couple (Current) | Fix Needed |
|---------|-------------------|-------------------|------------|
| Page header | `<PageHeader title="..." description="..." />` | No PageHeader — inline content | ❌ Should use PageHeader |
| Title styling | Via PageHeader: `text-2xl sm:text-3xl font-semibold text-slate-900 dark:text-white` | Not present (sections start directly with cards) | ❌ No page title |
| Card styling | `bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700` | Same | ✅ Matches |
| Stat card numbers | Varies | `text-2xl font-semibold text-slate-900 dark:text-white` | ✅ OK |
| Section spacing | `space-y-6` | `space-y-6` | ✅ Matches |
| Content alignment | Left-aligned within sidebar layout | Left-aligned within sidebar layout | ✅ Matches |

---

## 7. Hardcoded Colors Inventory

These hardcoded values in the couple portal need to be replaced with theme tokens:

| Hardcoded | Should Be | Files |
|-----------|-----------|-------|
| `#1e3a5f` | `text-wedding-navy` or `text-primary-700` | `setup/page.tsx` |
| `#d4af37` | `text-wedding-gold` or `text-secondary-400` | `setup/page.tsx` |
| `#2a4a6f` | `hover:bg-primary-800` | `setup/page.tsx` |
| `bg-red-50 text-red-700` | `border-wedding-rose/40 bg-wedding-rose/10 text-wedding-rose` | `login/page.tsx` |
| `focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f]` | `focus:ring-primary-500/20 focus:border-primary-500` | `setup/page.tsx` |

---

## 8. Missing Shared Components

| Component | Used in Admin | Used in Couple | Action |
|-----------|--------------|----------------|--------|
| `PageHeader` | Yes — all pages | No | Add to couple sections |
| `GlassCard` | Login, setup pages | Login only — not setup | Add to couple setup |
| `ErrorBoundary` | Layout wrapper | Missing | Add to couple layout |
| `AIChatWidget` | All admin pages | Missing | Add to couple layout |
| User avatar/dropdown | TopHeader | Missing | Add to CoupleTopHeader |

---

## 9. Font Usage Summary

| Context | Admin | Couple | Match? |
|---------|-------|--------|--------|
| Body text | `font-sans` (Inter) | `font-sans` (Inter) | ✅ |
| Headings | `font-heading` (Playfair Display) | Mixed — some `font-heading`, some `font-serif` | ❌ |
| Setup page title | Theme font stack | `font-serif` (generic) | ❌ |
| TopHeader couple name | N/A | `font-heading` | ✅ |
| Login titles | `font-semibold text-wedding-navy` | Same | ✅ |

---

## 10. Action Items (Priority Order)

### P0 — Must Fix (Visual Breaks)

1. **Setup page**: Replace all hardcoded colors with theme tokens, use `GlassCard`, use `font-heading` not `font-serif`
2. **TopHeader title size**: Change `text-lg` → `text-xl` to match admin
3. **Add AIChatWidget** to couple layout/dashboard
4. **Add ErrorBoundary** to couple layout

### P1 — Should Fix (Consistency)

5. **Login error styling**: Use `wedding-rose` tokens instead of `red-50/red-700`
6. **Login password field**: Match `pr-12` and show/hide button positioning to admin
7. **Sidebar nav item radius**: Change `rounded-xl` → `rounded-lg` to match admin
8. **Add PageHeader** to couple dashboard sections (or create section headers)
9. **TopHeader**: Add user avatar with initials and dropdown menu (Settings/Logout)

### P2 — Architecture (Deduplication)

10. **Extract shared MeshGradientBackground** component — used 4× identically
11. **Extract shared BaseSidebar** component — admin + couple configure via props
12. **Extract shared BaseTopHeader** component — with slot for right-side content
13. **Move sidebar/header management** from dashboard page to couple layout (match admin architecture)

---

## File References

| File | Role |
|------|------|
| `app/admin/login/page.tsx` | Admin login — reference |
| `app/couple/login/page.tsx` | Couple login — needs fixes |
| `app/setup-account/page.tsx` | Admin setup — reference |
| `app/couple/setup/page.tsx` | Couple setup — needs fixes |
| `app/admin/layout.tsx` | Admin layout — reference |
| `app/couple/components/CoupleLayoutClient.tsx` | Couple layout client |
| `app/couple/dashboard/page.tsx` | Couple dashboard — needs fixes |
| `app/admin/components/Sidebar.tsx` | Admin sidebar — reference |
| `app/couple/components/CoupleSidebar.tsx` | Couple sidebar — minor fix |
| `app/admin/components/TopHeader.tsx` | Admin TopHeader — reference |
| `app/couple/components/CoupleTopHeader.tsx` | Couple TopHeader — needs fixes |
| `app/admin/components/PageHeader.tsx` | Shared PageHeader — not used by couple |
| `app/components/ui/GlassCard.tsx` | Shared GlassCard — not used by couple setup |
| `app/components/ai/AIChatWidget.tsx` | AI Chat — missing from couple |
