
import React from 'react';

const GmailAuth = () => {
  const handleAuth = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/integrations/gmail/auth`);
      if (response.ok) {
        const data = await response.json();
        window.location.href = data.authorization_url;
      }
    } catch (error) {
      console.error("Failed to start Gmail authentication:", error);
    }
  };

  return (
    <div>
      <button onClick={handleAuth}>Connect Gmail</button>
    </div>
  );
};

export default GmailAuth;
