//! VecminDB client SDK for hand-rolled agents.
//!
//! Two lines wire any agent loop to the cognitive memory layer:
//!
//! ```no_run
//! use vecmindb_client::AgentMemory;
//!
//! let your_llm = |question: &str, context: &str| -> String {
//!     if context.is_empty() {
//!         format!("answered (no relevant memory): {question}")
//!     } else {
//!         format!("[using memories] answered: {question}")
//!     }
//! };
//! let mem = AgentMemory::connect("http://host:5520", "api-key", "my-agent");
//! let context = mem.before_turn("customer requirements", 3)?; // "" when gated
//! let reply = your_llm("customer requirements", &context);
//! let _memory_id = mem.after_turn("customer requirements", &reply, None)?;
//! # Ok::<(), Box<dyn std::error::Error>>(())
//! ```
//!
//! Invariants (same semantics as the Python/TypeScript SDKs):
//! - `before_turn` returns an EMPTY STRING for unrelated queries — the
//!   server-side relevance gate (`memory.search_min_score`, default 0.70)
//!   answers "No relevant memory" instead of returning least-dissimilar
//!   neighbors, so clients carry zero threshold logic.
//! - Memory never breaks the agent: network failures degrade to empty
//!   context / `Ok(None)` stores instead of panicking.
//! - `after_turn` auto-summarizes (question + first 200 chars of the
//!   reply) unless a `summary` is supplied; `summary: None` means
//!   auto, `Some("")` skips the store.

mod agent_memory;
mod client;

pub use agent_memory::{auto_summary, AfterTurnOptions, AgentMemory};
pub use client::{ClientError, VecminClient};
