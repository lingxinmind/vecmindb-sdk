/**
 * VecminDB TypeScript / Node.js SDK - 01 Quickstart Example
 * 
 * Demonstrates:
 * 1. Initializing VecminClient.
 * 2. Mounting an Agent Cognitive Memory Space.
 * 3. Storing & Searching memories asynchronously.
 */

import { VecminClient, AgentMemoryManager } from '../src';

async function main() {
  const endpoint = 'http://localhost:5520';
  console.log('=== VecminDB TypeScript SDK Quickstart ===');
  console.log(`Connecting to VecminDB server at ${endpoint}...`);

  try {
    const client = new VecminClient({ baseUrl: endpoint });
    console.log('✓ Successfully initialized VecminClient.');

    // 2. Collection Creation (Name & Optional Domain Only)
    // Built-in Supported Domains ("domain"):
    //   - "general"       : General Purpose Default
    //   - "finance"       : Financial Risk & Asset Management
    //   - "medical"       : Healthcare & Patient Clinical Records
    //   - "legal"         : Legal Contracts & Compliance Terms
    //   - "hr"            : Human Resources & Recruitment
    //   - "code"/"software": Software Specs & Source Code
    //   - "ecommerce"     : E-Commerce & Retail Logistics
    //   - "manufacturing" : Industrial Manufacturing & Quality Control
    //   - "insurance"     : Insurance Policy & Claims Processing
    //   - "education"     : Education & Academic Records

    // Option A: Zero-Param Creation
    await client.createCollection({ name: 'my_documents' });

    // Option B: Domain-Anchored Creation
    await client.createCollection({ name: 'financial_reports', domain: 'finance' });
    console.log("✓ Collections created successfully with domain factuality anchoring!");
    const manager = new AgentMemoryManager({
      client,
      agentId: 'demo_agent_node_01',
      sovereigntyToken: 'demo_sovereign_secret_99'
    });

    console.log('Mounting memory space...');
    const memory = await manager.mountMemory({ collectionName: 'financial_reports' });
    console.log('✓ Memory space mounted successfully.');

    // 3. Store Memories
    console.log('\nStoring episodic memories...');
    await memory.storeMemory('User prefers drinking espresso in the morning.');
    await memory.storeMemory('User works as a full-stack TypeScript engineer.');
    console.log('✓ Memories stored.');

    // 4. Search Memories
    const query = 'What does user like to drink?';
    console.log(`\nSearching memories with query: '${query}'...`);
    const results = await memory.searchMemory({ query, topK: 2 });

    console.log('=== Search Results ===');
    console.log(JSON.stringify(results, null, 2));

    console.log('\n✓ Quickstart completed successfully!');
  } catch (error) {
    console.log(`\n[Note] Server connection test: ${error}`);
    console.log('Make sure VecminDB server is running at http://localhost:5520.');
  }
}

main();
