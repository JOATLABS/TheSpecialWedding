
import React from 'react';
import { ConversationResponse } from '../../models/messaging';

interface InboxProps {
  conversations: ConversationResponse[];
  onSelectConversation: (conversation: ConversationResponse) => void;
}

const Inbox: React.FC<InboxProps> = ({ conversations, onSelectConversation }) => {
  return (
    <div className="flex flex-col w-1/4 border-r border-gray-200">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-xl font-bold">Inbox</h2>
      </div>
      <div className="flex-1 overflow-y-auto">
        {conversations.map((conversation) => (
          <div
            key={conversation.conversation_id}
            className="p-4 border-b border-gray-200 hover:bg-gray-100 cursor-pointer"
            onClick={() => onSelectConversation(conversation)}
          >
            <h3 className="font-semibold">{conversation.subject}</h3>
            <p className="text-gray-500">{conversation.last_message_summary}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Inbox;
