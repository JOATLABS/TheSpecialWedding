'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/button';

interface Wedding {
  id?: string;
  _id?: string;
  couple_names: string;
  date: string;
  slug: string;
  featured_image?: string;
}

export default function AdminGalleryUploadPage() {
  const { token, logout } = useAdmin();
  const router = useRouter();

  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<string>('');
  const [previews, setPreviews] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWedding, setSelectedWedding] = useState<string>('');
  const [selectedWeddingSlug, setSelectedWeddingSlug] = useState<string>('');
  const [uploadedImages, setUploadedImages] = useState<any[]>([]);
  const [loadingImages, setLoadingImages] = useState(false);
  const [activeTab, setActiveTab] = useState<'upload' | 'manage'>('upload');
  const [currentFeaturedImage, setCurrentFeaturedImage] = useState<string | null>(null);
  const [selectedFolder, setSelectedFolder] = useState<string>('gallery');

  // redirect if not logged in
  useEffect(() => {
    if (!token) router.push('/admin/login');
  }, [token, router]);

  // fetch weddings (only when token is available)
  useEffect(() => {
    if (token) {
      fetchWeddings();
    }
  }, [token]);

  const fetchWeddings = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL!;
      const response = await fetch(`${baseUrl}/admin/planner/weddings`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      const data = await response.json();
      setWeddings(Array.isArray(data) ? data : []);
    } catch (err) {
      setStatus('Failed to load weddings');
    }
  };

  const handleWeddingChange = (weddingId: string) => {
    setSelectedWedding(weddingId);
    const wedding = weddings.find(w => (w.id || w._id) === weddingId);
    setSelectedWeddingSlug(wedding?.slug || '');
    setCurrentFeaturedImage(wedding?.featured_image || null);
    if (wedding?.slug) {
      fetchUploadedImages(wedding.slug);
    }
  };

  const fetchUploadedImages = async (weddingSlug: string) => {
    setLoadingImages(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL!;
      
      // Fetch from all folders
      const folders = ['gallery', 'our-story', 'wedding-party'];
      const allImages = [];
      
      for (const folder of folders) {
        const response = await fetch(
          `${baseUrl}/admin/gallery/list?prefix=${folder}/${weddingSlug}/`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        if (response.ok) {
          const data = await response.json();
          allImages.push(...(Array.isArray(data) ? data : []));
        }
      }
      
      console.log('Fetched all images:', allImages);
      setUploadedImages(allImages);
    } catch (err) {
      console.error('Failed to fetch images:', err);
      setUploadedImages([]);
    } finally {
      setLoadingImages(false);
    }
  };

  const handleDeleteImage = async (imageKey: string) => {
    if (!confirm('Are you sure you want to delete this image?')) return;
    
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL!;
      console.log('Deleting image with key:', imageKey);
      
      const response = await fetch(
        `${baseUrl}/admin/gallery?key=${encodeURIComponent(imageKey)}`,
        {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      
      if (response.ok) {
        setStatus((s) => `${s}Deleted ${imageKey}\n`);
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
      setStatus(`Error: ${err.message}`);
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
      setStatus('Error: Please select a wedding and files to upload');
      return;
    }
    setUploading(true);
    setStatus('');
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('wedding_slug', selectedWeddingSlug);
        fd.append('folder', selectedFolder);
        
        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL!;
        const res = await fetch(
          `${baseUrl}/admin/gallery/upload`,
          {
            method: 'POST',
            body: fd,
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        if (!res.ok) {
          const errorData = await res.json();
          throw new Error(errorData.detail || 'Upload failed');
        }
        const result = await res.json();
        setStatus((s) => `${s}Uploaded ${file.name} -> ${result.key || 'uploaded'}\n`);
      }
      setFiles([]);
      // Refresh the uploaded images list
      if (selectedWeddingSlug) {
        fetchUploadedImages(selectedWeddingSlug);
      }
    } catch (err: any) {
      setStatus(`Error: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <main className="min-h-screen bg-wedding-ivory dark:bg-gray-900 p-6">
      <div className="w-full max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-elegant text-wedding-navy dark:text-gray-100">Gallery Management</h1>
        </div>

        {/* Wedding Selection - Global */}
        <Card className="mb-6">
          <div className="p-6">
            <label className="block text-sm font-medium text-wedding-navy dark:text-gray-100 mb-2">
              Select Wedding
            </label>
            <select
              value={selectedWedding}
              onChange={(e) => handleWeddingChange(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-sage focus:border-transparent"
              required
            >
              <option value="">Choose a wedding...</option>
              {weddings.map((wedding) => (
                <option key={wedding.id || wedding._id} value={wedding.id || wedding._id}>
                  {wedding.couple_names} - {wedding.date}
                </option>
              ))}
            </select>
          </div>
        </Card>

        {selectedWedding && (
          <>
            {/* Tabs */}
            <div className="flex gap-4 mb-6">
              <button
                onClick={() => setActiveTab('upload')}
                className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                  activeTab === 'upload'
                    ? 'bg-wedding-sage text-white'
                    : 'bg-white dark:bg-gray-700 text-wedding-navy dark:text-gray-100 hover:bg-wedding-ivory dark:hover:bg-gray-600'
                }`}
              >
                Upload Images
              </button>
              <button
                onClick={() => setActiveTab('manage')}
                className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                  activeTab === 'manage'
                    ? 'bg-wedding-sage text-white'
                    : 'bg-white dark:bg-gray-700 text-wedding-navy dark:text-gray-100 hover:bg-wedding-ivory dark:hover:bg-gray-600'
                }`}
              >
                Manage Gallery ({uploadedImages.length})
              </button>
            </div>

            {/* Upload Tab */}
            {activeTab === 'upload' && (
              <Card className="backdrop-blur-sm bg-white/60 dark:bg-gray-800/60">
                <div className="space-y-4 p-6">
                  {/* Folder Selection */}
                  <div>
                    <label className="block text-sm font-medium text-wedding-navy dark:text-gray-100 mb-2">
                      Upload to Folder
                    </label>
                    <select
                      value={selectedFolder}
                      onChange={(e) => setSelectedFolder(e.target.value)}
                      className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-sage focus:border-transparent"
                    >
                      <option value="gallery">Public Gallery</option>
                      <option value="our-story">Our Story</option>
                      <option value="wedding-party">Wedding Party</option>
                    </select>
                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                      • <strong>Public Gallery</strong>: Photos visible to all guests
                      <br />
                      • <strong>Our Story</strong>: Couple photos for the story section
                      <br />
                      • <strong>Wedding Party</strong>: Individual member photos
                    </p>
                  </div>

                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={handleFileChange}
                    className="w-full text-sm text-gray-900 dark:text-gray-100 file:py-2 file:px-4
                               file:rounded-full file:border-0
                               file:text-sm file:font-medium
                               file:bg-wedding-sage file:text-wedding-navy
                               hover:file:bg-wedding-rose dark:file:bg-gray-600 dark:file:text-gray-100
                               dark:hover:file:bg-gray-500"
                  />

                  {previews.length > 0 && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                      {previews.map((url, i) => (
                        <div
                          key={i}
                          className="relative rounded-lg overflow-hidden shadow-lg"
                        >
                          <img
                            src={url}
                            alt={`Preview ${i + 1}`}
                            className="w-full h-40 object-cover"
                          />
                          <button
                            type="button"
                            onClick={async () => {
                              const key = decodeURIComponent(
                                url.split('/').pop() || ''
                              );
                              try {
                                const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
                                const res = await fetch(
                                  `${base}/gallery?key=${encodeURIComponent(
                                    'gallery/' + key
                                  )}`,
                                  {
                                    method: 'DELETE',
                                    headers: { Authorization: `Bearer ${token}` },
                                  }
                                );
                                if (!res.ok) throw new Error('Delete failed');
                                setStatus((s) => `${s}Deleted ${key}\n`);
                                setFiles((f) => f.filter((_, idx) => idx !== i));
                              } catch (err: any) {
                                setStatus(`Error: ${err.message}`);
                              }
                            }}
                            className="absolute top-2 right-2 bg-red-600
                                       text-white text-xs px-2 py-1 rounded
                                       hover:bg-red-700"
                          >
                            Delete
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  <Button
                    onClick={handleUpload}
                    disabled={!files.length || uploading || !selectedWedding}
                    className="w-full"
                  >
                    {uploading ? 'Uploading…' : 'Upload Images'}
                  </Button>

                  {!selectedWedding && (
                    <p className="text-sm text-gray-600 dark:text-gray-300 text-center">
                      Please select a wedding before uploading images
                    </p>
                  )}

                  {status && (
                    <pre className="mt-2 text-sm whitespace-pre-wrap text-wedding-navy dark:text-gray-100">
                      {status}
                    </pre>
                  )}
                </div>
              </Card>
            )}

            {/* Gallery Management Tab */}
            {activeTab === 'manage' && (
              <Card className="backdrop-blur-sm bg-white/60 dark:bg-gray-800/60">
                <div className="p-6">
                  <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100 mb-4">
                    Uploaded Images for {weddings.find(w => (w.id || w._id) === selectedWedding)?.couple_names}
                  </h2>
                  
                  {loadingImages ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="animate-spin h-8 w-8 border-4 border-wedding-sage border-t-transparent rounded-full"></div>
                      <span className="ml-3 text-wedding-navy dark:text-gray-100">Loading images...</span>
                    </div>
                  ) : uploadedImages.length === 0 ? (
                    <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                      <p className="text-lg">No images uploaded yet</p>
                      <p className="text-sm mt-2">Switch to Upload tab to add some images</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                      {uploadedImages.map((image, index) => {
                        const isFeatured = currentFeaturedImage === (image.key || image.filename);
                        return (
                          <div key={index} className="relative group">
                            <div className={`aspect-square rounded-lg overflow-hidden shadow-lg bg-gray-100 ${isFeatured ? 'ring-4 ring-purple-600' : ''}`}>
                              <img
                                src={image.url || image.file_url || '#'}
                                alt={`Gallery image ${index + 1}`}
                                className="w-full h-full object-cover transition-transform group-hover:scale-105"
                                onError={(e) => {
                                  e.currentTarget.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlPC90ZXh0Pjwvc3ZnPg==';
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
                            <p className="text-xs text-gray-600 dark:text-gray-300 truncate">
                              {image.key || image.filename || `image-${index + 1}`}
                            </p>
                            <div className="flex items-center gap-2 mt-1">
                              {/* Folder Badge */}
                              <span className={`text-xs px-2 py-0.5 rounded-full ${
                                image.key?.startsWith('gallery/') ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-200' :
                                image.key?.startsWith('our-story/') ? 'bg-pink-100 dark:bg-pink-900 text-pink-700 dark:text-pink-200' :
                                image.key?.startsWith('wedding-party/') ? 'bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-200' :
                                'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200'
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
                          <button
                            onClick={() => {
                              console.log('Delete button clicked for:', image.key || image.filename);
                              handleDeleteImage(image.key || image.filename);
                            }}
                            className="absolute top-2 right-2 bg-red-600 text-white text-xs px-2 py-1 rounded hover:bg-red-700 opacity-0 group-hover:opacity-100 transition-opacity z-10"
                          >
                            Delete
                          </button>

                          {/* Copy URL Button */}
                          <button
                            onClick={() => {
                              console.log('Copy URL button clicked for:', image.key);
                              navigator.clipboard.writeText(image.url || image.file_url || '');
                              setStatus((s) => `${s}Copied URL for ${image.key}\n`);
                            }}
                            className="absolute top-2 left-2 bg-wedding-sage text-white text-xs px-2 py-1 rounded hover:bg-wedding-rose opacity-0 group-hover:opacity-100 transition-opacity z-10"
                          >
                            Copy URL
                          </button>

                          {/* Set as Featured Button */}
                          <button
                            onClick={async () => {
                              console.log('Set as Background clicked for:', image.key || image.filename);
                              console.log('Selected wedding ID:', selectedWedding);
                              try {
                                const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL!;
                                const response = await fetch(`${baseUrl}/admin/weddings/${selectedWedding}`, {
                                  method: 'PUT',
                                  headers: {
                                    'Authorization': `Bearer ${token}`,
                                    'Content-Type': 'application/json',
                                  },
                                  body: JSON.stringify({
                                    featured_image: image.key || image.filename
                                  }),
                                });

                                console.log('Response status:', response.status);
                                if (!response.ok) {
                                  const errorText = await response.text();
                                  console.error('Failed to set featured image:', errorText);
                                  throw new Error('Failed to set featured image');
                                }

                                setStatus((s) => `${s}Set ${image.key} as featured background\n`);
                                setCurrentFeaturedImage(image.key || image.filename);
                              } catch (err: any) {
                                console.error('Error setting featured image:', err);
                                setStatus(`Error: ${err.message}`);
                              }
                            }}
                            className="absolute bottom-2 left-2 right-2 bg-purple-600 text-white text-xs px-2 py-1 rounded hover:bg-purple-700 opacity-0 group-hover:opacity-100 transition-opacity z-20"
                          >
                            Set as Background
                          </button>
                        </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Gallery Stats */}
                  {uploadedImages.length > 0 && (
                    <div className="mt-6 p-4 bg-wedding-ivory rounded-lg">
                      <div className="flex justify-between items-center text-sm text-wedding-navy dark:text-gray-100">
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
    </main>
  );
}

