import { useMemo, useState } from 'react'
import ChatWindow from './components/ChatWindow.jsx'
import MessageComposer from './components/MessageComposer.jsx'
import TypingIndicator from './components/TypingIndicator.jsx'
import './styles/app.css'

const getId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

const initialMessages = [
  {
    id: getId(),
    role: 'assistant',
    content: '안녕하세요! 데이터 검증을 도와드리는 AI 에이전트입니다. 확인하고 싶은 데이터나 규칙을 입력해 주세요.'
  }
]

function App() {
  const [messages, setMessages] = useState(initialMessages)
  const [isLoading, setIsLoading] = useState(false)

  const conversationSummary = useMemo(() => {
    const lastUserMessage = [...messages].reverse().find((msg) => msg.role === 'user')
    if (!lastUserMessage) {
      return '신규 대화'
    }

    return lastUserMessage.content.length > 24 ? `${lastUserMessage.content.slice(0, 24)}...` : lastUserMessage.content
  }, [messages])

  const handleSendPrompt = async (prompt) => {
    const trimmed = prompt.trim()
    if (!trimmed) {
      return
    }

    const historyPayload = messages
      .filter((msg) => msg.role === 'user' || msg.role === 'assistant')
      .map((msg) => ({ role: msg.role, content: msg.content }))

    const userMessage = {
      id: getId(),
      role: 'user',
      content: trimmed
    }

    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    try {
      const response = await fetch('http://localhost:8000/api/agent/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          prompt: trimmed,
          history: historyPayload
        })
      })

      if (!response.ok) {
        console.log(response)
        throw new Error(`Server responded with ${response.status}`)
      }

      const data = await response.json()
      const assistantText = data?.reply?.trim() || '응답 메시지를 확인할 수 없습니다.'
      const assistantMessage = {
        id: getId(),
        role: 'assistant',
        content: assistantText
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      console.error('Failed to reach the chat API', error)
      const fallbackMessage = {
        id: getId(),
        role: 'assistant',
        content: '서버와 연결하지 못했습니다. 잠시 후 다시 시도해주세요.'
      }

      setMessages((prev) => [...prev, fallbackMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleReset = () => {
    setMessages(initialMessages)
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="sidebar-header">
          <span className="brand">Data Verify Agent</span>
          <button type="button" onClick={handleReset} className="reset-btn">
            새 대화
          </button>
        </div>
        <div className="sidebar-history">
          <div className="history-item active">
            <span className="dot" />
            <span className="title">{conversationSummary}</span>
          </div>
        </div>
      </aside>
      <main className="app-main">
        <header className="app-header">
          <div>
            <h1>2025 Do!S 데이터 검증 AI 에이전트</h1>
            <p className="subtitle">데이터 품질 점검, 규칙 정의, 결과 분석을 실시간으로 도와드립니다.</p>
          </div>
        </header>
        <section className="chat-container">
          <ChatWindow messages={messages} />
          {isLoading && <TypingIndicator />}
        </section>
        <footer className="chat-footer">
          <MessageComposer onSubmit={handleSendPrompt} disabled={isLoading} />
        </footer>
      </main>
    </div>
  )
}

export default App
