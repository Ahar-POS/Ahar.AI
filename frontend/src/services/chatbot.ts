/**
 * Chatbot API service with Skills API support.
 *
 * Admin-only. Sends messages and handles:
 * - Text replies for general chat
 * - File downloads for generated reports (P&L, etc.)
 * - Token usage tracking
 */

import apiClient, { getErrorMessage } from './api';
import { APIResponse } from '../types/api';

/** Token usage statistics */
export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
}

/** Response data for POST /chatbot/message */
export interface ChatbotMessageData {
  reply: string;
  download_url?: string;
  filename?: string;
  usage?: TokenUsage;
  needs_clarification?: boolean;
}

/** API response shape for chatbot message endpoint */
type ChatbotMessageResponse = APIResponse<ChatbotMessageData>;

export interface SendMessageOptions {
  insightId?: string;
  clearHistory?: boolean;
}

/**
 * Send a message and get the assistant reply (admin-only).
 *
 * Backend keeps multi-turn history per user; no need to send history from frontend.
 * Pass insightId to ground the conversation in a specific agent insight card.
 * Pass clearHistory=true when starting a fresh insight session.
 */
export async function sendMessage(message: string, options: SendMessageOptions = {}): Promise<ChatbotMessageData> {
  try {
    const response = await apiClient.post<ChatbotMessageResponse>(
      '/chatbot/message',
      {
        message,
        ...(options.insightId ? { insight_id: options.insightId } : {}),
        ...(options.clearHistory ? { clear_history: true } : {}),
      },
    );
    return response.data.data ?? { reply: '' };
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Get download URL for a generated file
 *
 * @param filename - Name of file to download
 * @returns Full download URL
 */
export function getDownloadUrl(filename: string): string {
  const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  return `${baseURL}/api/v1/chatbot/download/${filename}`;
}
