// Truebex MCP server (roadmap 40 / AI1): newline-delimited JSON-RPC 2.0 framing.
//
// The stdio binding: one message per line, UTF-8, no embedded newline; stdout
// carries ONLY MCP messages (logs go to stderr). The same framing runs on the
// named pipe into the app (truebex-agent-wire/1), so both ends share LineReader.

export const PARSE_ERROR = -32700;
export const INVALID_REQUEST = -32600;
export const METHOD_NOT_FOUND = -32601;
export const INVALID_PARAMS = -32602;
export const INTERNAL_ERROR = -32603;
/** UnsupportedProtocolVersion (MCP 2026-07-28, basic/versioning). */
export const UNSUPPORTED_VERSION = -32022;

/** At most 1 MiB a line, in either direction. */
export const MAX_LINE_BYTES = 1024 * 1024;

/**
 * Splits a byte stream into lines and hands each non-empty one to onLine.
 * A line longer than MAX_LINE_BYTES is dropped and reported through onOversize.
 */
export class LineReader {
  constructor(onLine, onOversize) {
    this.onLine = onLine;
    this.onOversize = onOversize || (() => {});
    this.chunks = [];
    this.length = 0;
    this.skipping = false;
  }

  push(chunk) {
    let start = 0;
    for (;;) {
      const nl = chunk.indexOf(10, start);
      if (nl < 0) {
        const rest = chunk.subarray(start);
        if (this.skipping) { return; }
        if (this.length + rest.length > MAX_LINE_BYTES) {
          this.reset();
          this.skipping = true;
          this.onOversize();
          return;
        }
        if (rest.length) { this.chunks.push(rest); this.length += rest.length; }
        return;
      }
      const piece = chunk.subarray(start, nl);
      start = nl + 1;
      if (this.skipping) { this.skipping = false; this.reset(); continue; }
      if (this.length + piece.length > MAX_LINE_BYTES) { this.reset(); this.onOversize(); continue; }
      this.chunks.push(piece);
      const line = Buffer.concat(this.chunks).toString('utf8').replace(/\r$/, '');
      this.reset();
      if (line.trim().length) { this.onLine(line); }
    }
  }

  reset() { this.chunks = []; this.length = 0; }
}

/** One JSON value on one line (JSON.stringify never emits a raw newline). */
export function frame(message) {
  return JSON.stringify(message) + '\n';
}

export function isRequest(m) {
  return m && typeof m === 'object' && !Array.isArray(m) && typeof m.method === 'string' && 'id' in m && m.id !== null;
}

export function isNotification(m) {
  return m && typeof m === 'object' && !Array.isArray(m) && typeof m.method === 'string' && !('id' in m);
}

export function errorResponse(id, code, message, data) {
  const error = { code, message };
  if (data !== undefined) { error.data = data; }
  return { jsonrpc: '2.0', id: id === undefined ? null : id, error };
}

export function resultResponse(id, result) {
  return { jsonrpc: '2.0', id, result };
}
