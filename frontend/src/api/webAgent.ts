import { request } from './client';

export interface WebAgentConfig {
  models: string[];
  shared_available: boolean;
  connections: { id: string; name: string; level: string; active: boolean }[];
}
export interface ChatMessage { role: 'user' | 'assistant'; content: string }
export interface AgentEvent {
  type: 'start' | 'text' | 'tool_start' | 'tool_end' | 'usage' | 'done' | 'error';
  text?: string;
  message?: string;
  configuration_error?: boolean;
  id?: string;
  name?: string;
  input_tokens?: number;
  output_tokens?: number;
  cache_read_tokens?: number;
  requests?: number;
}
export const webAgentApi = {
  config: () => request<WebAgentConfig>('/web-agent/config'),
  balance: () => request<{ available: boolean; balances: { currency: string; total_balance: string }[] }>('/web-agent/balance'),
};

export async function streamChat(body: {
  credential_id: string; message: string; history: ChatMessage[];
  model: string; source: 'personal' | 'shared'; api_key?: string;
}, signal: AbortSignal, onEvent: (event: AgentEvent) => void) {
  const response = await fetch('/api/web-agent/chat', {
    method: 'POST', credentials: 'same-origin', signal,
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('fgas-session-expired'));
    const data = await response.json().catch(() => null);
    throw Object.assign(new Error(typeof data?.detail === 'string' ? data.detail : `请求未完成（${response.status}）`),
      { configurationError: response.status === 400 || response.status === 403 });
  }
  if (!response.body) throw new Error('当前浏览器无法接收流式回复');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = '';
  let terminal = false;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      pending += decoder.decode(value, { stream: !done });
      const frames = pending.split('\n\n');
      pending = frames.pop() || '';
      for (const frame of frames) {
        const data = frame.split('\n').filter(line => line.startsWith('data: ')).map(line => line.slice(6)).join('\n');
        if (!data) continue;
        const event = JSON.parse(data) as AgentEvent;
        if (event.type === 'done' || event.type === 'error') terminal = true;
        onEvent(event);
      }
      if (done) break;
    }
  } finally { reader.releaseLock(); }
  if (!terminal) throw new Error('连接已中断，请核对已返回的结果和业务记录');
}
