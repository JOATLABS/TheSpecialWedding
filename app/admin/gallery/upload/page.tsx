'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

export default function AdminGalleryUploadPage() {
  const { token, logout } = useAdmin();
  const router = useRouter();

  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<string>('');
  const [previews, setPreviews] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);

  // redirect if not logged in
  useEffect(() => {
    if (!token) router.push('/admin/login');
  }, [token, router]);

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
    if (!token || !files.length) return;
    setUploading(true);
    setStatus('');
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append('file', file);
        const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/admin";
        const res = await fetch(
          `${base}/gallery/upload`,
          {
            method: 'POST',
            body: fd,
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        if (!res.ok) throw new Error((await res.json()).detail || 'Upload failed');
        const { key } = await res.json();
        setStatus((s) => `${s}✅ ${file.name} → ${key}\n`);
      }
      setFiles([]);
    } catch (err: any) {
      setStatus(`❌ ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <main className="flex items-center justify-center min-h-screen bg-wedding-ivory p-6">
      <div className="w-full max-w-2xl">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-3xl font-elegant text-wedding-navy">Gallery Upload</h1>
        </div>

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
              disabled={!files.length || uploading}
              className="w-full"
            >
              {uploading ? 'Uploading…' : 'Upload Images'}
            </Button>

            {status && (
              <pre className="mt-2 text-sm whitespace-pre-wrap text-wedding-navy">
                {status}
              </pre>
            )}
          </div>
        </Card>
      </div>
    </main>
  );
}

