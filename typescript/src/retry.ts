/**
 * @module retry
 * @description Configurable exponential-backoff retry strategy for transient failures.
 */

import type { RetryOptions } from "./models.js";
import { createErrorFromStatus, RateLimitError, VecminError } from "./errors.js";

/** Default retry configuration. */
const DEFAULTS: Required<RetryOptions> = {
  maxRetries: 3,
  backoffFactor: 0.5,
  retryableStatusCodes: [429, 500, 502, 503, 504],
};

/**
 * Resolve the effective retry options by merging caller-provided values
 * with SDK defaults.
 */
export function resolveRetryOptions(opts?: RetryOptions): Required<RetryOptions> {
  return {
    maxRetries: opts?.maxRetries ?? DEFAULTS.maxRetries,
    backoffFactor: opts?.backoffFactor ?? DEFAULTS.backoffFactor,
    retryableStatusCodes: opts?.retryableStatusCodes ?? DEFAULTS.retryableStatusCodes,
  };
}

/**
 * Sleep for the given number of milliseconds.
 * A thin wrapper so we don't need to polyfill `setTimeout` return types.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Determine whether an error / status combination is retryable.
 */
function isRetryable(status: number, retryableCodes: number[]): boolean {
  return retryableCodes.includes(status);
}

/**
 * Execute an async function with exponential-backoff retry semantics.
 *
 * @param fn         - The async operation to attempt.
 * @param options    - Retry configuration.
 * @returns          - The result of `fn` on success.
 * @throws           - The last {@link VecminError} when all retries are exhausted.
 *
 * @example
 * ```ts
 * const data = await withRetry(() => fetchJson("/api/v1/collections"), { maxRetries: 5 });
 * ```
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  options?: RetryOptions,
): Promise<T> {
  const opts = resolveRetryOptions(options);
  let lastError: VecminError | undefined;

  for (let attempt = 0; attempt <= opts.maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      // Only retry on VecminError with a retryable status code.
      if (err instanceof VecminError && isRetryable(err.code, opts.retryableStatusCodes)) {
        lastError = err;

        // Respect Retry-After header on 429 if the error carries it.
        let delayMs: number;
        if (err instanceof RateLimitError && (err as RateLimitError & { retryAfter?: number }).retryAfter) {
          delayMs = ((err as RateLimitError & { retryAfter?: number }).retryAfter ?? 1) * 1000;
        } else {
          delayMs = opts.backoffFactor * Math.pow(2, attempt) * 1000;
        }

        // Add ±100 ms jitter to avoid thundering-herd retries.
        const jitter = Math.random() * 200 - 100;
        await sleep(Math.max(0, delayMs + jitter));
        continue;
      }

      // For non-retryable errors, re-throw immediately.
      throw err;
    }
  }

  // All retries exhausted.
  throw lastError ?? new VecminError("All retry attempts exhausted", 0);
}

/**
 * Lightweight wrapper around `fetch` that:
 * 1. Throws structured {@link VecminError} subclasses on non-2xx responses.
 * 2. Parses the standard VecminDB response envelope `{code, message, data}`.
 *
 * This is the single point of HTTP I/O for the SDK.
 */
export async function fetchJson<T>(
  url: string,
  init: RequestInit,
  retryOpts?: RetryOptions,
): Promise<T> {
  return withRetry(async () => {
    const res = await fetch(url, init);

    // Read the body once — needed for both success and error paths.
    const body = (await res.json()) as { code?: number; message?: string; data?: T; error?: string };

    if (!res.ok) {
      const message =
        body?.error ?? body?.message ?? `HTTP ${res.status}`;
      const code = body?.code ?? res.status;
      throw createErrorFromStatus(code, message);
    }

    // The server wraps successful payloads in `{code, message, data}`.
    // If `data` is present, unwrap it; otherwise return the raw body.
    return (body?.data !== undefined ? body.data : body) as T;
  }, retryOpts);
}
