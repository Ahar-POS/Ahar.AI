/**
 * ChatbotPage component with Skills API support.
 *
 * Admin-only. Features:
 * - Multi-turn conversation with text replies
 * - File downloads for generated reports (P&L, etc.)
 * - Token usage tracking displayed in UI
 * - No real restaurant data used in general chat
 */

import React, { useRef, useEffect, useState } from 'react';
import { sendMessage, ChatbotMessageData, getDownloadUrl } from '../services/chatbot';
import './ChatbotPage.css';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  downloadUrl?: string;
  filename?: string;
  usage?: {
    input_tokens: number;
    output_tokens: number;
  };
}

export default function ChatbotPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || submitting) return;

    setError(null);
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setSubmitting(true);

    try {
      const response: ChatbotMessageData = await sendMessage(text);

      // Build assistant message
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.reply,
      };

      // Add download info if present
      if (response.download_url && response.filename) {
        assistantMessage.downloadUrl = response.download_url;
        assistantMessage.filename = response.filename;
      }

      // Add token usage if present
      if (response.usage) {
        assistantMessage.usage = response.usage;
      }

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to get reply';
      const ax = err && typeof err === 'object' && 'response' in err ? (err as { response?: { status?: number } }) : null;
      const responseStatus = ax?.response?.status ?? null;
      const isNetworkError = responseStatus === null && (message === 'Network Error' || message.includes('Network Error'));
      const displayMessage = isNetworkError
        ? 'Could not connect to the server. Make sure the backend is running (e.g. uvicorn app.main:app --reload --port 8000) and that VITE_API_URL points to it (default http://localhost:8000).'
        : message;
      setError(displayMessage);
      setMessages((prev) => [...prev, { role: 'assistant', content: displayMessage }]);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="chatbot-page">
      <div className="chatbot-page-header">
        <h1 className="chatbot-page-title">Chatbot</h1>
        <p className="chatbot-page-subtitle">
          Ask about restaurant financials, request P&L reports, or get general advice.
        </p>
      </div>

      <div className="chatbot-messages" role="log" aria-live="polite">
        {messages.length === 0 && (
          <p className="chatbot-placeholder">
            Send a message to start. Examples:<br />
            • &quot;Generate P&L for last week&quot;<br />
            • &quot;P&L for January 2024&quot;<br />
            • &quot;How can I improve inventory turnover?&quot;
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`chatbot-message chatbot-message--${msg.role}`}
            data-role={msg.role}
          >
            <span className="chatbot-message-role" aria-hidden="true">
              {msg.role === 'user' ? 'You' : 'Assistant'}
            </span>
            <p className="chatbot-message-content">{msg.content}</p>

            {/* Download link if file was generated */}
            {msg.downloadUrl && msg.filename && (
              <div className="chatbot-message-download">
                <a
                  href={getDownloadUrl(msg.filename)}
                  download={msg.filename}
                  className="btn btn-sm btn-success"
                >
                  📥 Download {msg.filename}
                </a>
              </div>
            )}

            {/* Token usage footer (only for assistant messages) */}
            {msg.role === 'assistant' && msg.usage && (
              <div className="chatbot-message-usage">
                <small>
                  Tokens: {msg.usage.input_tokens} in / {msg.usage.output_tokens} out
                  ({msg.usage.input_tokens + msg.usage.output_tokens} total)
                </small>
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div id="chatbot-error-id" className="chatbot-error" role="alert">
          {error}
        </div>
      )}

      <form
        className="chatbot-form"
        onSubmit={handleSubmit}
        aria-label="Send a message"
      >
        <label htmlFor="chatbot-input" className="sr-only">
          Message
        </label>
        <input
          id="chatbot-input"
          type="text"
          className="chatbot-input"
          placeholder="Type your message or request a P&L report..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={submitting}
          maxLength={4000}
          autoComplete="off"
          aria-describedby={error ? 'chatbot-error-id' : undefined}
        />
        <button
          type="submit"
          className="btn btn-primary chatbot-send"
          disabled={submitting || !input.trim()}
          aria-busy={submitting}
        >
          {submitting ? 'Sending…' : 'Send'}
        </button>
      </form>
    </div>
  );
}
