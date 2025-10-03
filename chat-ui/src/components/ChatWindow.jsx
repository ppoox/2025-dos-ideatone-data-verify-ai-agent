import PropTypes from 'prop-types';
import MessageBubble from './MessageBubble.jsx';
import './chat-window.css';

function ChatWindow({ messages }) {
  return (
    <div className="chat-window">
      {messages.map((message) => (
        <MessageBubble key={message.id} role={message.role} content={message.content} />
      ))}
    </div>
  );
}

ChatWindow.propTypes = {
  messages: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      role: PropTypes.oneOf(['user', 'assistant']).isRequired,
      content: PropTypes.string.isRequired
    })
  ).isRequired
};

export default ChatWindow;
