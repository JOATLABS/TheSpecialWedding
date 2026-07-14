import type { DemoVideoExportFormat } from '../app/data/demoVideoProduction';

export type DemoVideoRemotionProps = {
  demoId: string;
  title: string;
  audience: string;
  phaseOnePillar?: string;
  socialOutcome?: string;
  rawVideoPath: string;
  narrationPath: string;
  format: DemoVideoExportFormat;
  durationSeconds: number;
};
