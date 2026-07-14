import type { Caption } from '@remotion/captions';

import type { DemoVideoExportFormat } from '../app/data/demoVideoProduction';

export type DemoVideoRemotionProps = {
  demoId: string;
  title: string;
  audience: string;
  rawVideoPath: string;
  narrationPath: string;
  captions: Caption[];
  format: DemoVideoExportFormat;
  durationSeconds: number;
};
