'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import PageHeader from '../../components/PageHeader';
import WeddingPicker from '../../components/WeddingPicker';
import { toast } from 'sonner';
import { Upload, Images, ChevronDown, FolderOpen } from 'lucide-react';
import {
  fetchGalleryImagesForWedding,
  type GalleryImage,
} from './galleryImageListClient';
import { uploadGalleryFileViaPresignedUrl } from './galleryUploadClient';
import { getGalleryImageAlt, getGalleryImageLabel } from './galleryImagePresentation';

interface Wedding {
  id?: string;
  _id?: string;
  couple_names: string;
  date: string;
  slug: string;
  featured_image?: string;
}

export default function AdminGalleryUploadPage() {
  const { token } = useAdmin();
  const router = useRouter();

  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWedding, setSelectedWedding] = useState<string>('');
  const [selectedWeddingSlug, setSelectedWeddingSlug] = useState<string>('');
  const [uploadedImages, setUploadedImages] = useState<GalleryImage[]>([]);
  const [loadingImages, setLoadingImages] = useState(false);
  const [galleryLoadError, setGalleryLoadError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'upload' | 'manage'>('upload');
  const [currentFeaturedImage, setCurrentFeaturedImage] = useState<string | null>(null);
  const [selectedFolder, setSelectedFolder] = useState<string>('gallery');
  const galleryLoadRequestRef = useRef(0);

  // redirect if not logged in
  useEffect(() => {
    if (!token) router.push('/admin/login');
  }, [token, router]);

  const fetchWeddings = useCallback(async () => {
    if (!token) return;
    try {
      const baseUrl = getApiBaseUrl();
      // Use the authenticated planner endpoint to get assigned weddings
      const response = await fetch(`${baseUrl}/admin/planner/weddings`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      const data = await response.json();
      setWeddings(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error('Failed to load weddings');
    }
  }, [token]);

  // fetch weddings when token is available
  useEffect(() => {
    if (token) {
      fetchWeddings();
    }
  }, [token, fetchWeddings]);

  const handleWeddingChange = (weddingId: string) => {
    setSelectedWedding(weddingId);
    const wedding = weddings.find(w => (w.id || w._id) === weddingId);
    const nextWeddingSlug = wedding?.slug || '';
    if (nextWeddingSlug !== selectedWeddingSlug) {
      setUploadedImages([]);
    }
    setGalleryLoadError(null);
    setSelectedWeddingSlug(nextWeddingSlug);
    setCurrentFeaturedImage(wedding?.featured_image || null);
    if (wedding?.slug) {
      void fetchUploadedImages(wedding.slug);
    } else {
      galleryLoadRequestRef.current += 1;
      setLoadingImages(false);
    }
  };

  const fetchUploadedImages = async (weddingSlug: string) => {
    const requestId = ++galleryLoadRequestRef.current;
    setLoadingImages(true);
    setGalleryLoadError(null);
    try {
      const images = await fetchGalleryImagesForWedding({
        baseUrl: getApiBaseUrl(),
        token: token || '',
        weddingSlug,
      });
      if (requestId !== galleryLoadRequestRef.current) return;
      setUploadedImages(images);
    } catch (err: unknown) {
      if (requestId !== galleryLoadRequestRef.current) return;
      const message = err instanceof Error ? err.message : 'Gallery image loading failed';
      setGalleryLoadError(message);
      toast.error('Failed to load gallery images');
    } finally {
      if (requestId === galleryLoadRequestRef.current) {
        setLoadingImages(false);
      }
    }
  };

  const handleDeleteImage = async (imageKey: string) => {
    if (!confirm('Are you sure you want to delete this image?')) return;

    try {
      const baseUrl = getApiBaseUrl();
      console.log('Deleting image with key:', imageKey);

      const response = await fetch(
        `${baseUrl}/admin/gallery?key=${encodeURIComponent(imageKey)}`,
        {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (response.ok) {
        toast.success('Image deleted successfully');
        // Refresh the image list
        if (selectedWeddingSlug) {
          fetchUploadedImages(selectedWeddingSlug);
        }
      } else {
        const errorText = await response.text();
        console.error('Delete failed:', response.status, errorText);
        throw new Error(`Delete failed: ${response.status}`);
      }
    } catch (err: any) {
      console.error('Delete error:', err);
      toast.error(`Failed to delete: ${err.message}`);
    }
  };

  // generate previews
  useEffect(() => {
    if (!files.length) return setPreviews([]);
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [files]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) =>
    setFiles(Array.from(e.target.files || []));

  const handleUpload = async () => {
    if (!token || !files.length || !selectedWeddingSlug) {
      toast.error('Please select a wedding and files to upload');
      return;
    }
    setUploading(true);
    try {
      let successCount = 0;
      const baseUrl = getApiBaseUrl();
      for (const file of files) {
        await uploadGalleryFileViaPresignedUrl({
          baseUrl,
          token,
          file,
          weddingSlug: selectedWeddingSlug,
          folder: selectedFolder,
        });
        successCount++;
      }
      toast.success(`Successfully uploaded ${successCount} image${successCount > 1 ? 's' : ''}`);
      setFiles([]);
      // Refresh the uploaded images list
      if (selectedWeddingSlug) {
        fetchUploadedImages(selectedWeddingSlug);
      }
    } catch (err: any) {
      toast.error(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Gallery Management"
        description="Upload and manage wedding photos"
      />

        {/* Wedding picker — shared compact pill (see WeddingPicker.tsx).
            handleWeddingChange wires the slug + featured-image side effects;
            picker just feeds the wedding id through. */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500 dark:text-gray-400">Wedding:</span>
          <WeddingPicker
            options={weddings.map((w) => ({
              id: (w.id || w._id) as string,
              label: `${w.couple_names} — ${w.date}`,
            }))}
            value={selectedWedding}
            onChange={handleWeddingChange}
            placeholder="Choose a wedding…"
          />
        </div>

        {selectedWedding && (
          <>
            {/* Tabs */}
            <div className="flex gap-3 mb-8 p-1.5 bg-slate-100 dark:bg-slate-800/50 rounded-xl w-fit">
              <button
                onClick={() => setActiveTab('upload')}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all duration-200 ${
                  activeTab === 'upload'
                    ? 'bg-white dark:bg-slate-700 text-wedding-sage shadow-md'
                    : 'text-gray-600 dark:text-gray-400 hover:text-wedding-navy dark:hover:text-gray-200'
                }`}
              >
                <Upload className="w-4 h-4" />
                Upload Images
              </button>
              <button
                onClick={() => setActiveTab('manage')}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all duration-200 ${
                  activeTab === 'manage'
                    ? 'bg-white dark:bg-slate-700 text-wedding-sage shadow-md'
                    : 'text-gray-600 dark:text-gray-400 hover:text-wedding-navy dark:hover:text-gray-200'
                }`}
              >
                <Images className="w-4 h-4" />
                Manage Gallery
                {uploadedImages.length > 0 && (
                  <span className="ml-1 px-2 py-0.5 text-xs bg-wedding-sage/10 text-wedding-sage rounded-full">
                    {uploadedImages.length}
                  </span>
                )}
              </button>
            </div>

            {/* Upload Tab */}
            {activeTab === 'upload' && (
              <Card className="shadow-lg border-0 overflow-hidden">
                <div className="space-y-6 p-8">
                  {/* Folder Selection */}
                  <div>
                    <label className="flex items-center gap-2 text-sm font-semibold text-wedding-navy dark:text-gray-200 mb-3">
                      <FolderOpen className="w-4 h-4 text-wedding-sage" />
                      Upload to Folder
                    </label>
                    <div className="relative mb-4">
                      <select
                        value={selectedFolder}
                        onChange={(e) => setSelectedFolder(e.target.value)}
                        className="w-full px-5 py-4 pr-12 border border-slate-200 dark:border-slate-600 rounded-xl bg-white dark:bg-slate-800 text-gray-900 dark:text-gray-100 appearance-none cursor-pointer focus:ring-2 focus:ring-wedding-sage/50 focus:border-wedding-sage hover:border-wedding-sage/50 transition-all duration-200 shadow-sm text-base font-medium"
                      >
                        <option value="gallery">Public Gallery</option>
                        <option value="our-story">Our Story</option>
                        <option value="wedding-party">Wedding Party</option>
                      </select>
                      <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800">
                        <p className="text-sm font-medium text-blue-700 dark:text-blue-300">Public Gallery</p>
                        <p className="text-xs text-blue-600/70 dark:text-blue-400/70 mt-0.5">Photos visible to all guests</p>
                      </div>
                      <div className="p-3 rounded-lg bg-pink-50 dark:bg-pink-900/20 border border-pink-100 dark:border-pink-800">
                        <p className="text-sm font-medium text-pink-700 dark:text-pink-300">Our Story</p>
                        <p className="text-xs text-pink-600/70 dark:text-pink-400/70 mt-0.5">Couple photos for story section</p>
                      </div>
                      <div className="p-3 rounded-lg bg-purple-50 dark:bg-purple-900/20 border border-purple-100 dark:border-purple-800">
                        <p className="text-sm font-medium text-purple-700 dark:text-purple-300">Wedding Party</p>
                        <p className="text-xs text-purple-600/70 dark:text-purple-400/70 mt-0.5">Individual member photos</p>
                      </div>
                    </div>
                  </div>

                  {/* File Input */}
                  <div className="border-2 border-dashed border-slate-200 dark:border-slate-600 rounded-xl p-6 text-center hover:border-wedding-sage/50 transition-colors">
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={handleFileChange}
                      className="w-full text-sm file:mr-4 file:py-2.5 file:px-5
                                 file:rounded-full file:border-0
                                 file:text-sm file:font-semibold
                                 file:bg-wedding-sage file:text-white
                                 hover:file:bg-wedding-sage/90 file:cursor-pointer
                                 file:transition-colors file:shadow-md"
                    />
                    <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                      Drag and drop or click to select multiple images
                    </p>
                  </div>

                  {/* Preview Grid */}
                  {previews.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-wedding-navy dark:text-gray-200 mb-3">
                        Ready to upload ({previews.length} image{previews.length > 1 ? 's' : ''})
                      </p>
                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                        {previews.map((url, i) => (
                          <div
                            key={i}
                            className="relative aspect-square overflow-hidden rounded-xl shadow-lg group"
                          >
                            <Image
                              src={url}
                              alt={`Preview ${i + 1}`}
                              fill
                              className="object-cover transition-transform group-hover:scale-105"
                              sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
                            />
                            <div className="absolute inset-0 bg-gradient-to-t from-black/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                            <button
                              type="button"
                              onClick={() => {
                                setFiles((f) => f.filter((_, idx) => idx !== i));
                                toast.success('Removed from upload queue');
                              }}
                              className="absolute top-2 right-2 bg-red-600/90 backdrop-blur-sm
                                         text-white text-xs px-3 py-1.5 rounded-lg
                                         hover:bg-red-700 transition-all opacity-0 group-hover:opacity-100 shadow-lg"
                            >
                              Remove
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <Button
                    onClick={handleUpload}
                    disabled={!files.length || uploading || !selectedWedding}
                    className="w-full py-4 text-base font-semibold"
                  >
                    {uploading ? (
                      <span className="flex items-center justify-center gap-2">
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Uploading...
                      </span>
                    ) : (
                      <span className="flex items-center justify-center gap-2">
                        <Upload className="w-5 h-5" />
                        Upload Images
                      </span>
                    )}
                  </Button>

                  {!selectedWedding && (
                    <p className="text-sm text-gray-500 dark:text-gray-400 text-center bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-800 rounded-lg p-3">
                      Please select a wedding above before uploading images
                    </p>
                  )}
                </div>
              </Card>
            )}

            {/* Gallery Management Tab */}
            {activeTab === 'manage' && (
              <Card className="shadow-lg border-0 overflow-hidden">
                <div className="p-8">
                  <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100 mb-6">
                    Uploaded Images for {weddings.find(w => (w.id || w._id) === selectedWedding)?.couple_names}
                  </h2>

                  {loadingImages ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="animate-spin h-8 w-8 border-4 border-wedding-sage border-t-transparent rounded-full"></div>
                      <span className="ml-3 text-wedding-navy dark:text-gray-300">Loading images...</span>
                    </div>
                  ) : galleryLoadError ? (
                    <div
                      role="alert"
                      className="rounded-xl border border-red-200 bg-red-50 px-6 py-8 text-center dark:border-red-900/60 dark:bg-red-950/30"
                    >
                      <p className="text-lg font-semibold text-red-800 dark:text-red-200">
                        Gallery images are temporarily unavailable
                      </p>
                      <p className="mt-2 text-sm text-red-700 dark:text-red-300">
                        No partial folder result was shown. Try again to load the complete gallery.
                      </p>
                      <button
                        type="button"
                        onClick={() => void fetchUploadedImages(selectedWeddingSlug)}
                        className="mt-4 rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-red-800"
                      >
                        Try again
                      </button>
                    </div>
                  ) : uploadedImages.length === 0 ? (
                    <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                      <p className="text-lg">No images uploaded yet</p>
                      <p className="text-sm mt-2">Switch to Upload tab to add some images</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                      {uploadedImages.map((image, index) => {
                        const imageKey = image.key || image.filename;
                        const isFeatured = Boolean(imageKey) && currentFeaturedImage === imageKey;
                        return (
                          <div key={index} className="relative group">
                            <div className={`relative aspect-square overflow-hidden rounded-lg shadow-lg bg-gray-100 dark:bg-slate-700 ${isFeatured ? 'ring-4 ring-purple-600' : ''}`}>
                              <Image
                                src={image.url || image.file_url || '#'}
                                alt={getGalleryImageAlt(image, index)}
                                fill
                                className="object-cover transition-transform group-hover:scale-105"
                                sizes="(min-width: 1024px) 25vw, (min-width: 768px) 33vw, 50vw"
                                onError={(event) => {
                                  event.currentTarget.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlPC90ZXh0Pjwvc3ZnPg==';
                                }}
                              />
                              {isFeatured && (
                                <div className="absolute top-0 left-0 right-0 bg-purple-600 text-white text-xs px-2 py-1 text-center">
                                  <span className="flex items-center justify-center gap-1">
                                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                    </svg>
                                    Featured Background
                                  </span>
                                </div>
                              )}
                            </div>

                          {/* Image Info */}
                          <div className="mt-2">
                            <p className="text-xs text-gray-600 dark:text-gray-400 truncate">
                              {getGalleryImageLabel(image, index)}
                            </p>
                            <div className="flex items-center gap-2 mt-1">
                              {/* Folder Badge */}
                              <span className={`text-xs px-2 py-0.5 rounded-full ${
                                image.key?.startsWith('gallery/') ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300' :
                                image.key?.startsWith('our-story/') ? 'bg-pink-100 dark:bg-pink-900/50 text-pink-700 dark:text-pink-300' :
                                image.key?.startsWith('wedding-party/') ? 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300' :
                                'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                              }`}>
                                {image.key?.startsWith('gallery/') ? 'Gallery' :
                                 image.key?.startsWith('our-story/') ? 'Our Story' :
                                 image.key?.startsWith('wedding-party/') ? 'Wedding Party' :
                                 'Unknown'}
                              </span>
                              {image.size && (
                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                  {(image.size / 1024).toFixed(1)} KB
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Delete Button */}
                          {imageKey && (
                            <button
                              onClick={() => handleDeleteImage(imageKey)}
                              className="absolute top-2 right-2 bg-red-600/90 backdrop-blur-sm text-white text-xs px-3 py-1.5 rounded-lg hover:bg-red-700 transition-colors opacity-0 group-hover:opacity-100 shadow-lg z-10"
                            >
                              Delete
                            </button>
                          )}

                          {/* Copy URL Button */}
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(image.url || image.file_url || '');
                              toast.success('URL copied to clipboard');
                            }}
                            className="absolute top-2 left-2 bg-wedding-sage/90 backdrop-blur-sm text-white text-xs px-3 py-1.5 rounded-lg hover:bg-wedding-rose transition-colors opacity-0 group-hover:opacity-100 shadow-lg z-10"
                          >
                            Copy URL
                          </button>

                          {/* Set as Featured Button */}
                          {imageKey && (
                            <button
                              onClick={async () => {
                                try {
                                  const baseUrl = getApiBaseUrl();
                                  const response = await fetch(`${baseUrl}/admin/weddings/${selectedWedding}`, {
                                    method: 'PUT',
                                    headers: {
                                      'Authorization': `Bearer ${token}`,
                                      'Content-Type': 'application/json',
                                    },
                                    body: JSON.stringify({ featured_image: imageKey }),
                                  });

                                  if (!response.ok) {
                                    throw new Error('Failed to set featured image');
                                  }

                                  toast.success('Featured background updated');
                                  setCurrentFeaturedImage(imageKey);
                                } catch (err: unknown) {
                                  const message = err instanceof Error ? err.message : 'Unknown error';
                                  toast.error(`Failed to update: ${message}`);
                                }
                              }}
                              className="absolute bottom-2 left-2 right-2 bg-purple-600/90 backdrop-blur-sm text-white text-xs px-3 py-1.5 rounded-lg hover:bg-purple-700 transition-colors opacity-0 group-hover:opacity-100 shadow-lg z-20"
                            >
                              Set as Background
                            </button>
                          )}
                        </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Gallery Stats */}
                  {uploadedImages.length > 0 && (
                    <div className="mt-6 p-4 bg-gray-50 dark:bg-slate-700/50 rounded-lg">
                      <div className="flex justify-between items-center text-sm text-wedding-navy dark:text-gray-300">
                        <span>Total Images: {uploadedImages.length}</span>
                        <span>Wedding: {selectedWeddingSlug}</span>
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            )}
          </>
        )}
    </div>
  );
}
