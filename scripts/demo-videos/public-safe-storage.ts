import fs from 'node:fs';

const FORBIDDEN_PUBLIC_DEMO_PATTERNS = [
  /peace\s*(?:&|and|-|_)?\s*emmanuel/i,
  /emmanuel\s*(?:&|and|-|_)?\s*peace/i,
  /peace[-_]emmanuel/i,
  /emmanuel[-_]peace/i,
  /couple_demo_video_peace_emmanuel/i,
  /wedding_demo_video_peace_emmanuel/i,
  /akinwale/i,
];

type StorageStateCookie = {
  name?: string;
  value?: string;
};

type StorageState = {
  cookies?: StorageStateCookie[];
};

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
  const haystacks = [raw];

  try {
    const parsed = JSON.parse(raw) as StorageState;
    for (const cookie of parsed.cookies ?? []) {
      if (!cookie.value) continue;
      haystacks.push(...jwtPayloadsFromCookieValue(cookie.value));
    }
  } catch {
    haystacks.push(raw);
  }

  const violations = new Set<string>();
  for (const haystack of haystacks) {
    for (const pattern of FORBIDDEN_PUBLIC_DEMO_PATTERNS) {
      if (pattern.test(haystack)) {
        violations.add(pattern.source);
      }
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
      'It contains owner-wedding identity in the raw file or decoded auth cookies.',
      `Matched: ${violations.join(', ')}`,
      'Regenerate with the Sofia & Daniel demo couple, or pass an explicitly private storage state outside the public marketing capture path.',
    ].join('\n'),
  );
}
