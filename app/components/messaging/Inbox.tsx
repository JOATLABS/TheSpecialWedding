
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
    <>
      <div className="mb-4">
        <input
          type="text"
          placeholder="Search conversations..."
          className="w-full px-4 py-2 border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-indigo-500"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>
      <div className="flex-1 overflow-y-auto -mx-4">
        {filteredConversations.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <p className="text-sm">No conversations found</p>
          </div>
        ) : (
          filteredConversations.map((conversation) => (
            <div
              key={conversation.conversation_id}
              className={`p-4 border-b border-gray-200 cursor-pointer ${
                activeConversationId === conversation.conversation_id ? 'bg-indigo-50' : 'hover:bg-gray-100'
              }`}
              onClick={() => onSelectConversation(conversation)}
            >
              <div className="flex items-center">
                <div className="relative w-12 h-12 mr-4">
                  <div
                    className="w-12 h-12 rounded-full bg-indigo-500 flex items-center justify-center text-white font-semibold"
                    aria-label={conversation.subject}
                  >
                    {(conversation.subject || 'C').charAt(0).toUpperCase()}
                  </div>
                  <span className="absolute bottom-0 right-0 block h-3 w-3 rounded-full bg-green-500 border-2 border-white"></span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-start">
                    <h3 className="font-semibold text-gray-800 truncate">{conversation.subject || 'No Subject'}</h3>
                    <p className="text-xs text-gray-500 ml-2 whitespace-nowrap">
                      {new Date(conversation.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                  {conversation.last_message_summary && (
                    <p className="text-sm text-gray-600 truncate mt-1">{conversation.last_message_summary}</p>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </>
  );
};

export default Inbox;
