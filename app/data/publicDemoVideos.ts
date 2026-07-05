export type PublicDemoVideoStatus = 'scripted' | 'recording' | 'published';

export type PublicDemoVideo = {
  id: string;
  featureId?: string;
  title: string;
  audience: string;
  durationSeconds: number;
  status: PublicDemoVideoStatus;
  assetUrl?: string;
  thumbnailUrl?: string;
  captionUrl?: string;
  transcriptUrl?: string;
  socialAssetUrl?: string;
  socialThumbnailUrl?: string;
  recordedAt?: string;
};

export function getPublicDemoVideoStatusLabel(status: PublicDemoVideoStatus): string {
  if (status === 'published') return 'Watch demo';
  if (status === 'recording') return 'Coming soon';
  return 'Preview demo';
}
