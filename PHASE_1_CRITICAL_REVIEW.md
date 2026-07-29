# Phase 1 critical review

**Review date:** 2026-07-29
**Reviewed revision:** `PHASE_1_OPTIMAL_PLAN.md` Revision 3
**Verdict:** Ready as the Phase 1 implementation source.

## Why Revision 2 was replaced

Revision 2 optimized for public Page discovery and collection.

The operator changed the product driver:

- Private-Group scanning comes first.
- Posts and top-level comments form the first content contract.
- One working Group demo comes before scale.
- Correctness and resume behavior come before speed.
- Competitor comparison begins only after the local workflow works.
- Other surfaces follow only after the private-Group advantage is proven.

## Critical corrections in Revision 3

### Phase boundaries are explicit

The programme now separates:

1. One-Group correctness.
2. Ten-Group performance.
3. Competitor proof.
4. Product expansion.

This prevents performance optimization and feature breadth from blocking the
first usable vertical slice.

### The demo contract is exact

Phase 1 requires:

- Equal imported-session and guided-login workflows.
- Keyword-and-location Group discovery.
- One selected Group.
- Thirty days of posts.
- Every visible top-level comment on matching posts.
- No reply expansion.
- Raw capture, normalization, exports, resume, and offline replay.

### Authentication is separated from collection

Guided login occurs in a visible controlled browser.

Collection workers consume only an encrypted session envelope. They never
receive or persist account passwords.

### Private evidence receives shorter retention

Private raw captures use a 30-day default.

Normalized records retain the earlier 90-day default. Cleanup produces deletion
receipts.

### Performance claims are delayed

Phase 1 records performance metrics but sets no superiority threshold.

Phase 3 will select competitors and define equal-contract comparison gates after
the working demo and ten-Group performance phase.

### Agent execution is bounded

Revision 3 defines:

- Work-item identifiers.
- Dependencies.
- Safe execution waves.
- Disjoint file ownership.
- Required tests.
- Evidence receipts.
- Coordinator-owned integration.
- Final closure gates.

This structure supports repeated agent work without losing scope or evidence.

## Residual risks

### Source-layout drift

Private Group layouts and session flows can change.

Mitigation:

- Immutable raw captures.
- Versioned parsers.
- Replay fixtures.
- Mutation tests.
- Explicit parser-drift states.

### Session instability

Sessions can expire, receive challenges, or lose Group visibility.

Mitigation:

- Explicit health states.
- Pre-run inspection.
- Equal session preparation methods.
- Durable job states.
- No silent success.

### Comment workload variability

One post can contain many top-level comments.

Phase 1 prioritizes correctness and records workload size. Phase 2 adds workload
classes, budgets, and optimization.

### Discovery variability

Keyword-and-location results can vary by session and time.

Fixture discovery gates deterministic behavior. The controlled demo records the
exact query, candidates, timestamp, and health state.

## Review conclusion

Revision 3 is decision-complete for Phase 1.

Implementation must follow the work-item graph and evidence gates. Performance
optimization, competitor claims, and additional surfaces remain outside Phase 1.
