
import React from 'react';
import { MessageResponse } from '../../models/messaging';

interface ConversationViewProps {
  messages: MessageResponse[];
}

const ConversationView: React.FC<ConversationViewProps> = ({ messages }) => {
  return (
    <div className="flex flex-col flex-1">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-xl font-bold">John Doe</h2>
      </div>
      <div className="flex-1 p-4 overflow-y-auto">
        {messages.map((message) => (
          <div
            key={message.message_id}
            className={`flex mb-4 ${
              message.sender_id === 'You' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`rounded-lg px-4 py-2 ${
                message.sender_id === 'You'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-200 text-gray-800'
              }`}
            >
              {message.body}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ConversationView;
