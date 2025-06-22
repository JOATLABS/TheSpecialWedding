'use client';
import React, { useContext, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { WeddingContext } from '@/contexts/WeddingContext';
import { LandingLayout } from '@/components/landing-page/LandingLayout';
import { GalleryImage } from '@/types/landing';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/admin";
const API_URL = API_BASE_URL.replace('/admin', ''); // Remove /admin for public endpoints

export default function WeddingLandingPage() {
  const wedding = useContext(WeddingContext);
  const params = useParams();
  const slug = params.slug as string;
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchGallery() {
      if (!slug) return;
      try {
        // Use the public gallery endpoint that returns images with URLs
        const res = await fetch(`${API_URL}/gallery?wedding_slug=${slug}`, { cache: 'no-store' });
        if (!res.ok) throw new Error('Failed to fetch gallery');
        const data = await res.json();
        setImages(data.map((img: any) => ({ key: img.key, url: img.url })));
      } catch (err: any) {
        console.error(err);
        setError('Gallery could not be loaded.');
      }
    }

    fetchGallery();
  }, [slug]);

  if (!wedding) return <p>Wedding not found</p>;
  if (error) return <p>{error}</p>;

  return <LandingLayout wedding={wedding} images={images} />;
}