//! Runnable example: wire a hand-rolled agent loop to VecminDB memory
//! in two lines with AgentMemory.
//!
//!   cargo run --example agent_memory
//!
//! Replace ENDPOINT / API_KEY with your deployment. Memory never breaks
//! the agent: on network failure both calls degrade to no-ops.

use vecmindb_client::AgentMemory;

const ENDPOINT: &str = "http://localhost:5520";
const API_KEY: &str = "";

/// Stand-in for the agent's own LLM call — in a real agent this is your model.
fn fake_llm(question: &str, context: &str) -> String {
    if context.is_empty() {
        format!("answered (no relevant memory): {question}")
    } else {
        let memories = context.lines().count().saturating_sub(1);
        format!("[using {memories} memories] answered: {question}")
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mem = AgentMemory::connect(ENDPOINT, API_KEY, "example-agent");

    let turns = [
        "客户对部署方式有什么要求?", // related -> before_turn returns memories
        "今天晚饭吃什么好呢?",       // unrelated -> before_turn returns "" (relevance gate)
    ];
    for question in turns {
        let context = mem.before_turn(question, 3)?;
        let reply = fake_llm(question, &context);
        println!("Q: {question}");
        println!("context: {}", if context.is_empty() { "(empty — gated)" } else { &context });
        println!("A: {reply}");
        let memory_id = mem.after_turn(question, &reply, None)?;
        println!("stored: {}\n", memory_id.unwrap_or_else(|| "(skipped/failed)".into()));
    }
    Ok(())
}
