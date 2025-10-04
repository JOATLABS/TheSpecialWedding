#!/usr/bin/env node
import { createRequire } from 'module';

const require = createRequire(import.meta.url);

const requiredDependencies = ['tiny-invariant'];
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

if (missingDependencies.length > 0) {
  // eslint-disable-next-line no-console
  console.error(
    `Missing required npm package${missingDependencies.length > 1 ? 's' : ''}: ${missingDependencies.join(', ')}`
  );
  // eslint-disable-next-line no-console
  console.error(
    'Run "npm install" (or "npm install ' + missingDependencies.join(' ') + '") before starting the development server.'
  );
  process.exit(1);
}
