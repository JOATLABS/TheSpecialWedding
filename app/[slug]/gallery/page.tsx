// app/[slug]/gallery/page.tsx

import { Metadata } from 'next';
import { getApiBaseUrl } from '@/utils/env';
import { GalleryGrid } from '@/components/GalleryGrid';
import { formatDate } from '@/utils/dateFormat';

type GalleryImage = {
  key: string;
  url: string;
};

export const metadata: Metadata = {
  title: 'Gallery - Wedding Memories',
  description: 'Browse through beautiful moments from the wedding celebration.',
};

async function fetchGallery(slug: string): Promise<GalleryImage[]> {
  const baseUrl = getApiBaseUrl();
  const apiUrl = baseUrl.replace('/admin', ''); // Remove /admin for public endpoints
  const res = await fetch(`${apiUrl}/gallery?wedding_slug=${slug}`, {
    cache: 'no-store',
  });

  if (!res.ok) {
    throw new Error('Failed to fetch gallery images');
  }

  return res.json();
}

async function fetchWedding(slug: string) {
  const base = getApiBaseUrl();
  const res = await fetch(`${base}/weddings/slug/${slug}`);
  if (!res.ok) return null;
  return res.json();
}

export default async function GalleryPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const [images, wedding] = await Promise.all([
    fetchGallery(slug),
    fetchWedding(slug)
  ]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with wedding info */}
      <div className="bg-wedding-navy text-white py-12">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            {wedding?.couple_names || "Wedding"} Gallery
          </h1>
          {wedding?.date && (
            <p className="text-xl text-blue-100">
              {formatDate(wedding.date, {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          )}
          {wedding?.venue && (
            <p className="text-lg text-blue-200 mt-2">{wedding.venue}</p>
          )}
        </div>
      </div>

      {/* Gallery */}
      <section className="px-4 py-12 max-w-7xl mx-auto">
        {images.length > 0 ? (
          <>
            <p className="text-center text-gray-600 mb-8">
              {images.length} photo{images.length !== 1 ? 's' : ''}
            </p>
            <GalleryGrid images={images} />
          </>
        ) : (
          <div className="text-center py-24">
            <div className="text-gray-400">
              <svg className="mx-auto h-24 w-24 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <h3 className="text-xl font-medium text-gray-600 mb-2">No photos yet</h3>
            <p className="text-gray-500">Photos from the wedding will appear here soon!</p>
          </div>
        )}
      </section>

      {/* Back to home */}
      <div className="text-center pb-12">
        <a 
          href={`/${slug}`}
          className="inline-flex items-center bg-wedding-rose text-white px-6 py-3 rounded-lg font-semibold hover:bg-opacity-90 transition-colors"
        >
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Wedding Page
        </a>
      </div>
    </div>
  );
}
