'use client';
import React, { useContext, useEffect, useState } from 'react';
import { WeddingContext } from '@/contexts/WeddingContext';
import { LandingLayout } from '@/components/landing-page/LandingLayout';
import { GalleryImage } from '@/types/landing';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export default function WeddingLandingPage() {
  const wedding = useContext(WeddingContext);
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchGallery() {
      try {
        const res = await fetch(`${API_URL}/gallery`, { cache: 'no-store' });
        if (!res.ok) throw new Error('Failed to fetch gallery');
        const data = await res.json();
        setImages(data.map((img: any) => ({ key: img.key, url: img.url })));
      } catch (err: any) {
        console.error(err);
        setError('Gallery could not be loaded.');
      }
    }

    fetchGallery();
  }, []);

  if (!wedding) return <p>Wedding not found</p>;
  if (error) return <p>{error}</p>;

  return <LandingLayout wedding={wedding} images={images} />;
}
