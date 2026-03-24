# Couple Portal Inconsistency Report

## What Exists (Shared Resources the Couple Portal SHOULD Use)

### Shared UI Primitives (`/app/components/ui/`)
- `Button` — variants (primary, secondary, danger, outline, ghost), sizes, loading state
- `Card`, `CardHeader`, `CardTitle`, `CardContent` — dark mode, rounded, shadow
- `Dialog`, `DialogTrigger`, `DialogContent` — context-based, keyboard, backdrop dismiss
- `Badge` — variants (default, success, warning, danger, outline)
- `Input` — dark mode, accessible
- `Label` — accessible form labels
- `Textarea` — dark mode
- `GlassCard` — glassmorphism with depth/blur, dark mode
- `ConfirmDialogProvider` / `useConfirmDialog` — promise-based confirm dialogs

### Shared Contexts (`/app/contexts/`)
- `ThemeProvider` / `useTheme` — dark mode, system preference, localStorage
- `SSEProvider` / `useSSEEvent` — real-time notifications (couple portal has NO real-time)

### Shared Components (`/app/components/`)
- `ErrorBoundary` — catch errors, fallback UI
- `LoadingSpinner` — sizes (sm, md, lg), animated, optional message

### Shared Utilities (`/app/utils/`)
- `dateFormat.ts` — timezone-aware formatting
- `errorHandler.ts` — standardized error parsing
- `env.ts` — `getApiBaseUrl()`, `getFrontendUrl()`

### Platform Patterns (from admin pages)
- `PageHeader` — unified page title + action buttons
- Bell notification icon with unread count badge (in TopHeader)
- User profile avatar with initials fallback
- Gradient user avatar: `bg-gradient-to-br from-primary-400 to-secondary-400`

---

## INCONSISTENCIES FOUND

### 1. Login Page (`/couple/login/page.tsx`)
| Issue | Couple Portal | Platform Standard |
|-------|--------------|-------------------|
| Background | `min-h-screen flex items-center justify-center` (plain) | Gradient `bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff]` with ambient blur circles |
| Card | `bg-white rounded-2xl shadow-lg border border-gray-100` (light-only) | `GlassCard depth="near" blur="xl"` with glassmorphism |
| Font heading | `font-serif text-[#1e3a5f]` (hardcoded) | `font-semibold text-wedding-navy` (design token) |
| Subtitle | `text-gray-500 text-sm tracking-widest uppercase` | `text-xs font-medium uppercase tracking-[0.3em] text-wedding-navy/70` |
| Inputs | `border-gray-200 focus:ring-[#1e3a5f]/20` (hardcoded) | `border-white/40 bg-white/60 focus:border-wedding-rose focus:ring-wedding-rose/50` |
| Button | `bg-[#1e3a5f] hover:bg-[#2a4a6f]` (hardcoded) | Uses `<Button>` component with proper variants |
| Layout | Single centered column | Split layout with `WelcomeShowcase` panel |
| Dark mode | None | Full dark mode support |
| Show/hide password | None | Toggle button |
| Help text | None | `p.text-xs.text-wedding-navy/60` guidance |

### 2. Setup Page (`/couple/setup/page.tsx`)
| Issue | Couple Portal | Platform Standard |
|-------|--------------|-------------------|
| Same issues as login | Hardcoded colors, no glassmorphism, no dark mode, centered column layout |
| Error states | `bg-red-50 rounded-full` with `XCircle` | Should use platform error patterns |
| Success badge | `bg-green-50 text-green-700` (hardcoded) | Should use `Badge` component with success variant |

### 3. Dashboard Page Wrapper (`/couple/dashboard/page.tsx`)
| Issue | Couple Portal | Platform Standard |
|-------|--------------|-------------------|
| Outer div | ~~`min-h-screen overflow-x-hidden`~~ (FIXED: added bg/text tokens) | `min-h-screen overflow-x-hidden bg-light-bg dark:bg-dark-bg` |
| Content z-index | ~~Missing~~ (FIXED: added `relative z-10`) | `relative z-10` |

### 4. CoupleTopHeader vs Admin TopHeader
| Issue | Couple Portal | Platform Standard |
|-------|--------------|-------------------|
| Notifications | NONE — no bell icon | Bell icon with unread count + SSE real-time updates |
| User profile | Simple text: couple name | Avatar with initials + profile dropdown menu |
| Logout | Standalone button in header | Inside dropdown menu |
| Title display | Heart icon + couple name | Optional page title via `title` prop |
| Font | `text-lg font-heading font-semibold` | `text-xl font-heading font-semibold` |

### 5. CoupleSidebar vs Admin Sidebar
| Issue | Couple Portal | Platform Standard |
|-------|--------------|-------------------|
| Active state source | Callback props (`activeSection`) | URL-based via `usePathname()` |
| Permission filtering | None | Role-based filtering per team permissions |
| Shortcut section | None | Admin has keyboard shortcuts section |
| Badge rendering | Inline, but offset bug when collapsed (`absolute left-[3.2rem]`) | Admin uses different positioning |

### 6. Global Font & Color Issues
| Issue | Couple Portal | Platform Standard |
|-------|--------------|-------------------|
| Login fonts | `font-serif` (raw CSS) | `font-heading` (Playfair Display via Tailwind config) |
| Color palette | `#1e3a5f`, `#d4af37`, `gray-*` (hardcoded hex) | `wedding-navy`, `wedding-gold`, `slate-*` (design tokens) |
| Body text | `text-gray-500`, `text-gray-700` | `text-slate-500 dark:text-slate-400`, `text-slate-700 dark:text-slate-300` |
| Card backgrounds | `bg-white border border-gray-100` (no dark) | `bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700` |

### 7. Missing Shared Component Usage
| Feature | Couple Portal Uses | Should Use |
|---------|-------------------|-----------|
| Buttons | Raw `<button>` with inline classes | `<Button>` component |
| Cards | Raw `<div>` with card classes | `<Card>` component |
| Form inputs | Raw `<input>` with inline classes | `<Input>` component |
| Labels | Raw `<label>` with inline classes | `<Label>` component |
| Loading | Inline `<Loader2>` spinner | `<LoadingSpinner>` component |
| Error boundary | Not wrapped | `<ErrorBoundary>` |
| Confirm dialogs | None | `<ConfirmDialogProvider>` + `useConfirmDialog` |
| Badges | Inline styled `<span>` | `<Badge>` component |

### 8. Missing Features on Couple Portal
- No bell notification icon / unread notification count
- No SSE real-time updates (planner messages arrive, couple sees nothing until refresh)
- No ConfirmDialog for destructive actions (delete registry, etc.)
- No AIChatWidget (planner gets AI assistance, couple gets nothing)
- No account settings (couple can't change password from dashboard)
- No proper error boundary wrapping

---

## PRIORITY FIX ORDER

1. **CoupleTopHeader** — Add notifications bell, use proper font sizes, avatar pattern
2. **Login page** — Use GlassCard, Button, Input, design tokens, dark mode, split layout
3. **Setup page** — Same as login: GlassCard, Button, Input, design tokens, dark mode
4. **Dashboard page** — Replace raw HTML with shared components (Button, Card, Badge, LoadingSpinner)
5. **CoupleLayoutClient** — Add ConfirmDialogProvider, ErrorBoundary wrapping
6. **SSE integration** — Add SSEProvider to couple layout for real-time notifications
7. **Extract shared base Sidebar/Header** — Reduce duplication between admin and couple
