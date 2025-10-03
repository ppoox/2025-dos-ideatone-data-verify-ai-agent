import './typing-indicator.css';

function TypingIndicator() {
  return (
    <div className="typing-indicator" aria-live="polite">
      <span className="dot" />
      <span className="dot" />
      <span className="dot" />
    </div>
  );
}

export default TypingIndicator;
