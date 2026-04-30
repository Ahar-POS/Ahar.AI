/**
 * ChatbotPage — Ahar AI assistant interface.
 *
 * Two-state layout:
 *  • Empty state  — greeting + input card + suggestion pills are one centered unit
 *  • Active state — messages fill the page; input is pinned at the bottom
 *
 * Both input instances share the same React state. Only one is ever visible:
 * the centered welcome input fades out and the bottom chat input fades in when
 * the first message is sent, creating a smooth "settling" transition.
 */

import React, { useRef, useEffect, useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAuth } from '../contexts/AuthContext';
import { sendMessage, ChatbotMessageData, getDownloadUrl } from '../services/chatbot';
import './ChatbotPage.css';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  downloadUrl?: string;
  filename?: string;
  /** Token usage information from API */
  usage?: {
    input_tokens: number;
    output_tokens: number;
  };
}

/** Ahar-specific suggestion prompts for the welcome screen. */
const SUGGESTION_PILLS = [
  { label: 'Generate P&L Report',   prompt: 'Generate a P&L report for last month' },
  { label: 'Analyse Sales Trends',  prompt: 'Analyse my sales trends for the past week' },
  { label: 'Low Stock Alerts',      prompt: 'Which items are low in stock and need restocking?' },
  { label: 'Browse Ingredients',    prompt: 'List all ingredients grouped by category' },
  { label: 'Operational Tips',      prompt: 'Give me tips to improve my restaurant operational efficiency' },
];

function getTimeGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good Morning';
  if (hour < 17) return 'Good Afternoon';
  return 'Good Evening';
}

