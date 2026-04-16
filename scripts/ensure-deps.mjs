#!/usr/bin/env node
/**
 * Frontend dependency integrity guard for local development and CI.
 * Verifies the expected direct packages, local binaries, and npm tree health
 * before running scripts that depend on the Next.js toolchain.
 */

import { execFileSync } from 'node:child_process';
import { accessSync, constants, existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const cwd = process.cwd();
const args = new Set(process.argv.slice(2));
const doctorMode = args.has('--doctor');
const nodeModulesPath = join(cwd, 'node_modules');
const packageLockPath = join(cwd, 'package-lock.json');
const packageJsonPath = join(cwd, 'package.json');
const packageJson = JSON.parse(readFileSync(packageJsonPath, 'utf8'));
const directPackages = Object.keys({
  ...(packageJson.dependencies ?? {}),
  ...(packageJson.devDependencies ?? {}),
}).sort();
const requiredBins = ['next', 'eslint', 'tsx', 'tsc'];
const supportedNodeMin = [20, 9, 0];
const supportedNodeMaxExclusive = [25, 0, 0];
const supportedNodeMajors = new Set([20, 24]);
const supportedNpmMin = [10, 0, 0];
const ignorableTreeProblemPatterns = [
  /^extraneous: @emnapi\/runtime@/,
];

function parseVersion(raw) {
  const [major = '0', minor = '0', patch = '0'] = raw.split('.');
  return [Number(major), Number(minor), Number(patch)];
}

function compareVersions(left, right) {
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    const leftPart = left[index] ?? 0;
    const rightPart = right[index] ?? 0;
    if (leftPart !== rightPart) {
      return leftPart > rightPart ? 1 : -1;
    }
  }

  return 0;
}

function formatVersion(version) {
  return version.join('.');
}

function summarizeList(values, limit = 8) {
  if (values.length <= limit) {
    return values.join(', ');
  }

  return `${values.slice(0, limit).join(', ')}, and ${values.length - limit} more`;
}

function getNpmVersion() {
  const userAgent = process.env.npm_config_user_agent ?? '';
  const match = userAgent.match(/npm\/([0-9]+(?:\.[0-9]+){0,2})/);

  if (match) {
    return match[1];
  }

  return execFileSync('npm', ['--version'], {
    cwd,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'ignore'],
  }).trim();
}

function getMissingDirectPackages() {
  return directPackages.filter((packageName) => {
    const packagePath = join(nodeModulesPath, ...packageName.split('/'), 'package.json');
    return !existsSync(packagePath);
  });
}

function getMissingBins() {
  const platformSuffix = process.platform === 'win32' ? '.cmd' : '';
  return requiredBins.filter((binaryName) => {
    const binaryPath = join(nodeModulesPath, '.bin', `${binaryName}${platformSuffix}`);
    try {
      accessSync(binaryPath, constants.X_OK);
      return false;
    } catch {
      return true;
    }
  });
}

function getNpmTreeProblems() {
  if (!existsSync(nodeModulesPath)) {
    return [];
  }

  try {
    const output = execFileSync('npm', ['ls', '--depth=0', '--json'], {
      cwd,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    return JSON.parse(output).problems ?? [];
  } catch (error) {
    const output = error.stdout?.toString() || error.stderr?.toString() || '';

    if (!output) {
      return ['npm ls --depth=0 --json failed before producing diagnostic output'];
    }

    try {
      return JSON.parse(output).problems ?? ['npm ls --depth=0 reported an unknown dependency issue'];
    } catch {
      return ['npm ls --depth=0 produced unreadable output'];
    }
  }
}

function printFailure(issues, warnings, treeProblems) {
  console.error(`❌ ${doctorMode ? 'Dependency doctor failed.' : 'Dependency preflight failed.'}`);
  console.error('');

  for (const issue of issues) {
    console.error(`- ${issue}`);
  }

  if (warnings.length > 0) {
    console.error('');
    console.error('Warnings:');
    for (const warning of warnings) {
      console.error(`- ${warning}`);
    }
  }

  if (treeProblems.length > 0) {
    console.error('');
    console.error('npm reported dependency tree problems:');
    for (const problem of treeProblems.slice(0, 12)) {
      console.error(`- ${problem}`);
    }

    if (treeProblems.length > 12) {
      console.error(`- ...and ${treeProblems.length - 12} more`);
    }
  }

  console.error('');
  console.error('Recovery (npm-only):');
  console.error('1. rm -rf node_modules');
  console.error('2. npm ci');
  console.error('3. npm run deps:doctor');
  console.error('');
  console.error('If you intentionally changed dependencies, run `npm install`, commit the updated `package-lock.json`, and rerun `npm run deps:doctor`.');

  process.exit(1);
}

const issues = [];
const warnings = [];
const currentNodeVersion = parseVersion(process.versions.node);

if (compareVersions(currentNodeVersion, supportedNodeMin) < 0 || compareVersions(currentNodeVersion, supportedNodeMaxExclusive) >= 0) {
  issues.push(
    `Unsupported Node.js ${process.versions.node}. Expected a version in the package.json engines range >=${formatVersion(supportedNodeMin)} <${formatVersion(supportedNodeMaxExclusive)}.`,
  );
} else if (!supportedNodeMajors.has(currentNodeVersion[0])) {
  warnings.push(
    `Node.js ${process.versions.node} satisfies package.json engines, but this repo is only validated on Node 20.x and Node 24.x.`,
  );
}

let npmVersion = null;

try {
  npmVersion = getNpmVersion();
  if (compareVersions(parseVersion(npmVersion), supportedNpmMin) < 0) {
    issues.push(`Unsupported npm ${npmVersion}. Expected npm >=${formatVersion(supportedNpmMin)}.`);
  }
} catch {
  issues.push('Unable to determine npm version. Run scripts through npm 10+.');
}

if (!existsSync(packageLockPath)) {
  issues.push('Missing canonical lockfile `package-lock.json`.');
}

if (!existsSync(nodeModulesPath)) {
  issues.push('Missing `node_modules`. Install dependencies with `npm ci`.');
}

const missingPackages = getMissingDirectPackages();
if (missingPackages.length > 0) {
  issues.push(`Missing direct packages: ${summarizeList(missingPackages)}.`);
}

const missingBins = getMissingBins();
if (missingBins.length > 0) {
  issues.push(`Missing local binaries from node_modules/.bin: ${missingBins.join(', ')}.`);
}

const rawTreeProblems = getNpmTreeProblems();
const ignoredTreeProblems = rawTreeProblems.filter((problem) =>
  ignorableTreeProblemPatterns.some((pattern) => pattern.test(problem)),
);
const treeProblems = rawTreeProblems.filter((problem) => !ignoredTreeProblems.includes(problem));

if (ignoredTreeProblems.length > 0) {
  warnings.push(
    `Ignoring known npm optional-dependency noise: ${ignoredTreeProblems.join('; ')}.`,
  );
}

if (treeProblems.length > 0) {
  issues.push('npm detected dependency tree drift between `package.json`, `package-lock.json`, and `node_modules`.');
}

if (issues.length > 0) {
  printFailure(issues, warnings, treeProblems);
}

if (warnings.length > 0) {
  console.warn(`⚠️ ${warnings.join(' ')}`);
}

console.log(`✅ ${doctorMode ? 'Dependency doctor passed.' : 'Dependency preflight passed.'}`);
