'use client';

import PlayCircle from 'lucide-react/dist/esm/icons/play-circle';
import { useState } from 'react';

import type { PublicDemoVideo } from '@/data/publicDemoVideos';
import { getPublicDemoVideoStatusLabel } from '@/data/publicDemoVideos';

import DemoVideoModal from './DemoVideoModal';

type DemoVideoLauncherVariant = 'hero' | 'outline' | 'link';

interface DemoVideoLauncherProps {
  demo: PublicDemoVideo;
  label?: string;
  variant?: DemoVideoLauncherVariant;
  className?: string;
}

function variantClasses(variant: DemoVideoLauncherVariant): string {
  if (variant === 'hero') {
    return 'inline-flex items-center justify-center gap-2 rounded-full border border-white/25 px-6 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-white/10';
  }

  if (variant === 'outline') {
    return 'inline-flex items-center justify-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm font-semibold text-white transition hover:border-wedding-rose/50 hover:text-wedding-rose';
  }

  return 'inline-flex items-center gap-1.5 text-sm font-semibold text-wedding-rose transition hover:text-wedding-blush';
}

export default function DemoVideoLauncher({
  demo,
  label,
  variant = 'link',
  className = '',
}: DemoVideoLauncherProps) {
  const [open, setOpen] = useState(false);
  const computedLabel = label ?? getPublicDemoVideoStatusLabel(demo.status);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={`${variantClasses(variant)} ${className}`.trim()}
        data-testid={`demo-launcher-${demo.id}`}
      >
        <PlayCircle className="h-4 w-4" aria-hidden="true" />
        <span>{computedLabel}</span>
      </button>
      <DemoVideoModal demo={demo} open={open} onClose={() => setOpen(false)} />
    </>
  );
}
