//! Turn-loop memory primitives with the same semantics as the
//! Python/TypeScript SDKs.

use regex::Regex;
use serde_json::json;

use crate::client::{ClientError, VecminClient};

/// Characters kept from the reply tail in an auto-generated summary.
const SUMMARY_CHAR_CAP: usize = 200;

/// Options for [`AgentMemory::after_turn`].
#[derive(Debug, Default, Clone)]
pub struct AfterTurnOptions {
    /// Override the auto-generated summary. `Some("")` skips the store
    /// entirely (empty chatter); `None` means auto-summarize.
    pub summary: Option<String>,
    /// Mark durable constraints/decisions for strong anchoring.
    pub is_factual: bool,
}

impl AfterTurnOptions {
    pub fn skip() -> Self {
        Self {
            summary: Some(String::new()),
            ..Default::default()
        }
    }
}

/// Builds the default stored summary: question + capped reply tail.
pub fn auto_summary(question: &str, reply: &str) -> String {
    let tail = reply.trim();
    if tail.chars().count() > SUMMARY_CHAR_CAP {
        let truncated: String = tail.chars().take(SUMMARY_CHAR_CAP).collect();
        return format!("Q: {}\nA: {}...", question.trim(), truncated.trim_end());
    }
    format!("Q: {}\nA: {}", question.trim(), tail)
}

fn extract_context(report: &str) -> String {
    // Gate check first: the server answers honestly when nothing clears
    // the relevance floor.
    if report.contains("No relevant memory") {
        return String::new();
    }
    let score_re = Regex::new(r"^\d+\. \[Score: ([\d.]+)\] ID: (\S+)").expect("static regex");
    let mut hits: Vec<(f32, String)> = Vec::new();
    let mut current: Option<(f32, String)> = None;
    for line in report.lines() {
        if let Some(caps) = score_re.captures(line.trim()) {
            if let Some(prev) = current.take() {
                hits.push(prev);
            }
            current = Some((caps[1].parse().unwrap_or(0.0), String::new()));
            continue;
        }
        if let Some(hit) = current.as_mut() {
            if let Some(text) = line.trim().strip_prefix("Text: ") {
                hit.1 = text.to_string();
            }
        }
    }
    if let Some(prev) = current.take() {
        hits.push(prev);
    }
    let usable: Vec<_> = hits.into_iter().filter(|(_, t)| !t.is_empty()).collect();
    if usable.is_empty() {
        return String::new();
    }
    let mut lines = vec!["[Relevant memories]".to_string()];
    for (score, text) in &usable {
        lines.push(format!("- ({score:.2}) {text}"));
    }
    lines.join("\n")
}

/// Turn-loop memory facade. Never panics on network failures: context
/// degrades to empty and stores degrade to `Ok(None)`.
pub struct AgentMemory {
    client: VecminClient,
}

impl AgentMemory {
    pub fn connect(base_url: &str, api_key: &str, agent_id: &str) -> Self {
        Self {
            client: VecminClient::new(base_url, api_key, agent_id),
        }
    }

    /// Returns a prompt-injectable context block, or "" when nothing
    /// clears the relevance gate.
    pub fn before_turn(&self, query: &str, top_k: usize) -> Result<String, ClientError> {
        let report = match self.client.mcp_call(
            "search_memory",
            json!({ "query": query, "top_k": top_k }),
        ) {
            Ok(r) => r,
            Err(e) => {
                log_warn(&e);
                return Ok(String::new());
            }
        };
        Ok(extract_context(&report))
    }

    /// Stores this turn's memory; `Ok(None)` when skipped or the store
    /// failed. `options.summary` = None auto-summarizes, Some("") skips.
    pub fn after_turn(
        &self,
        question: &str,
        reply: &str,
        options: Option<AfterTurnOptions>,
    ) -> Result<Option<String>, ClientError> {
        let opts = options.unwrap_or_default();
        let summary = match &opts.summary {
            Some(s) if s.is_empty() => return Ok(None), // explicit skip
            Some(s) => s.clone(),
            None => auto_summary(question, reply),
        };
        let arguments = json!({
            "text": summary,
            "is_factual": opts.is_factual,
            "agent_id": self.client.agent_id(),
        });
        match self.client.mcp_call("store_memory", arguments) {
            Ok(report) => Ok(Some(report)),
            Err(e) => {
                log_warn(&e);
                Ok(None)
            }
        }
    }
}

/// The SDK has no logging dependency; surface degradations on stderr so
/// the agent operator can see them without a panic.
fn log_warn(err: &ClientError) {
    eprintln!("[vecmindb] degraded to no-op: {err}");
}

#[cfg(test)]
mod tests {
    use super::*;

    const REPORT_WITH_HITS: &str = "Retrieved 2 relevant semantic anchors from domain 'system':\n\
1. [Score: 0.9123] ID: abc123\n   Text: customer requires SLA 99.9%\n\
2. [Score: 0.7031] ID: def456\n   Text: audit logs kept 180 days\n";

    #[test]
    fn auto_summary_truncates_reply_tail() {
        let s = auto_summary("question?", &"x".repeat(500));
        assert!(s.starts_with("Q: question?\nA: "));
        let tail = s.split("A: ").nth(1).unwrap();
        assert!(tail.chars().count() <= SUMMARY_CHAR_CAP + 3); // + "..."
    }

    #[test]
    fn auto_summary_handles_empty_reply() {
        assert_eq!(auto_summary("q", ""), "Q: q\nA: ");
    }

    #[test]
    fn extract_context_formats_hits() {
        let ctx = extract_context(REPORT_WITH_HITS);
        assert!(ctx.contains("[Relevant memories]"));
        assert!(ctx.contains("0.91"));
        assert!(ctx.contains("customer requires SLA 99.9%"));
    }

    #[test]
    fn extract_context_gates_empty_reports() {
        let ctx = extract_context(
            "No relevant memory found in domain 'system' (no match cleared threshold 0.70).",
        );
        assert_eq!(ctx, "");
    }

    #[test]
    fn extract_context_returns_empty_on_unparseable_reports() {
        assert_eq!(extract_context("some totally unexpected format"), "");
    }

    #[test]
    fn extract_context_handles_chinese_reports() {
        let report = "Retrieved 1 relevant semantic anchors from domain 'system':\n\
1. [Score: 0.9213] ID: c0ffee\n   Text: 数据不得出网\n";
        let ctx = extract_context(report);
        assert!(ctx.contains("数据不得出网"));
    }
}
