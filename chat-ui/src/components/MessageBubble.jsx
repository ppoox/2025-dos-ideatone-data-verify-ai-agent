import PropTypes from 'prop-types';
import './message-bubble.css';

const labels = {
  user: '사용자',
  assistant: '에이전트'
};

function MessageBubble({ role, content }) {
  const isUser = role === 'user';

  return (
    <article className={`message-bubble ${isUser ? 'from-user' : 'from-assistant'}`}>
      <div className="avatar" aria-hidden="true">
        {isUser ? 'U' : 'A'}
      </div>
      <div className="message-body">
        <header className="message-meta">
          <span className="author">{labels[role]}</span>
        </header>
        <p className="message-text">{content}</p>
      </div>
    </article>
  );
}

MessageBubble.propTypes = {
  role: PropTypes.oneOf(['user', 'assistant']).isRequired,
  content: PropTypes.string.isRequired
};

export default MessageBubble;
