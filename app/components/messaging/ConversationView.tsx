
import React from 'react';
import { MessageResponse, ConversationResponse } from '../../types/messaging';

interface ConversationViewProps {
  messages: MessageResponse[];
  activeConversation: ConversationResponse;
}

const ConversationView: React.FC<ConversationViewProps> = ({ messages, activeConversation }) => {
  return (
    <div className="flex flex-col flex-1 bg-white">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-xl font-bold text-gray-800">{activeConversation?.subject}</h2>
      </div>
      <div className="flex-1 p-4 overflow-y-auto">
        {messages.map((message) => (
          <div
            key={message.message_id}
            className={`flex mb-4 ${
              message.sender_id === 'You' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div className="flex items-end">
              {message.sender_id !== 'You' && (
                <img
                  src={`https://i.pravatar.cc/150?u=${message.sender_id}`} // Placeholder avatar
                  alt={message.sender_id}
                  className="w-8 h-8 rounded-full mr-3"
                />
              )}
              <div
                className={`rounded-lg px-4 py-2 max-w-md ${
                  message.sender_id === 'You'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-200 text-gray-800'
                }`}
              >
                <div className="font-semibold text-sm">{message.sender_id}</div>
                <p>{message.body}</p>
                {message.attachments && message.attachments.length > 0 && (
                  <div className="mt-2">
                    {message.attachments.map((attachment, index) => (
                      <div key={index} className="flex items-center">
                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
                        <a href={attachment.url} target="_blank" rel="noopener noreferrer" className="text-sm underline">
                          {attachment.title || 'View Attachment'}
                        </a>
                      </div>
                    ))}
                  </div>
                )}
                <div className="text-xs text-right mt-1 opacity-75">
                  {new Date(message.created_at).toLocaleTimeString()}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ConversationView;
