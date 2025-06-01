// app/[slug]/gallery/page.tsx

import { Metadata } from 'next';
import Image from 'next/image';

type GalleryImage = {
  key: string;
  url: string;
};

export const metadata: Metadata = {
  title: 'Gallery - Wedding Memories',
  description: 'Browse through beautiful moments from the wedding celebration.',
};

async function fetchGallery(): Promise<GalleryImage[]> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/gallery`, {
    cache: 'no-store',
  });

  if (!res.ok) {
    throw new Error('Failed to fetch gallery images');
  }

  return res.json();
}

export default async function GalleryPage({
  params,
}: {
  params: { slug: string };
}) {
  const images = await fetchGallery();

  return (
    <section className="px-4 py-8 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold text-center mb-6">Photo Gallery</h1>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
        {images.map((img) => (
          <div key={img.key} className="relative w-full h-64 rounded overflow-hidden shadow">
            <Image
              src={img.url}
              alt="Wedding gallery"
              layout="fill"
              objectFit="cover"
              className="rounded"
            />
          </div>
        ))}
      </div>
    </section>
  );
}
