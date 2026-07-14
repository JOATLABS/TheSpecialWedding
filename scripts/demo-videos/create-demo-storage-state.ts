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
  const plannerOutputPath = path.resolve(
    args.values.get('planner-output')
      ?? resolveFromRepo('output', 'demo-videos', 'state', 'demo-planner.json'),
  );
  const coupleOutputPath = path.resolve(
    args.values.get('couple-output')
      ?? resolveFromRepo('output', 'demo-videos', 'state', 'demo-couple.json'),
  );
  const publicOutputPath = path.resolve(
    args.values.get('public-output')
      ?? resolveFromRepo('output', 'demo-videos', 'state', 'demo-public.json'),
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
  try {
    const plannerContext = await browser.newContext();
    await login(plannerContext, baseUrl, '/api/proxy/admin/token', plannerEmail, plannerPassword);
    fs.mkdirSync(path.dirname(plannerOutputPath), { recursive: true });
    await plannerContext.storageState({ path: plannerOutputPath });
    await plannerContext.close();

    const coupleContext = await browser.newContext();
    await login(coupleContext, baseUrl, '/api/proxy/couple/login', coupleEmail, couplePassword);
    fs.mkdirSync(path.dirname(coupleOutputPath), { recursive: true });
    await coupleContext.storageState({ path: coupleOutputPath });
    await coupleContext.close();

    const publicContext = await browser.newContext();
    fs.mkdirSync(path.dirname(publicOutputPath), { recursive: true });
    await publicContext.storageState({ path: publicOutputPath });
    await publicContext.close();
  } finally {
    await browser.close();
  }

  if (!args.flags.has('allow-personal-state')) {
    for (const outputPath of [plannerOutputPath, coupleOutputPath, publicOutputPath]) {
      assertPublicSafeStorageState(outputPath);
    }
  }

  console.log(`Planner demo state written to ${plannerOutputPath}`);
  console.log(`Couple demo state written to ${coupleOutputPath}`);
  console.log(`Public demo state written to ${publicOutputPath}`);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
