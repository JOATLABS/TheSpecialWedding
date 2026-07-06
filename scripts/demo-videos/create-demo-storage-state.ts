import fs from 'node:fs';
import path from 'node:path';

import { chromium, type BrowserContext } from 'playwright';

import { getRequiredValue, parseCliArgs, resolveFromRepo } from './cli';
import { assertPublicSafeStorageState } from './public-safe-storage';

async function login(
  context: BrowserContext,
  baseUrl: string,
  endpoint: string,
  email: string,
  password: string,
): Promise<void> {
  const url = new URL(endpoint, baseUrl).toString();
  const response = await context.request.post(url, {
    data: { email, password },
  });

  if (!response.ok()) {
    const body = await response.text().catch(() => '');
    throw new Error(`Login failed for ${email} at ${endpoint}: ${response.status()} ${body}`);
  }
}

async function main(): Promise<void> {
  const args = parseCliArgs(process.argv.slice(2));
  const baseUrl = args.values.get('base-url') ?? 'http://localhost:3100';
  const outputPath = path.resolve(
    args.values.get('output') ?? resolveFromRepo('output', 'demo-videos', 'state', 'demo-public-safe.json'),
  );

  const plannerEmail = args.values.get('planner-email') ?? process.env.DEMO_VIDEO_PLANNER_EMAIL ?? process.env.SMOKE_PLANNER_EMAIL;
  const plannerPassword = args.values.get('planner-password') ?? process.env.DEMO_VIDEO_PLANNER_PASSWORD ?? process.env.SMOKE_PLANNER_PASSWORD;
  const coupleEmail = args.values.get('couple-email') ?? process.env.DEMO_VIDEO_COUPLE_EMAIL ?? process.env.SMOKE_COUPLE_EMAIL;
  const couplePassword = args.values.get('couple-password') ?? process.env.DEMO_VIDEO_COUPLE_PASSWORD ?? process.env.SMOKE_COUPLE_PASSWORD;

  if (!plannerEmail || !plannerPassword) {
    throw new Error('Planner credentials are required. Pass --planner-email/--planner-password or SMOKE_PLANNER_*.');
  }
  if (!coupleEmail || !couplePassword) {
    throw new Error('Couple credentials are required. Pass --couple-email/--couple-password or SMOKE_COUPLE_*.');
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();

  await login(context, baseUrl, '/api/proxy/admin/token', plannerEmail, plannerPassword);
  await login(context, baseUrl, '/api/proxy/couple/login', coupleEmail, couplePassword);

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  await context.storageState({ path: outputPath });
  await context.close();
  await browser.close();

  if (!args.flags.has('allow-personal-state')) {
    assertPublicSafeStorageState(outputPath);
  }

  console.log(`Demo browser storage state written to ${outputPath}`);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
