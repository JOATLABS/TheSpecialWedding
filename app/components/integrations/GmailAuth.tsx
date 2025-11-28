
import React from 'react';

const GmailAuth = () => {
  const handleAuth = () => {
    window.location.href = '/api/integrations/gmail/auth';
  };

  return (
    <div>
      <button onClick={handleAuth}>Connect Gmail</button>
    </div>
  );
};

export default GmailAuth;
