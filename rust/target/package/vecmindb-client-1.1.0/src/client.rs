//! Minimal HTTP client for the VecminDB MCP message endpoint.

use std::time::Duration;

use serde_json::{json, Value};

/// Errors surfaced by the client. The SDK's agent-facing helpers never
/// panic: they convert any failure into a degraded no-op.
#[derive(Debug)]
pub struct ClientError(pub String);

impl std::fmt::Display for ClientError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "vecmindb client error: {}", self.0)
    }
}

impl std::error::Error for ClientError {}

impl From<reqwest::Error> for ClientError {
    fn from(e: reqwest::Error) -> Self {
        ClientError(e.to_string())
    }
}

/// Blocking HTTP client for the `/api/v1/mcp/message` JSON-RPC endpoint.
pub struct VecminClient {
    http: reqwest::blocking::Client,
    endpoint: String,
    api_key: String,
    agent_id: String,
}

impl VecminClient {
    pub fn new(base_url: &str, api_key: &str, agent_id: &str) -> Self {
        let http = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(60))
            .build()
            .expect("static client configuration is valid");
        Self {
            http,
            endpoint: format!("{}/api/v1/mcp/message", base_url.trim_end_matches('/')),
            api_key: api_key.to_string(),
            agent_id: agent_id.to_string(),
        }
    }

    /// Calls an MCP tool by name and returns the text of the first
    /// content item (the server's human-readable report).
    pub fn mcp_call(&self, tool: &str, arguments: Value) -> Result<String, ClientError> {
        let body = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": { "name": tool, "arguments": arguments },
        });
        let resp = self
            .http
            .post(&self.endpoint)
            .header("content-type", "application/json")
            .header("x-api-key", &self.api_key)
            .json(&body)
            .send()?;
        let data: Value = resp.json()?;
        data["result"]["content"]
            .get(0)
            .and_then(|c| c["text"].as_str())
            .map(|s| s.to_string())
            .ok_or_else(|| {
                ClientError(format!(
                    "unexpected response shape: {}",
                    serde_json::to_string(&data).unwrap_or_default()
                ))
            })
    }

    pub fn agent_id(&self) -> &str {
        &self.agent_id
    }
}
