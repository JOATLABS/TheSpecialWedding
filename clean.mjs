#!/usr/bin/env node
/**
 * Cleans build artifacts and caches
 */

import { rmSync, existsSync } from 'fs';
import { join } from 'path';

const paths = ['.next', '.turbo'];

paths.forEach(p => {
  const fullPath = join(process.cwd(), p);
  if (existsSync(fullPath)) {
    console.log(`🗑️  Cleaning ${p}...`);
    rmSync(fullPath, { recursive: true, force: true });
  }
});

console.log('✨ Clean complete');
