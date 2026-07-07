/**
 * @module errors
 * @description Custom error hierarchy for the VecminDB SDK.
 *
 * Every error thrown by the SDK is a subclass of {@link VecminError},
 * making it straightforward to catch and inspect failures.
 */

// ---------------------------------------------------------------------------
// Base Error
// ---------------------------------------------------------------------------

/**
 * Base error class for all VecminDB SDK errors.
 * Carries the HTTP status code for easy programmatic handling.
 */
export class VecminError extends Error {
  /** HTTP-style status code from the server response. */
  public readonly code: number;

  constructor(message: string, code: number) {
    super(message);
    this.name = "VecminError";
    this.code = code;
    // Restore the prototype chain that is broken by extending built-ins.
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

// ---------------------------------------------------------------------------
// Authentication / Authorization
// ---------------------------------------------------------------------------

/** Thrown when the request lacks valid credentials (HTTP 401). */
export class AuthenticationError extends VecminError {
  constructor(message = "Authentication failed or missing credentials") {
    super(message, 401);
    this.name = "AuthenticationError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/** Thrown when the authenticated identity lacks the required permission (HTTP 403). */
export class PermissionError extends VecminError {
  constructor(message = "Insufficient permissions") {
    super(message, 403);
    this.name = "PermissionError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/** Thrown when subscription payment or a valid license key is required (HTTP 402). */
export class PaymentRequiredError extends VecminError {
  constructor(message = "Subscription payment or valid license key required. Please register/activate your license at https://lingxinmind.com") {
    super(message, 402);
    this.name = "PaymentRequiredError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

// ---------------------------------------------------------------------------
// Resource Errors
// ---------------------------------------------------------------------------

/** Thrown when the requested resource does not exist (HTTP 404). */
export class NotFoundError extends VecminError {
  constructor(message = "Resource not found") {
    super(message, 404);
    this.name = "NotFoundError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

// ---------------------------------------------------------------------------
// Rate Limit / Transient Errors
// ---------------------------------------------------------------------------

/** Thrown when the server rate-limits the request (HTTP 429). */
export class RateLimitError extends VecminError {
  constructor(message = "Rate limit exceeded") {
    super(message, 429);
    this.name = "RateLimitError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

// ---------------------------------------------------------------------------
// Server Errors
// ---------------------------------------------------------------------------

/** Thrown for any 5xx server-side failure. */
export class ServerError extends VecminError {
  constructor(message = "Internal server error", code = 500) {
    super(message, code);
    this.name = "ServerError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

/**
 * Maps an HTTP status code to the most specific {@link VecminError} subclass.
 * Falls back to a generic {@link VecminError} for unrecognised codes.
 */
export function createErrorFromStatus(status: number, message: string): VecminError {
  switch (status) {
    case 401:
      return new AuthenticationError(message);
    case 402:
      return new PaymentRequiredError(message);
    case 403:
      return new PermissionError(message);
    case 404:
      return new NotFoundError(message);
    case 429:
      return new RateLimitError(message);
    default:
      if (status >= 500 && status < 600) {
        return new ServerError(message, status);
      }
      return new VecminError(message, status);
  }
}
