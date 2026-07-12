"use client";

import type { PublicDemoVideo } from '@/data/publicDemoVideos';

import { PhaseOneProductStories } from './PhaseOneProductStories';

type FeatureShowcaseProps = {
  demoVideosByFeatureId: Record<string, PublicDemoVideo>;
};

export function FeatureShowcase({ demoVideosByFeatureId }: FeatureShowcaseProps) {
  return <PhaseOneProductStories demoVideosByFeatureId={demoVideosByFeatureId} />;
}
