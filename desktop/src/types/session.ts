/** Tokens as held by the main process. Mirrors `electron/preload.ts`. */
export interface StoredSession {
  accessToken: string;
  refreshToken: string;
}
