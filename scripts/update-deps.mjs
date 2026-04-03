#!/usr/bin/env node
/**
 * update-deps.mjs
 *
 * Dependency maintenance script for the Wedding Web App.
 *
 * What it does:
 *   1. Removes known deprecated packages from package.json
 *   2. Aligns companion packages (e.g. eslint-config-next ↔ next)
 *   3. Runs `npm outdated --json` to discover stale versions
 *   4. Auto-updates safe semver-compatible (patch / minor) packages
 *   5. Reports major-version bumps that need manual review
 *   6. Cleans the Turbopack / Next.js cache so the next `npm run dev` starts fresh
 *
 * Usage:
 *   node scripts/update-deps.mjs            # interactive (default)
 *   node scripts/update-deps.mjs --dry-run  # show what would change, touch nothing
 *   node scripts/update-deps.mjs --auto     # apply safe updates without prompting
 */

import { readFileSync, writeFileSync, existsSync, rmSync } from 'fs';
import { join } from 'path';
import { execSync } from 'child_process';
import { createInterface } from 'readline';

// ──────────────────────────────────────────────
// Config
// ──────────────────────────────────────────────

const ROOT = process.cwd();
const PKG_PATH = join(ROOT, 'package.json');

/** Packages to remove outright — they are deprecated or superseded. */
const DEPRECATED_REMOVALS = {
  '@types/puppeteer': 'puppeteer ships its own types since v22',
  '@dnd-kit/utilities': 'merged into @dnd-kit/core in v6+',
  'victory-vendor': 'internal Victory package, not meant for direct use',
  'is-number': 'use native Number.isFinite() instead',
};

/**
 * Companion version alignment rules.
 * When the "source" package is present, the "target" should match its major.
 * Value is the npm dist-tag or version range to install.
 */
const ALIGNMENTS = [
  {
    source: 'next',
    target: 'eslint-config-next',
    description: 'eslint-config-next should match the Next.js major version',
    /** Resolve to the same major as `next` */
    resolve: (nextVersion) => `^${parseMajor(nextVersion)}.0.0`,
  },
];

// ──────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────

function parseMajor(semver) {
  return semver.replace(/^[\^~>=<]*/, '').split('.')[0];
}

function readPkg() {
  return JSON.parse(readFileSync(PKG_PATH, 'utf-8'));
}

function writePkg(pkg) {
  writeFileSync(PKG_PATH, JSON.stringify(pkg, null, 2) + '\n');
}

function run(cmd, opts = {}) {
  return execSync(cmd, { cwd: ROOT, encoding: 'utf-8', ...opts });
}

function semverBump(current, latest) {
  const c = current.replace(/^[\^~>=<]*/, '').split('.');
  const l = latest.split('.');
  if (c[0] !== l[0]) return 'major';
  if (c[1] !== l[1]) return 'minor';
  return 'patch';
}

async function confirm(question) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question(question + ' (y/N) ', (answer) => {
      rl.close();
      resolve(answer.trim().toLowerCase() === 'y');
    });
  });
}

// ──────────────────────────────────────────────
// Steps
// ──────────────────────────────────────────────

function stepRemoveDeprecated(pkg, dryRun) {
  const removed = [];
  for (const [name, reason] of Object.entries(DEPRECATED_REMOVALS)) {
    for (const section of ['dependencies', 'devDependencies']) {
      if (pkg[section]?.[name]) {
        removed.push({ name, section, version: pkg[section][name], reason });
        if (!dryRun) delete pkg[section][name];
      }
    }
  }
  return removed;
}

function stepAlignCompanions(pkg, dryRun) {
  const aligned = [];
  for (const rule of ALIGNMENTS) {
    const sourceVersion =
      pkg.dependencies?.[rule.source] || pkg.devDependencies?.[rule.source];
    if (!sourceVersion) continue;

    for (const section of ['dependencies', 'devDependencies']) {
      if (pkg[section]?.[rule.target]) {
        const newRange = rule.resolve(sourceVersion);
        const oldRange = pkg[section][rule.target];
        if (oldRange !== newRange) {
          aligned.push({
            name: rule.target,
            from: oldRange,
            to: newRange,
            reason: rule.description,
          });
          if (!dryRun) pkg[section][rule.target] = newRange;
        }
      }
    }
  }
  return aligned;
}

function stepFindOutdated() {
  try {
    // npm outdated returns exit code 1 when outdated deps exist
    run('npm outdated --json', { stdio: 'pipe' });
    return {};
  } catch (e) {
    try {
      return JSON.parse(e.stdout || '{}');
    } catch {
      return {};
    }
  }
}

function categoriseOutdated(outdated, pkg) {
  const safe = [];
  const breaking = [];
  const allDeps = { ...pkg.dependencies, ...pkg.devDependencies };

  for (const [name, info] of Object.entries(outdated)) {
    // Skip packages we already removed
    if (DEPRECATED_REMOVALS[name]) continue;

    const currentRange = allDeps[name];
    if (!currentRange) continue;

    const bump = semverBump(currentRange, info.latest);
    const entry = {
      name,
      current: info.current || 'unknown',
      wanted: info.wanted,
      latest: info.latest,
      bump,
      section: pkg.dependencies?.[name] ? 'dependencies' : 'devDependencies',
    };

    if (bump === 'major') {
      breaking.push(entry);
    } else {
      safe.push(entry);
    }
  }

  return { safe, breaking };
}

