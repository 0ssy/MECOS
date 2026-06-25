# Integration Plan: OpenOutreach + SalesGPT + ECC → MECOS

## Goal
Wire OpenOutreach skills into MECOS outreach workflows, integrate SalesGPT conversation engine, and enable ECC skills in the cognition loop — all without conflicting with mattpocock skills.

## Current State
- WorldMonitor: ✅ Integrated via `WorldMonitorAdapter` in OutreachAgent
- Email Enrichment: ✅ MECOS `EmailEnricher` with Hunter/Apollo/BetterContact
- DeliveryAgent: Basic templates, no conversational flow
- ECC Skills: 180+ skills available but not wired to MECOS
- MattPocock Skills: Loaded as stub tools, LLM-executable

## Decisions

### 1. OpenOutreach Skills Integration
**Direction**: Use ECC skills from `libs/ECC/skills/` in MECOS workflows
**Scope**: Import relevant skills (email, outreach, crm, social) as MECOS skill tools
**Non-goal**: Don't replace MECOS email system (keep `EmailEnricher`), just add skill guidance

### 2. SalesGPT Conversation Flow
**Integration Point**: Replace `DeliveryAgent.draft_email()` with SalesGPT multi-stage flow
**Trigger**: All leads with discovered emails (`contacts.emails` exists)
**Stages**: Introduction → Qualification → Value Proposition → Solution Presentation → Close
**Non-goal**: Don't replace MECOS SMTP pipeline, just generate better email content

### 3. ECC Skills in Cognition Loop
**Integration Point**: Import as additional tools alongside mattpocock skills
**Prefix**: ECC skills use `ecc:` prefix to avoid conflicts
**Selection**: Focus on engineering, CRM, and outreach-relevant skills
**Non-goal**: Don't import all 180 skills, curate by relevance

## Integration Tasks

### Phase A: ECC Skills Import (Non-conflicting)
- [ ] Create `ecc_skills.py` to discover/import ECC skills into ToolRegistry
- [ ] Skills use `ecc:` prefix (e.g., `ecc:email-ops`, `ecc:crm`, `ecc:social-graph-ranker`)
- [ ] Add to `tool_registry.load_skill()` to also scan `libs/ECC/skills/`
- [ ] Mattpocock skills keep `skill:` prefix, no overlap

### Phase B: SalesGPT Conversation Engine
- [ ] Create `sales_conversation_adapter.py` wrapping SalesGPT `step()`/`human_step()`
- [ ] Modify `DeliveryAgent.draft_for_lead()` to use SalesGPT flow when email exists
- [ ] Map MECOS lead brief to SalesGPT context:
  - `company_name` ← `lead_brief.domain`
  - `salesperson_name` ← "MECOS Automation Specialist"
  - `pain_points` ← `lead_brief.pain_points` as conversation context
- [ ] Export generated email via SalesGPT templates → MECOS SMTP pipeline

### Phase C: Outreach Skill Enhancement
- [ ] Import `libs/ECC/skills/email-ops`, `libs/ECC/skills/crm`, `libs/ECC/skills/workspace-surface-audit`
- [ ] Import `libs/ECC/skills/connections-optimizer` for social graph scoring
- [ ] Wire skill triggers in `Reasoner._match_skills()` for outreach context

### Phase D: SalesGPT Tool Integration
- [ ] Extend `SalesConversationAdapter` to pass MECOS tools to SalesGPT
- [ ] Map MECOS ToolRegistry tools to SalesGPT-compatible format
- [ ] Enable native tool-calling in SalesGPT context (collaboration mode)

## Data Flow
```
Lead Found (scanner)
    ↓
Email Enriched (EmailEnricher)
    ↓
SalesGPT Generate (SalesConversationAdapter)
    ↓
MECOS SMTP Send (DeliveryAgent._send_smtp)
    ↓
Revenue Tracked (RevenueLedger)
```

## Validation
1. `python -c "from ecc_skills import import_ecc_skills; import_ecc_skills()"` loads without error
2. Lead with email triggers SalesGPT flow → generates 60%+ more contextual content
3. ECC skills available as `ecc:*` tools in Reasoner plans
4. No naming conflicts between `skill:*` and `ecc:*` tools

## Risks
- ECC skills use different prompt formats than mattpocock → adapter needed
- SalesGPT expects product catalog → use service templates as fallback
- Multiple skill systems could overload LLM context → prefix filtering

## Open Questions
- Should ECC skills be imported lazily or at startup? (Recommend: startup for speed)
- How to handle SalesGPT's tool-calling when MECOS tools differ? (Recommend: disable SalesGPT tools, use MECOS context)