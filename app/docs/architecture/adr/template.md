# ADR-000: Template for Architecture Decision Records

**Date**: YYYY-MM-DD  
**Status**: [Proposed | Accepted | Rejected | Deprecated | Superseded]  
**Deciders**: [List of people involved in the decision]  
**Technical Story**: [Link to issue or ticket if applicable]

## Context and Problem Statement

[Describe the context and problem statement, e.g., in free form using two to three sentences. You may want to articulate the problem in form of a question.]

## Decision Drivers

- [Driver 1, e.g., a force, facing concern, ...]
- [Driver 2, e.g., a force, facing concern, ...]
- [Driver 3, e.g., a force, facing concern, ...]
- [...]

## Considered Options

- [Option 1]
- [Option 2]
- [Option 3]
- [...]

## Decision Outcome

Chosen option: "[Option X]", because [justification. e.g., only option, which meets k.o. criterion decision driver | which resolves force force | ... | comes out best (see below)].

### Positive Consequences

- [e.g., improvement of quality attribute satisfaction, follow-up decisions required, ...]
- [...]

### Negative Consequences

- [e.g., compromising quality attribute, follow-up decisions required, ...]
- [...]

## Pros and Cons of the Options

### [Option 1]

[Example | Description | Pointer to more information | ...]

- Good, because [argument a]
- Good, because [argument b]
- Bad, because [argument c]
- [...]

### [Option 2]

[Example | Description | Pointer to more information | ...]

- Good, because [argument a]
- Good, because [argument b]
- Bad, because [argument c]
- [...]

### [Option 3]

[Example | Description | Pointer to more information | ...]

- Good, because [argument a]
- Good, because [argument b]
- Bad, because [argument c]
- [...]

## Links

- [Link type] [Link to ADR] <!-- example: Refined by [ADR-0005](0005-example.md) -->
- [...]

---

## Template Usage Instructions

1. **Copy this template** to create a new ADR
2. **Number sequentially** (ADR-001, ADR-002, etc.)
3. **Use descriptive titles** that summarize the decision
4. **Include all stakeholders** in the decision process
5. **Document alternatives** even if they were quickly dismissed
6. **Update status** as decisions evolve
7. **Link related ADRs** to maintain decision history

## ADR Naming Convention

```
ADR-NNN-short-title.md

Examples:
ADR-001-choose-database-technology.md
ADR-002-authentication-strategy.md
ADR-003-frontend-framework-selection.md
```

## Status Definitions

- **Proposed**: Decision is being considered but not yet finalized
- **Accepted**: Decision has been approved and is being implemented
- **Rejected**: Decision was considered but ultimately not chosen
- **Deprecated**: Decision is no longer current but still in effect
- **Superseded**: Decision has been replaced by a newer ADR