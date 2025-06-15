'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

interface Wedding {
  id?: string;
  _id?: string;
  couple_names: string;
  date: string;
  slug: string;
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

  // redirect if not logged in
  useEffect(() => {
    if (!token) router.push('/admin/login');
  }, [token, router]);

  // fetch weddings
  useEffect(() => {
    fetchWeddings();
  }, []);

  const fetchWeddings = async () => {
    try {
      const response = await fetch('http://localhost:8000/weddings');
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
    if (wedding?.slug) {
      fetchUploadedImages(wedding.slug);
    }
  };

  const fetchUploadedImages = async (weddingSlug: string) => {
    setLoadingImages(true);
    try {
      const response = await fetch(
        `http://localhost:8000/gallery?wedding_slug=${weddingSlug}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (response.ok) {
        const data = await response.json();
        setUploadedImages(Array.isArray(data) ? data : []);
      } else {
        setUploadedImages([]);
      }
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
      const response = await fetch(
        `http://localhost:8000/admin/gallery?key=${encodeURIComponent(imageKey)}`,
        {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      
      if (response.ok) {
        setStatus((s) => `${s}🗑️ Deleted ${imageKey}\n`);
        // Refresh the image list
        if (selectedWeddingSlug) {
          fetchUploadedImages(selectedWeddingSlug);
        }
      } else {
        throw new Error('Delete failed');
      }
    } catch (err: any) {
      setStatus(`❌ ${err.message}`);
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
      setStatus('❌ Please select a wedding and files to upload');
      return;
    }
    setUploading(true);
    setStatus('');
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('wedding_slug', selectedWeddingSlug);
        
        const res = await fetch(
          `http://localhost:8000/admin/gallery/upload`,
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
        setStatus((s) => `${s}✅ ${file.name} → ${result.key || 'uploaded'}\n`);
      }
      setFiles([]);
      // Refresh the uploaded images list
      if (selectedWeddingSlug) {
        fetchUploadedImages(selectedWeddingSlug);
      }
    } catch (err: any) {
      setStatus(`❌ ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <main className="min-h-screen bg-wedding-ivory p-6">
      <div className="w-full max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-elegant text-wedding-navy">Gallery Management</h1>
        </div>

        {/* Wedding Selection - Global */}
        <Card className="mb-6">
          <div className="p-6">
            <label className="block text-sm font-medium text-wedding-navy mb-2">
              Select Wedding
            </label>
            <select
              value={selectedWedding}
              onChange={(e) => handleWeddingChange(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-sage focus:border-transparent"
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
                    : 'bg-white text-wedding-navy hover:bg-wedding-ivory'
                }`}
              >
                Upload Images
              </button>
              <button
                onClick={() => setActiveTab('manage')}
                className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                  activeTab === 'manage'
                    ? 'bg-wedding-sage text-white'
                    : 'bg-white text-wedding-navy hover:bg-wedding-ivory'
                }`}
              >
                Manage Gallery ({uploadedImages.length})
              </button>
            </div>

            {/* Upload Tab */}
            {activeTab === 'upload' && (
              <Card className="backdrop-blur-sm bg-white/60">
                <div className="space-y-4">

            <input
              type="file"
              accept="image/*"
              multiple
              onChange={handleFileChange}
              className="w-full text-sm file:py-2 file:px-4
                         file:rounded-full file:border-0
                         file:text-sm file:font-medium
                         file:bg-wedding-sage file:text-wedding-navy
                         hover:file:bg-wedding-rose"
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
                          setStatus((s) => `${s}🗑️ Deleted ${key}\n`);
                          setFiles((f) => f.filter((_, idx) => idx !== i));
                        } catch (err: any) {
                          setStatus(`❌ ${err.message}`);
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
              <p className="text-sm text-gray-600 text-center">
                Please select a wedding before uploading images
              </p>
            )}

                  {status && (
                    <pre className="mt-2 text-sm whitespace-pre-wrap text-wedding-navy">
                      {status}
                    </pre>
                  )}
                </div>
              </Card>
            )}

            {/* Gallery Management Tab */}
            {activeTab === 'manage' && (
              <Card className="backdrop-blur-sm bg-white/60">
                <div className="p-6">
                  <h2 className="text-xl font-semibold text-wedding-navy mb-4">
                    Uploaded Images for {weddings.find(w => (w.id || w._id) === selectedWedding)?.couple_names}
                  </h2>
                  
                  {loadingImages ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="animate-spin h-8 w-8 border-4 border-wedding-sage border-t-transparent rounded-full"></div>
                      <span className="ml-3 text-wedding-navy">Loading images...</span>
                    </div>
                  ) : uploadedImages.length === 0 ? (
                    <div className="text-center py-12 text-gray-500">
                      <p className="text-lg">No images uploaded yet</p>
                      <p className="text-sm mt-2">Switch to Upload tab to add some images</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                      {uploadedImages.map((image, index) => (
                        <div key={index} className="relative group">
                          <div className="aspect-square rounded-lg overflow-hidden shadow-lg bg-gray-100">
                            <img
                              src={image.url || image.file_url || '#'}
                              alt={`Gallery image ${index + 1}`}
                              className="w-full h-full object-cover transition-transform group-hover:scale-105"
                              onError={(e) => {
                                e.currentTarget.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlPC90ZXh0Pjwvc3ZnPg==';
                              }}
                            />
                          </div>
                          
                          {/* Image Info */}
                          <div className="mt-2">
                            <p className="text-xs text-gray-600 truncate">
                              {image.key || image.filename || `image-${index + 1}`}
                            </p>
                            {image.size && (
                              <p className="text-xs text-gray-500">
                                {(image.size / 1024).toFixed(1)} KB
                              </p>
                            )}
                          </div>

                          {/* Delete Button */}
                          <button
                            onClick={() => handleDeleteImage(image.key || image.filename)}
                            className="absolute top-2 right-2 bg-red-600 text-white text-xs px-2 py-1 rounded hover:bg-red-700 opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            Delete
                          </button>

                          {/* Copy URL Button */}
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(image.url || image.file_url || '');
                              setStatus((s) => `${s}📋 Copied URL for ${image.key}\n`);
                            }}
                            className="absolute top-2 left-2 bg-wedding-sage text-white text-xs px-2 py-1 rounded hover:bg-wedding-rose opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            Copy URL
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Gallery Stats */}
                  {uploadedImages.length > 0 && (
                    <div className="mt-6 p-4 bg-wedding-ivory rounded-lg">
                      <div className="flex justify-between items-center text-sm text-wedding-navy">
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

