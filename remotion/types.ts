import type { DemoVideoExportFormat } from '../app/data/demoVideoProduction';
import type { NarrationWindow } from './musicDucking';

export type DemoVideoRemotionProps = {
  demoId: string;
  title: string;
  audience: string;
  phaseOnePillar?: string;
  socialOutcome?: string;
  rawVideoPath: string;
  narrationPath: string;
  musicPath?: string;
  narrationWindows?: readonly NarrationWindow[];
  format: DemoVideoExportFormat;
  durationSeconds: number;
};
