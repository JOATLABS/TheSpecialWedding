
import React, { useState } from 'react';

const AttachmentHandler = () => {
  const [file, setFile] = useState<File | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/integrations/attachments', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        alert('Attachment uploaded successfully');
      } else {
        alert('Failed to upload attachment');
      }
    } catch (error) {
      console.error('Failed to upload attachment:', error);
      alert('Failed to upload attachment');
    }
  };

  return (
    <div>
      <input type="file" onChange={handleFileChange} />
      <button onClick={handleUpload}>Upload</button>
    </div>
  );
};

export default AttachmentHandler;
