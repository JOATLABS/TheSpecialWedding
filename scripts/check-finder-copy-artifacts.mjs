#!/usr/bin/env node

import { execFileSync } from 'node:child_process';

const COPY_SUFFIX_PATTERN = /(^|\/)[^/]+ (?:[2-9]|[1-9]\d+)\.[^/]+$/;

function parseRoot(argv) {
  const rootIndex = argv.indexOf('--root');
  if (rootIndex === -1) {
    return process.cwd();
  }

  const root = argv[rootIndex + 1];
  if (!root) {
    throw new Error('Missing value for --root');
  }
  return root;
}

function listCandidateFiles(root) {
  const output = execFileSync(
    'git',
    ['-C', root, 'ls-files', '-co', '--exclude-standard', '-z'],
    {
      encoding: 'utf8',
    }
  );

  return output.split('\0').filter(Boolean);
}

function listDeletedTrackedFiles(root) {
  const output = execFileSync('git', ['-C', root, 'status', '--porcelain=v1', '-z'], {
    encoding: 'utf8',
  });

  const deleted = new Set();
  for (const entry of output.split('\0').filter(Boolean)) {
    const status = entry.slice(0, 2);
    if (status === ' D' || status === 'D ') {
      deleted.add(entry.slice(3));
    }
  }
  return deleted;
}

function findCopyArtifacts(files, deletedFiles) {
  return files
    .filter((file) => !deletedFiles.has(file))
    .filter((file) => COPY_SUFFIX_PATTERN.test(file))
    .sort();
}

function main() {
  const root = parseRoot(process.argv.slice(2));
  const artifacts = findCopyArtifacts(
    listCandidateFiles(root),
    listDeletedTrackedFiles(root)
  );

  if (artifacts.length === 0) {
    console.log('No Finder-style copy artifacts found.');
    return;
  }

  console.error('Finder-style copy artifacts found:');
  for (const artifact of artifacts) {
    console.error(`- ${artifact}`);
  }
  console.error(
    'Remove accidental duplicates or rename intentional files before committing.'
  );
  process.exit(1);
}

main();