function stepApplySafe(pkg, safeUpdates, dryRun) {
  for (const dep of safeUpdates) {
    const prefix = pkg[dep.section][dep.name]?.startsWith('^')
      ? '^'
      : pkg[dep.section][dep.name]?.startsWith('~')
        ? '~'
        : '';
    if (!dryRun) {
      pkg[dep.section][dep.name] = `${prefix}${dep.latest}`;
    }
  }
}

function stepCleanCache(dryRun) {
  const dirs = [
    join(ROOT, '.next'),
    join(ROOT, 'node_modules', '.cache'),
  ];
  const cleaned = [];
  for (const dir of dirs) {
    if (existsSync(dir)) {
      cleaned.push(dir.replace(ROOT + '/', ''));
      if (!dryRun) rmSync(dir, { recursive: true, force: true });
    }
  }

  // Remove corrupted "dist 2" folder if present
  const dist2 = join(ROOT, 'node_modules', 'next', 'dist 2');
  if (existsSync(dist2)) {
    cleaned.push('node_modules/next/dist 2 (corrupted)');
    if (!dryRun) rmSync(dist2, { recursive: true, force: true });
  }

  return cleaned;
}

// ──────────────────────────────────────────────
// Main
// ──────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const auto = args.includes('--auto');

  console.log('\n🔍  Wedding Web App — Dependency Updater');
  console.log('─'.repeat(48));
  if (dryRun) console.log('   (dry-run mode — no changes will be made)\n');

  const pkg = readPkg();

  // Step 1 — Remove deprecated
  const removed = stepRemoveDeprecated(pkg, dryRun);
  if (removed.length) {
    console.log('\n🗑️  Deprecated packages to remove:');
    for (const r of removed) {
      console.log(`   - ${r.name} (${r.version}) — ${r.reason}`);
    }
  } else {
    console.log('\n✅  No deprecated packages found.');
  }

  // Step 2 — Align companions
  const aligned = stepAlignCompanions(pkg, dryRun);
  if (aligned.length) {
    console.log('\n🔗  Companion alignments:');
    for (const a of aligned) {
      console.log(`   - ${a.name}: ${a.from} → ${a.to} (${a.reason})`);
    }
  }

  // Write removals + alignments before running npm outdated
  if (!dryRun && (removed.length || aligned.length)) {
    writePkg(pkg);
  }

  // Step 3 — Find outdated
  console.log('\n📡  Checking npm registry for updates...');
  const outdated = stepFindOutdated();
  const { safe, breaking } = categoriseOutdated(outdated, pkg);

  // Step 4 — Safe updates
  if (safe.length) {
    console.log(`\n🟢  Safe updates (patch/minor) — ${safe.length} packages:`);
    for (const d of safe) {
      console.log(`   - ${d.name}: ${d.current} → ${d.latest} (${d.bump})`);
    }

    let proceed = auto;
    if (!auto && !dryRun) {
      proceed = await confirm('\n   Apply safe updates?');
    }

    if (proceed && !dryRun) {
      stepApplySafe(pkg, safe, false);
      writePkg(pkg);
      console.log('   ✅ package.json updated with safe versions.');
    }
  } else {
    console.log('\n✅  All patch/minor versions are current.');
  }

  // Step 5 — Report breaking
  if (breaking.length) {
    console.log(`\n🟡  Major version bumps (manual review needed) — ${breaking.length} packages:`);
    for (const d of breaking) {
      console.log(`   - ${d.name}: ${d.current} → ${d.latest}`);
    }
    console.log('\n   Run individual upgrades when ready:');
    for (const d of breaking) {
      const flag = d.section === 'devDependencies' ? ' --save-dev' : '';
      console.log(`     npm install ${d.name}@latest${flag}`);
    }
  }

  // Step 6 — Clean caches
  const cleaned = stepCleanCache(dryRun);
  if (cleaned.length) {
    console.log('\n🧹  Cleaned caches:');
    for (const c of cleaned) console.log(`   - ${c}`);
  }

  // Step 7 — Reinstall
  if (!dryRun && (removed.length || safe.length || aligned.length)) {
    console.log('\n📦  Running npm install...');
    try {
      const output = run('npm install 2>&1', { stdio: 'pipe' });
      const added = output.match(/added \d+ packages/)?.[0] || '';
      const removedPkgs = output.match(/removed \d+ packages/)?.[0] || '';
      const changed = output.match(/changed \d+ packages/)?.[0] || '';
      const parts = [added, removedPkgs, changed].filter(Boolean).join(', ');
      console.log(`   ✅ ${parts || 'up to date'}`);
    } catch (e) {
      console.error('   ⚠️  npm install had warnings — review output above.');
    }
  }

  // Summary
  console.log('\n' + '─'.repeat(48));
  const total = removed.length + safe.length + aligned.length;
  if (dryRun) {
    console.log(`📋  Dry run complete. ${total} changes would be applied.`);
  } else if (total === 0 && breaking.length === 0) {
    console.log('🎉  All dependencies are up to date!');
  } else {
    console.log(`✅  Done. ${total} updates applied${breaking.length ? `, ${breaking.length} major bumps need manual review.` : '.'}`);
  }
  console.log('');
}

main().catch((err) => {
  console.error('💥 update-deps failed:', err.message);
  process.exit(1);
});
