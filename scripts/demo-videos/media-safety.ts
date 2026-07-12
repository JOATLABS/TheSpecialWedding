import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';

export type PublicCaptureSafetyCode =
  | 'owner-identity'
  | 'local-origin'
  | 'development-label'
  | 'test-label'
  | 'demo-label'
  | 'fixture-label'
  | 'sandbox-label'
  | 'preview-only-label'
  | 'example-identity'
  | 'error-state'
  | 'loading-state'
  | 'email-address'
  | 'phone-number'
  | 'bearer-token'
  | 'jwt-token'
  | 'query-token'
  | 'internal-demo-id'
  | 'database-id'
  | 'ocr-unavailable'
  | 'ocr-failed';

type SafetyPattern = {
  code: PublicCaptureSafetyCode;
  pattern: RegExp;
};

export type PublicCaptureSafetyFinding = {
  code: PublicCaptureSafetyCode;
  evidenceSha256: string;
};

export type CaptureArtifactSafetyReceipt = {
  artifactSha256: string;
  byteLength: number;
  safe: boolean;
  ocrStatus: 'provided' | 'completed' | 'unavailable' | 'failed';
  findings: readonly PublicCaptureSafetyFinding[];
};

export type ScanCaptureArtifactOptions = {
  visibleText?: string;
  /** Test and adapter seam. Production callers should let the configured OCR executable provide this. */
  ocrText?: string;
  requireOcr?: boolean;
  ocrExecutable?: string;
};

const PUBLIC_CAPTURE_SAFETY_PATTERNS: readonly SafetyPattern[] = [
  {
    code: 'owner-identity',
    pattern: /peace\s*(?:&|and|-|_)?\s*emmanuel|emmanuel\s*(?:&|and|-|_)?\s*peace|akinwale/i,
  },
  {
    code: 'local-origin',
    pattern: /(?:https?:\/\/)?(?:localhost|127(?:\.\d{1,3}){3}|0\.0\.0\.0)(?::\d+)?|\b[a-z0-9-]+\.local\b/i,
  },
  { code: 'development-label', pattern: /\bdev(?:elopment)?\b/i },
  { code: 'test-label', pattern: /\btest(?:ing)?\b/i },
  { code: 'demo-label', pattern: /\bdemo\b/i },
  { code: 'fixture-label', pattern: /\bfixtures?\b/i },
  { code: 'sandbox-label', pattern: /\bsandbox\b/i },
  { code: 'preview-only-label', pattern: /\bpreview\s+only\b/i },
  { code: 'example-identity', pattern: /(?:example\.(?:com|org|net)|example@)/i },
  {
    code: 'error-state',
    pattern: /\b(?:authentication\s+failed|failed\s+to\s+(?:load|fetch|save)|something\s+went\s+wrong|forbidden|not\s+found|unable\s+to\s+load|error\s+(?:loading|saving))\b/i,
  },
  { code: 'loading-state', pattern: /\b(?:loading|please\s+wait)\.{0,3}\b/i },
  {
    code: 'email-address',
    pattern: /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i,
  },
  {
    code: 'phone-number',
    pattern: /(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]*\d{3}[\s.-]*\d{4}\b/,
  },
  { code: 'bearer-token', pattern: /\bbearer\s+[A-Z0-9._~-]{12,}\b/i },
  { code: 'jwt-token', pattern: /\beyJ[A-Z0-9_-]{4,}\.[A-Z0-9_-]+\.[A-Z0-9_-]+\b/i },
  {
    code: 'query-token',
    pattern: /(?:[?&]|\b)(?:access_token|auth_token|signature|token|uploadToken)=[A-Z0-9._~-]{8,}/i,
  },
  {
    code: 'internal-demo-id',
    pattern: /\b(?:CON-DEMO-[A-Z0-9-]+|(?:wedding|couple|guest|vendor)[-_]demo[-_][A-Z0-9_-]+)\b/i,
  },
  { code: 'database-id', pattern: /\b[0-9a-f]{24}\b/i },
] as const;

function sha256(value: string | Buffer): string {
  return createHash('sha256').update(value).digest('hex');
}

function finding(code: PublicCaptureSafetyCode, evidence: string): PublicCaptureSafetyFinding {
  return { code, evidenceSha256: sha256(evidence) };
}

export function findPublicCaptureSafetyFindings(text: string): PublicCaptureSafetyFinding[] {
  const findings = new Map<PublicCaptureSafetyCode, PublicCaptureSafetyFinding>();

  for (const { code, pattern } of PUBLIC_CAPTURE_SAFETY_PATTERNS) {
    const match = pattern.exec(text);
    if (!match) continue;
    findings.set(code, finding(code, match[0]));
  }

  return [...findings.values()].sort((left, right) => left.code.localeCompare(right.code));
}

function runOcr(
  artifactPath: string,
  executable: string,
): { status: CaptureArtifactSafetyReceipt['ocrStatus']; text: string; finding?: PublicCaptureSafetyFinding } {
  const result = spawnSync(executable, [artifactPath, 'stdout', '--psm', '6', '-l', 'eng'], {
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024,
  });

  if (result.error) {
    const code = result.error.message.includes('ENOENT') ? 'ocr-unavailable' : 'ocr-failed';
    return { status: code === 'ocr-unavailable' ? 'unavailable' : 'failed', text: '', finding: finding(code, code) };
  }

  if (result.status !== 0) {
    return { status: 'failed', text: '', finding: finding('ocr-failed', `exit:${result.status ?? 'unknown'}`) };
  }

  return { status: 'completed', text: result.stdout ?? '' };
}

export function scanCaptureArtifact(
  artifactPath: string,
  options: ScanCaptureArtifactOptions = {},
): CaptureArtifactSafetyReceipt {
  const bytes = fs.readFileSync(artifactPath);
  const requireOcr = options.requireOcr ?? true;
  const ocr = options.ocrText === undefined
    ? runOcr(artifactPath, options.ocrExecutable ?? process.env.DEMO_CAPTURE_OCR_EXECUTABLE ?? 'tesseract')
    : { status: 'provided' as const, text: options.ocrText };

  const findings = new Map<PublicCaptureSafetyCode, PublicCaptureSafetyFinding>();
  for (const item of findPublicCaptureSafetyFindings([options.visibleText ?? '', ocr.text].join('\n'))) {
    findings.set(item.code, item);
  }
  if (requireOcr && ocr.finding) {
    findings.set(ocr.finding.code, ocr.finding);
  }

  const orderedFindings = [...findings.values()].sort((left, right) => left.code.localeCompare(right.code));
  return {
    artifactSha256: sha256(bytes),
    byteLength: bytes.byteLength,
    safe: orderedFindings.length === 0,
    ocrStatus: ocr.status,
    findings: orderedFindings,
  };
}

export function assertCaptureArtifactSafe(
  artifactPath: string,
  options: ScanCaptureArtifactOptions = {},
): CaptureArtifactSafetyReceipt {
  const receipt = scanCaptureArtifact(artifactPath, options);
  if (receipt.safe) return receipt;

  throw new Error(
    `Capture artifact failed public-safety scan (${receipt.findings.map((item) => item.code).join(', ')}).`,
  );
}
