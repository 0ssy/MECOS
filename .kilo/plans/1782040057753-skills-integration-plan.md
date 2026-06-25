# MECOS Skills Integration Plan

## Goal
Integrate the 17 newly added Kilo skills into MECOS's cognitive architecture to enhance agent capabilities, enable MCP server connectivity, and improve LLM-powered planning.

## Status: COMPLETED ✓

## Context
- 17 skills loaded into ToolRegistry (marketing, social-media, financial, legal, etc.)
- Skills now wired to agents
- MCP servers configured (notion, slack, granola, zapier) and integrated
- LLM provider abstraction implemented

## Implementation Summary

### Phase A: Agent Integration ✓
- [x] Created `compliance_agent.py` for legal-workflow skill
- [x] Extended `trading_agent.py` with MarketingSentimentAnalyzer mixin and social sentiment
- [x] Extended `reasoner.py` with skill-aware planning and trigger matching
- [x] Updated `main.py` to register compliance_agent

### Phase B: MCP Connectivity ✓
- [x] Added `mcp_client_register_skill_tools()` method to tool_orchestrator.py
- [x] Added `register_mcp_from_config()` for skill-based MCP wrapper
- [x] MCP servers (notion, slack, granola, zapier) registered as mcp:* tools

### Phase C: Reasoner Enhancement ✓
- [x] Added `_load_skill_triggers()` to extract skill keywords
- [x] Added `_match_skills()` to detect skill matches in goals
- [x] Added `_skill_tools_context()` to provide tool descriptions
- [x] Added `invoke_skill()` method for direct skill invocation
- [x] Updated `_build_plan_prompt()` with skill tool examples

### Phase D: LLM Upgrade Path ✓
- [x] Added `LLM_ROUTER` setting (local | openai | anthropic | google)
- [x] Added `LLM_PROVIDERS` configuration in config.py
- [x] Updated `mecos_llm.py` with provider-aware client initialization
- [x] Added environment variables to `.env.example`

## Files Changed
- `compliance_agent.py` - NEW: Legal workflow agent
- `trading_agent.py` - Added MarketingSentimentAnalyzer mixin
- `reasoner.py` - Extended with skill-aware planning
- `tool_orchestrator.py` - Added MCP skill tool registration
- `config.py` - Added LLM_PROVIDERS and MCP_SERVERS config
- `mecos_llm.py` - Added router-based client initialization
- `main.py` - Added compliance_agent registration and MCP skill tools
- `.env.example` - Added MCP and LLM provider environment variables

## Validation
Run `python -m py_compile compliance_agent.py trading_agent.py reasoner.py tool_orchestrator.py config.py mecos_llm.py main.py` to verify syntax.