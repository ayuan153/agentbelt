/** Options for configuring the Seatbelt proxy connection. */
export interface SeatbeltOptions {
  /** Seatbelt proxy URL. Defaults to SEATBELT_BASE_URL env or http://localhost:8088/v1 */
  baseURL?: string;
  /** Optional session ID sent as X-Seatbelt-Session header for multi-turn tracking. */
  sessionId?: string;
}

/** Returns `{ baseURL, defaultHeaders }` to spread into `new OpenAI({...})`. */
export function seatbeltConfig(opts?: SeatbeltOptions): { baseURL: string; defaultHeaders: Record<string, string> } {
  const baseURL = opts?.baseURL || process.env.SEATBELT_BASE_URL || 'http://localhost:8088/v1';
  const defaultHeaders: Record<string, string> = {};
  if (opts?.sessionId) defaultHeaders['X-Seatbelt-Session'] = opts.sessionId;
  return { baseURL, defaultHeaders };
}

/** Merges Seatbelt settings into an existing OpenAI client options object. */
export function withSeatbelt<T extends Record<string, any>>(openaiOptions: T, opts?: SeatbeltOptions): T & { baseURL: string; defaultHeaders: Record<string, string> } {
  return { ...openaiOptions, ...seatbeltConfig(opts) };
}
