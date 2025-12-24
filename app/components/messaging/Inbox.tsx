
import React, { useState } from 'react';
import { ConversationResponse } from '../../types/messaging';

interface InboxProps {
  conversations: ConversationResponse[];
  onSelectConversation: (conversation: ConversationResponse) => void;
  activeConversationId?: string;
}

const Inbox: React.FC<InboxProps> = ({ conversations, onSelectConversation, activeConversationId }) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredConversations = conversations.filter(
    (conversation) =>
      conversation.subject?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      conversation.wedding_id?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="flex flex-col w-full md:w-1/3 lg:w-1/4 border-r border-gray-200 bg-gray-50">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-2xl font-bold text-gray-800">Inbox</h2>
        <div className="mt-4">
          <input
            type="text"
            placeholder="Search conversations..."
            className="w-full px-4 py-2 border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {filteredConversations.map((conversation) => (
          <div
            key={conversation.conversation_id}
            className={`p-4 border-b border-gray-200 cursor-pointer ${
              activeConversationId === conversation.conversation_id ? 'bg-blue-100' : 'hover:bg-gray-100'
            }`}
            onClick={() => onSelectConversation(conversation)}
          >
            <div className="flex items-center">
              <div className="relative w-12 h-12 mr-4">
                <div
                  className="w-12 h-12 rounded-full bg-blue-500 flex items-center justify-center text-white font-semibold"
                  aria-label={conversation.subject}
                >
                  {(conversation.subject || 'C').charAt(0).toUpperCase()}
                </div>
                <span className="absolute bottom-0 right-0 block h-3 w-3 rounded-full bg-green-500 border-2 border-white"></span>
              </div>
              <div className="flex-1">
                <div className="flex justify-between">
                  <h3 className="font-semibold text-gray-800">{conversation.subject}</h3>
                  <p className="text-xs text-gray-500">
                    {new Date(conversation.updated_at).toLocaleTimeString()}
                  </p>
                </div>
                <div className="flex justify-between">
                  <p className="text-sm text-gray-600 truncate">{`Wedding: ${conversation.wedding_id}`}</p>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Inbox;
