import fs from 'node:fs';

import { findPublicCaptureSafetyFindings } from './media-safety';

type StorageStateCookie = {
  name?: string;
  value?: string;
};

type StorageState = {
  cookies?: StorageStateCookie[];
  origins?: Array<{
    origin?: string;
    localStorage?: Array<{ name?: string; value?: string }>;
  }>;
};

function publicSafetyHaystack(raw: string, parsed: StorageState): string {
  const looksLikePlaywrightState = Array.isArray(parsed.cookies) || Array.isArray(parsed.origins);
  if (!looksLikePlaywrightState) return raw;

  // Local cookie domains and origin URLs are transport details for a local capture
  // session. Keep key names in the structural scan, decode cookie identity claims
  // separately below, and leave rendered PII/token enforcement to the DOM + OCR
  // artifact scan.
  return JSON.stringify({
    cookies: (parsed.cookies ?? []).map((cookie) => ({ name: cookie.name })),
    origins: (parsed.origins ?? []).map((origin) => ({
      localStorageKeys: (origin.localStorage ?? []).map((entry) => entry.name),
    })),
  });
}

function decodeBase64Url(value: string): string | null {
  try {
    const padded = value.padEnd(value.length + ((4 - (value.length % 4)) % 4), '=');
    return Buffer.from(padded.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8');
  } catch {
    return null;
  }
}

function jwtPayloadsFromCookieValue(rawValue: string): string[] {
  const value = rawValue.replace(/^"+|"+$/g, '');
  const parts = value.split('.');
  if (parts.length < 2) return [];

  const decoded = decodeBase64Url(parts[1]);
  return decoded ? [decoded] : [];
}

export function findPublicDemoStorageStateViolations(filePath: string): string[] {
  const raw = fs.readFileSync(filePath, 'utf8');
  const haystacks: string[] = [];
  let playwrightStorageState = false;

  try {
    const parsed = JSON.parse(raw) as StorageState;
    playwrightStorageState = Array.isArray(parsed.cookies) || Array.isArray(parsed.origins);
    haystacks.push(publicSafetyHaystack(raw, parsed));
    for (const cookie of parsed.cookies ?? []) {
      if (!cookie.value) continue;
      haystacks.push(...jwtPayloadsFromCookieValue(cookie.value));
    }
  } catch {
    haystacks.push(raw);
  }

  const violations = new Set<string>();
  for (const haystack of haystacks) {
    for (const safetyFinding of findPublicCaptureSafetyFindings(haystack)) {
      // Auth cookies necessarily contain token-shaped values and often fixture
      // email claims. They are not rendered by the browser. For a real
      // Playwright state, retain the original identity guard and leave visible
      // PII/token enforcement to the DOM + OCR artifact scan.
      if (playwrightStorageState && safetyFinding.code !== 'owner-identity') continue;
      violations.add(safetyFinding.code);
    }
  }

  return [...violations].sort();
}

export function assertPublicSafeStorageState(filePath: string): void {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Storage state file does not exist: ${filePath}`);
  }

  const violations = findPublicDemoStorageStateViolations(filePath);
  if (violations.length === 0) return;

  throw new Error(
    [
      `Storage state is not public-safe: ${filePath}`,
      'It contains public-capture safety violations in the raw file or decoded auth cookies.',
      `Matched categories: ${violations.join(', ')}`,
      'The matched values are intentionally omitted. Regenerate a disposable public-safe session before capture.',
    ].join('\n'),
  );
}
