#!/usr/bin/env node
/**
 * Simple dependency checker for development environment
 * Ensures node_modules exists before starting the dev server
 */

import { existsSync } from 'fs';
import { join } from 'path';

const nodeModulesPath = join(process.cwd(), 'node_modules');

if (!existsSync(nodeModulesPath)) {
  console.error('❌ Error: node_modules not found!');
  console.error('Please run: npm install');
  process.exit(1);
}

console.log('✅ Dependencies verified');
