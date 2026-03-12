/**
 * Shared constants for wedding slug validation.
 *
 * Used by both middleware.ts and [slug]/layout.tsx to prevent
 * static-asset or reserved-path requests from reaching the
 * wedding API. Kept in one place to avoid drift.
 */

/** Top-level paths that are NOT wedding slugs. */
export const RESERVED_SLUG_PATHS = new Set([
  '_next', 'api', 'admin', 'favicon', 'robots', 'sitemap',
]);

/** Quick check: is this slug clearly not a wedding page? */
export function isNonWeddingSlug(slug: string): boolean {
  // Contains a dot → static asset (favicon.ico, apple-touch-icon.png, etc.)
  if (slug.includes('.')) return true;
  // Reserved path name
  if (RESERVED_SLUG_PATHS.has(slug.toLowerCase())) return true;
  return false;
}
