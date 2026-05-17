import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

const scriptPath = join(process.cwd(), 'scripts/check-finder-copy-artifacts.mjs');

function makeGitFixture(files: Record<string, string>): string {
  const root = mkdtempSync(join(tmpdir(), 'finder-copy-artifacts-'));

  execFileSync('git', ['init', '-q'], { cwd: root });
  for (const [path, body] of Object.entries(files)) {
    writeFileSync(join(root, path), body);
  }
  execFileSync('git', ['add', '.'], { cwd: root });

  return root;
}

describe('Finder copy artifact guard', () => {
  it('fails when a tracked file uses a space-number copy suffix', () => {
    const root = makeGitFixture({
      'canonical.ts': 'export const value = 1;\n',
      'canonical 2.ts': 'export const value = 1;\n',
    });

    try {
      const result = spawnSync(process.execPath, [scriptPath, '--root', root], {
        encoding: 'utf8',
      });

      assert.equal(result.status, 1);
      assert.match(result.stderr, /canonical 2\.ts/);
      assert.match(result.stderr, /Finder-style copy artifacts/);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it('fails when an untracked file uses a space-number copy suffix', () => {
    const root = makeGitFixture({
      'canonical.ts': 'export const value = 1;\n',
    });

    try {
      writeFileSync(join(root, 'canonical 2.ts'), 'export const value = 1;\n');

      const result = spawnSync(process.execPath, [scriptPath, '--root', root], {
        encoding: 'utf8',
      });

      assert.equal(result.status, 1);
      assert.match(result.stderr, /canonical 2\.ts/);
      assert.match(result.stderr, /Finder-style copy artifacts/);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it('passes when tracked filenames avoid Finder copy suffixes', () => {
    const root = makeGitFixture({
      'canonical.ts': 'export const value = 1;\n',
      'canonical-v2.ts': 'export const value = 2;\n',
    });

    try {
      const output = execFileSync(process.execPath, [scriptPath, '--root', root], {
        encoding: 'utf8',
      });

      assert.match(output, /No Finder-style copy artifacts found/);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it('passes while a tracked copy artifact is already deleted from the worktree', () => {
    const root = makeGitFixture({
      'canonical.ts': 'export const value = 1;\n',
      'canonical 2.ts': 'export const value = 1;\n',
    });

    try {
      execFileSync(
        'git',
        ['-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-q', '-m', 'initial'],
        { cwd: root }
      );
      rmSync(join(root, 'canonical 2.ts'), { force: true });

      const output = execFileSync(process.execPath, [scriptPath, '--root', root], {
        encoding: 'utf8',
      });

      assert.match(output, /No Finder-style copy artifacts found/);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});
