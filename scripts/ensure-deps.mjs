#!/usr/bin/env node
import { createRequire } from 'module';
import { spawnSync } from 'node:child_process';

const require = createRequire(import.meta.url);

const COMMAND_REQUIREMENTS = {
  dev: ['tiny-invariant'],
  lint: ['tiny-invariant', 'eslint', 'eslint-config-next'],
  test: ['tiny-invariant', 'tsx'],
};

const context = process.argv[2] && COMMAND_REQUIREMENTS[process.argv[2]] ? process.argv[2] : 'dev';
const requiredDependencies = Array.from(new Set(COMMAND_REQUIREMENTS[context] ?? []));

const missingDependencies = [];

for (const pkg of requiredDependencies) {
  try {
    require.resolve(pkg);
  } catch (error) {
    if (error?.code === 'MODULE_NOT_FOUND') {
      missingDependencies.push(pkg);
    } else {
      throw error;
    }
  }
}

if (missingDependencies.length === 0) {
  process.exit(0);
}

const formattedList = missingDependencies.join(', ');
// eslint-disable-next-line no-console
console.warn(`Missing required npm package${missingDependencies.length > 1 ? 's' : ''}: ${formattedList}`);

const hasAttemptedInstall = process.env.SPECIAL_WEDDING_SKIP_ENSURE === '1';

if (!hasAttemptedInstall) {
  // eslint-disable-next-line no-console
  console.warn('Attempting to install missing dependencies using "npm install"...');
  const installResult = spawnSync('npm', ['install'], {
    stdio: 'inherit',
    shell: process.platform === 'win32',
    env: {
      ...process.env,
      NODE_ENV: 'development',
      npm_config_production: 'false',
      SPECIAL_WEDDING_SKIP_ENSURE: '1',
    },
  });

  if (installResult.status !== 0) {
    // eslint-disable-next-line no-console
    console.error('Failed to install dependencies automatically. Please run "npm install" and re-run the command.');
    process.exit(installResult.status ?? 1);
  }

  const unresolved = [];
  for (const pkg of missingDependencies) {
    try {
      require.resolve(pkg);
    } catch (error) {
      if (error?.code === 'MODULE_NOT_FOUND') {
        unresolved.push(pkg);
      } else {
        throw error;
      }
    }
  }

  if (unresolved.length === 0) {
    // eslint-disable-next-line no-console
    console.log('Successfully installed missing dependencies. Continuing...');
    process.exit(0);
  }

  // eslint-disable-next-line no-console
  console.error(
    `The following packages are still missing after installation: ${unresolved.join(', ')}. Please install them manually.`
  );
  process.exit(1);
}

// eslint-disable-next-line no-console
console.error('Dependencies are missing and automatic installation was skipped. Run "npm install" and try again.');
process.exit(1);
