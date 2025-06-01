'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';

export default function AdminGalleryUploadPage() {
  const { token, logout } = useAdmin();
  const router = useRouter();

  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<string>('');
  const [previews, setPreviews] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (!token) {
      router.push('/admin/login');
    }
  }, [token, router]);

  useEffect(() => {
    if (files.length === 0) {
      setPreviews([]);
      return;
    }

    const objectUrls = files.map((file) => URL.createObjectURL(file));
    setPreviews(objectUrls);

    // Clean up object URLs on unmount
    return () => objectUrls.forEach((url) => URL.revokeObjectURL(url));
  }, [files]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    setFiles(selected);
  };

  const handleUpload = async () => {
    if (!token || files.length === 0) return;
    setUploading(true);
    setStatus('');

    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/gallery/upload`, {
          method: 'POST',
          body: formData,
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Upload failed');
        }

        const result = await res.json();
        setStatus((prev) => prev + `✅ ${file.name} uploaded as ${result.key}\n`);
      }
      setFiles([]);
    } catch (err: any) {
      setStatus(`❌ Error: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

    return (
        <main className="max-w-2xl mx-auto p-4">
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold">Admin Gallery Upload</h1>
                <button
                    onClick={logout}
                    className="text-red-600 hover:underline text-sm"
                >
                    Logout
                </button>
            </div>

            <input
                type="file"
                accept="image/*"
                multiple
                onChange={handleFileChange}
                className="block mb-4"
            />

            {previews.length > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
                    {previews.map((url, i) => (
                        <div key={i} className="relative border rounded overflow-hidden group">
                            <img
                                src={url}
                                alt={`Preview ${i + 1}`}
                                className="w-full h-40 object-cover"
                            />
                            <button
                                type="button"
                                onClick={async () => {
                                    const key = decodeURIComponent(url.split('/').pop() ?? '');
                                    try {
                                        const res = await fetch(
                                            `${process.env.NEXT_PUBLIC_API_BASE_URL}/gallery?key=${encodeURIComponent('gallery/' + key)}`,
                                            {
                                                method: 'DELETE',
                                                headers: {
                                                    Authorization: `Bearer ${token}`,
                                                },
                                            }
                                        );

                                        if (!res.ok) {
                                            throw new Error('Delete failed');
                                        }

                                        setStatus((prev) => prev + `🗑️ Deleted: ${key}\n`);
                                        setFiles((f) => f.filter((_, idx) => idx !== i));
                                        setPreviews((p) => p.filter((_, idx) => idx !== i));
                                    } catch (err: any) {
                                        setStatus(`❌ Failed to delete: ${err.message}`);
                                    }
                                }}
                                className="absolute top-2 right-2 bg-red-600 text-white text-xs px-2 py-1 rounded shadow hover:bg-red-700 opacity-80"
                            >
                                Delete
                            </button>
                        </div>
                    ))}
                </div>

            )}

            <button
                onClick={handleUpload}
                disabled={files.length === 0 || uploading}
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:bg-blue-300"
            >
                {uploading ? 'Uploading...' : 'Upload'}
            </button>

            {status && (
                <pre className="mt-4 bg-gray-100 p-3 text-sm whitespace-pre-wrap rounded border">
                    {status}
                </pre>
            )}
        </main>
    );
}
