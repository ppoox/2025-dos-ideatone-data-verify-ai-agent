import { useState } from 'react';
import PropTypes from 'prop-types';
import './message-composer.css';

function MessageComposer({ onSubmit, disabled }) {
  const [prompt, setPrompt] = useState('');

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!prompt.trim() || disabled) {
      return;
    }

    onSubmit(prompt);
    setPrompt('');
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit(event);
    }
  };

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <textarea
        className="composer-input"
        name="prompt"
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="검증할 데이터나 규칙을 입력해주세요. Shift+Enter로 줄바꿈."
        rows={2}
        disabled={disabled}
      />
      <button type="submit" className="composer-submit" disabled={disabled || !prompt.trim()}>
        전송
      </button>
    </form>
  );
}

MessageComposer.propTypes = {
  onSubmit: PropTypes.func.isRequired,
  disabled: PropTypes.bool
};

MessageComposer.defaultProps = {
  disabled: false
};

export default MessageComposer;
