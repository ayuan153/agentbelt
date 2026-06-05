/** Options for configuring the Agentbelt proxy connection. */
export interface AgentbeltOptions {
  /** Agentbelt proxy URL. Defaults to AGENTBELT_BASE_URL env or http://localhost:8088/v1 */
  baseURL?: string;
  /** Optional session ID sent as X-Agentbelt-Session header for multi-turn tracking. */
  sessionId?: string;
}

/** Returns `{ baseURL, defaultHeaders }` to spread into `new OpenAI({...})`. */
export function agentbeltConfig(opts?: AgentbeltOptions): { baseURL: string; defaultHeaders: Record<string, string> } {
  const baseURL = opts?.baseURL || process.env.AGENTBELT_BASE_URL || 'http://localhost:8088/v1';
  const defaultHeaders: Record<string, string> = {};
  if (opts?.sessionId) defaultHeaders['X-Agentbelt-Session'] = opts.sessionId;
  return { baseURL, defaultHeaders };
}

/** Merges Agentbelt settings into an existing OpenAI client options object. */
export function withAgentbelt<T extends Record<string, any>>(openaiOptions: T, opts?: AgentbeltOptions): T & { baseURL: string; defaultHeaders: Record<string, string> } {
  return { ...openaiOptions, ...agentbeltConfig(opts) };
}
