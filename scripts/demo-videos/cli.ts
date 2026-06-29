import path from 'node:path';
import { fileURLToPath } from 'node:url';

export type CliArgs = {
  flags: Set<string>;
  values: Map<string, string>;
  repeatedValues: Map<string, string[]>;
};

export const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

export function parseCliArgs(argv: readonly string[]): CliArgs {
  const flags = new Set<string>();
  const values = new Map<string, string>();
  const repeatedValues = new Map<string, string[]>();

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (!arg.startsWith('--')) continue;

    const withoutPrefix = arg.slice(2);
    const [key, inlineValue] = withoutPrefix.split('=', 2);
    const next = argv[index + 1];
    const value = inlineValue ?? (next && !next.startsWith('--') ? next : undefined);

    if (value === undefined) {
      flags.add(key);
      continue;
    }

    if (inlineValue === undefined) {
      index += 1;
    }

    values.set(key, value);
    repeatedValues.set(key, [...(repeatedValues.get(key) ?? []), value]);
  }

  return { flags, values, repeatedValues };
}

export function getRequiredValue(args: CliArgs, key: string): string {
  const value = args.values.get(key);
  if (!value) {
    throw new Error(`Missing required --${key} value.`);
  }

  return value;
}

export function getNumberValue(args: CliArgs, key: string, fallback: number): number {
  const value = args.values.get(key);
  if (!value) return fallback;

  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`--${key} must be a positive number.`);
  }

  return parsed;
}

export function resolveFromRepo(...segments: string[]): string {
  return path.resolve(repoRoot, ...segments);
}

export function parseKeyValuePairs(values: readonly string[]): Record<string, string> {
  return Object.fromEntries(
    values.map((entry) => {
      const separatorIndex = entry.indexOf('=');
      if (separatorIndex === -1) {
        throw new Error(`Expected key=value pair, received "${entry}".`);
      }

      return [entry.slice(0, separatorIndex), entry.slice(separatorIndex + 1)];
    }),
  );
}