function truncateTitle(text: string, maxLength = 45): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trimEnd() + '…';
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M8 13V3M8 3L3 8M8 3L13 8"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function ChatbotPage() {
  const { user } = useAuth();
  const [messages, setMessages]               = useState<ChatMessage[]>([]);
  const [input, setInput]                     = useState('');
  const [submitting, setSubmitting]           = useState(false);
  const [error, setError]                     = useState<string | null>(null);
  const [conversationTitle, setConversationTitle] = useState<string | null>(null);
  const [sessionTokens, setSessionTokens]     = useState({ input: 0, output: 0 });

  const messagesEndRef  = useRef<HTMLDivElement>(null);
  /** Input ref used in the centered welcome state. */
  const welcomeInputRef = useRef<HTMLInputElement>(null);
  /** Input ref used once the conversation is active (pinned bottom). */
  const chatInputRef    = useRef<HTMLInputElement>(null);

  const hasStarted = messages.length > 0;

  const greeting = useMemo(() => {
    const firstName = user?.first_name ?? 'there';
    return `${getTimeGreeting()}, ${firstName}`;
  }, [user?.first_name]);

  // Auto-scroll to the latest message.
  useEffect(() => {
    if (messagesEndRef.current) {
      const container = messagesEndRef.current.parentElement;
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    }
  }, [messages, submitting]);

  // On mount: focus the centered welcome input.
  useEffect(() => {
    welcomeInputRef.current?.focus();
  }, []);

  // When conversation starts, shift focus to the bottom chat input.
  useEffect(() => {
    if (hasStarted) {
      chatInputRef.current?.focus();
    }
  }, [hasStarted]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || submitting) return;

    if (!conversationTitle) {
      setConversationTitle(truncateTitle(text));
    }

    setError(null);
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setSubmitting(true);

    try {
      const response: ChatbotMessageData = await sendMessage(text);

      const assistantMessage: ChatMessage = { role: 'assistant', content: response.reply };

      if (response.download_url && response.filename) {
        // Use backend API download URL so the file is served by the backend (not frontend origin)
        assistantMessage.downloadUrl = getDownloadUrl(response.filename);
        assistantMessage.filename    = response.filename;
      }
      if (response.usage) {
        assistantMessage.usage = response.usage;
        // Update session token counters
        setSessionTokens(prev => ({
          input: prev.input + response.usage.input_tokens,
          output: prev.output + response.usage.output_tokens
        }));
      }

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to get reply';
      const ax = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { status?: number } }) : null;
      const isNetworkError =
        (ax?.response?.status ?? null) === null &&
        (message === 'Network Error' || message.includes('Network Error'));
      const displayMessage = isNetworkError
        ? 'Could not connect to the server. Make sure the backend is running.'
        : message;

      setError(displayMessage);
      setMessages((prev) => [...prev, { role: 'assistant', content: displayMessage }]);
    } finally {
      setSubmitting(false);
    }
  };

  const handlePillClick = (prompt: string) => {
    setInput(prompt);
    welcomeInputRef.current?.focus();
  };

  /** Shared input card markup — rendered in both welcome and chat positions. */
  const inputCard = (ref: React.RefObject<HTMLInputElement>, inputId: string) => (
    <div className="chatbot-input-card">
      <label htmlFor={inputId} className="sr-only">Message</label>
      <input
        id={inputId}
        ref={ref}
        type="text"
        className="chatbot-input"
        placeholder={hasStarted ? 'Continue the conversation…' : 'Ask anything about your restaurant…'}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        disabled={submitting}
        maxLength={4000}
        autoComplete="off"
        aria-describedby={error ? 'chatbot-error-id' : undefined}
      />
      <button
        type="submit"
        className="chatbot-send-btn"
        disabled={submitting || !input.trim()}
        aria-label="Send message"
        aria-busy={submitting}
      >
        <SendIcon />
      </button>
    </div>
  );

  return (
    <div className={`chatbot-page${hasStarted ? ' chatbot-page--active' : ''}`}>

      {/* ── Conversation title bar ── slides in when active */}
      <div
        className={`chatbot-title-bar${hasStarted && conversationTitle ? ' chatbot-title-bar--visible' : ''}`}
        aria-hidden={!hasStarted}
      >
        <div className="chatbot-title-bar-left">
          <span className="chatbot-snowflake" aria-hidden="true">❄</span>
          <span className="chatbot-title-bar-text">{conversationTitle ?? ''}</span>
        </div>
        {hasStarted && (sessionTokens.input > 0 || sessionTokens.output > 0) && (
          <div className="chatbot-session-tokens" title="Session Token Usage">
            <span className="chatbot-session-tokens-label">Session:</span>
            <span className="chatbot-session-tokens-value">
              {(sessionTokens.input + sessionTokens.output).toLocaleString()} tokens
            </span>
            <span className="chatbot-session-tokens-detail">
              ({sessionTokens.input.toLocaleString()}↑ {sessionTokens.output.toLocaleString()}↓)
            </span>
          </div>
        )}
      </div>

      {/* ── Main area ── welcome and messages overlay each other */}
      <div className="chatbot-main">

        {/* ── Welcome state ──
            Greeting + input card + suggestion pills, all centered as one unit.
            Fades out and slides up when the first message is sent. */}
        <div
          className={`chatbot-welcome${hasStarted ? ' chatbot-welcome--hidden' : ''}`}
          aria-hidden={hasStarted}
        >
          {/* Brand + greeting */}
          <div className="chatbot-brand">
            <span className="chatbot-snowflake chatbot-snowflake--lg" aria-hidden="true">❄</span>
            <h1 className="chatbot-greeting">{greeting}</h1>
          </div>
          <p className="chatbot-tagline">Ask about your restaurant, request reports, or get advice.</p>

          {/* Centered input card */}
          <div className="chatbot-welcome-input">
            {error && (
              <div className="chatbot-error" role="alert" id="chatbot-error-id">{error}</div>
            )}
            <form onSubmit={handleSubmit} aria-label="Send a message">
              {inputCard(welcomeInputRef, 'chatbot-input-welcome')}
            </form>

            {/* Suggestion pills */}
            <div className="chatbot-suggestions" role="group" aria-label="Suggested prompts">
              {SUGGESTION_PILLS.map((pill) => (
                <button
                  key={pill.label}
                  type="button"
                  className="chatbot-pill"
                  onClick={() => handlePillClick(pill.prompt)}
                >
                  {pill.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── Messages ── fades in when active */}
        <div
          className={`chatbot-messages${hasStarted ? ' chatbot-messages--visible' : ''}`}
          role="log"
          aria-live="polite"
          aria-label="Conversation"
        >
          {messages.map((msg, i) => (
            <div key={i} className={`chatbot-message chatbot-message--${msg.role}`}>
              {msg.role === 'assistant' ? (
                <div className="chatbot-response">
                  <div className="chatbot-response-content chatbot-bubble-markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                </div>
              ) : (
                <div className="chatbot-bubble">
                  <p className="chatbot-bubble-text">{msg.content}</p>
                </div>
              )}

              {msg.downloadUrl && msg.filename && (
                <div className="chatbot-download-wrapper">
                  <a
                    href={msg.downloadUrl}
                    download={msg.filename}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="chatbot-download-btn"
                    onClick={(e) => {
                      // Prevent page navigation
                      e.preventDefault();
                      // Open download in new window
                      window.open(msg.downloadUrl, '_blank');
                    }}
                  >
                    ↓ Download {msg.filename}
                  </a>
                </div>
              )}

              {msg.role === 'assistant' && msg.usage && (
                <div className="chatbot-token-usage" title="API Token Usage">
                  {msg.usage.input_tokens.toLocaleString()} input • {msg.usage.output_tokens.toLocaleString()} output tokens
                </div>
              )}
            </div>
          ))}

          {/* Animated thinking dots while waiting */}
          {submitting && (
            <div className="chatbot-message chatbot-message--assistant">
              <div className="chatbot-response">
                <div className="chatbot-bubble chatbot-bubble--thinking">
                  <span className="chatbot-dot" />
                  <span className="chatbot-dot" />
                  <span className="chatbot-dot" />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* ── Bottom input ── only visible once conversation is active */}
      <div
        className={`chatbot-input-area${hasStarted ? ' chatbot-input-area--visible' : ''}`}
        aria-hidden={!hasStarted}
      >
        {error && (
          <div className="chatbot-error" role="alert" id="chatbot-error-id">{error}</div>
        )}
        <form onSubmit={handleSubmit} aria-label="Send a message">
          {inputCard(chatInputRef, 'chatbot-input-chat')}
        </form>
      </div>

    </div>
  );
}
