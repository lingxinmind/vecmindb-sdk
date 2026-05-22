/**
 * @module auth
 * @description Authentication manager for the VecminDB SDK.
 *
 * Handles:
 * - API-Key injection via the `x-api-key` header.
 * - JWT token management with automatic refresh (5 minutes before expiry).
 * - Token caching and thread-safe access.
 */

import type { VecminClientOptions, LoginParams } from "./models.js";
import { fetchJson } from "./retry.js";

// ---------------------------------------------------------------------------
// JWT Utilities
// ---------------------------------------------------------------------------

/**
 * Decode the payload of a JWT without verifying the signature.
 * Returns `null` if the token is malformed.
 */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length < 2) return null;
    // Base64url decode
    const base64 = parts[1]!.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join(""),
    );
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/**
 * Determine whether a JWT is expired or about to expire.
 *
 * @param token     - The raw JWT string.
 * @param bufferMs  - Safety margin in ms.  @default 300_000 (5 min)
 * @returns `true` if the token is expired or will expire within the buffer.
 */
function isJwtExpiringSoon(token: string, bufferMs = 5 * 60 * 1000): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload) return true; // Unparseable → treat as expired.

  const exp = payload["exp"];
  if (typeof exp !== "number") return true; // No exp claim → treat as expired.

  return Date.now() >= (exp * 1000 - bufferMs);
}

// ---------------------------------------------------------------------------
// AuthManager
// ---------------------------------------------------------------------------

/**
 * Manages authentication state for the SDK client.
 *
 * ### API-Key mode
 * Injects `x-api-key: <key>` on every request.
 *
 * ### JWT mode
 * Injects `Authorization: Bearer <jwt>`.
 * When the JWT is within 5 minutes of expiry the manager automatically
 * re-authenticates via `POST /api/v1/cluster/login`.
 */
export class AuthManager {
  private apiKey?: string;
  private jwt?: string;
  private loginParams?: LoginParams;
  private baseUrl: string;
  private refreshPromise: Promise<string | null> | null = null;

  constructor(baseUrl: string, options: VecminClientOptions) {
    this.baseUrl = baseUrl;
    this.apiKey = options.apiKey;
    this.jwt = options.jwt;
  }

  /**
   * Store login credentials so the manager can automatically refresh the JWT.
   * Called internally by {@link VecminClient.login}.
   */
  setLoginCredentials(params: LoginParams, jwt: string): void {
    this.loginParams = params;
    this.jwt = jwt;
  }

  /**
   * Return the HTTP headers needed for the next request.
   *
   * If a JWT is present and not expiring soon, uses `Authorization: Bearer`.
   * Otherwise falls back to `x-api-key` (if configured).
   *
   * When both are configured, JWT takes precedence; if the JWT is expiring
   * the method triggers a background refresh and falls back to the API key
   * for the current request.
   */
  async getHeaders(): Promise<Record<string, string>> {
    const headers: Record<string, string> = {};

    if (this.jwt) {
      if (isJwtExpiringSoon(this.jwt)) {
        // Attempt a transparent refresh.
        const freshJwt = await this.refreshJwt();
        if (freshJwt) {
          headers["Authorization"] = `Bearer ${freshJwt}`;
        } else if (this.apiKey) {
          headers["x-api-key"] = this.apiKey;
        }
      } else {
        headers["Authorization"] = `Bearer ${this.jwt}`;
      }
    } else if (this.apiKey) {
      headers["x-api-key"] = this.apiKey;
    }

    return headers;
    }

  /**
   * Attempt to refresh the JWT by re-posting the stored login credentials.
   * Uses a singleton promise so concurrent calls don't trigger multiple logins.
   */
  private async refreshJwt(): Promise<string | null> {
    if (!this.loginParams) return null;

    // Coalesce concurrent refresh attempts.
    if (this.refreshPromise) return this.refreshPromise;

    this.refreshPromise = (async () => {
      try {
        const result = await fetchJson<string>(
          `${this.baseUrl}/api/v1/cluster/login`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(this.loginParams),
          },
          { maxRetries: 1 }, // Don't retry aggressively on auth failures.
        );
        this.jwt = result;
        return result;
      } catch {
        return null;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }
}
