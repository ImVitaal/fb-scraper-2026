# Novel competitive-advantage findings

**Review date:** 2026-07-29  
**Status:** Reviewed and narrowed  
**Product:** FB Scraper 2026

## Executive conclusion

The strongest novel direction is a **closed-loop observable-discovery engine**.

It combines:

1. **Discovery Saturation Estimation** — estimate whether repeated queries have probably exhausted the observable result population.
2. **Message Family Query Expansion** — derive high-precision discovery queries from stable phrases found in reused message templates.

The combined loop is more valuable than either feature alone:

```text
Keyword and location seeds
    ↓
Deterministic discovery probes
    ↓
Observed entities and content
    ↓
Reusable message-family extraction
    ↓
Rare-anchor query generation
    ↓
Additional discovery probes
    ↓
Observable-coverage estimate
    ↓
STOP / CONTINUE / INCONCLUSIVE
```

This gives users an auditable answer to two important questions:

- **What relevant targets are we still likely missing?**
- **What evidence supports stopping discovery?**

## What was rejected as insufficiently novel

These remain important platform requirements, but they are not strong headline differentiators:

| Idea | Decision | Reason |
|---|---|---|
| Raw-response replay | Foundation | Mature evidence and web-archive systems already use replayable captures. |
| Provenance ledger | Foundation | Valuable, but established provenance standards already exist. |
| Semantic change detection | Foundation | Social-specific implementation is useful, but change-monitoring products already provide history and diffs. |
| Schema-drift detection | Foundation | Essential parser maintenance rather than a customer-defining innovation. |
| Confidence scoring | Supporting feature | Common unless backed by unusual calibration data and workflows. |
| Vector search | Supporting feature | Widely available and easily copied. |
| Local AI summaries | Reject for MVP | Low defensibility, uncertain value, and unnecessary model complexity. |
| Generic sentiment analysis | Reject | Commoditized and difficult to validate across languages and contexts. |
| Dashboard and alerts | Reject as differentiator | Expected product features rather than competitive advantages. |
| Standard entity resolution | Foundation | Necessary for canonical records, but not novel by itself. |

## Finding 1: Discovery Saturation Estimator

### Finding

Estimate how much of the **observable** Page, Group, Event, or Post population has been found through repeated keyword-and-location probes.

### User problem

A search result limit does not indicate discovery completeness.

A short result list can mean:

- Few relevant entities exist.
- The search source ranked them poorly.
- The query missed aliases or local terminology.
- Results were capped.
- Access or parser failures hid results.

Without a stopping rule, analysts either stop too early or waste time running redundant searches.

### Competitive gap

Reviewed competitors document search, extraction, pagination, scheduling, or result limits. Their inspected primary documentation did not expose:

- Estimated unseen entities.
- Observable-coverage confidence.
- Query-overlap analysis.
- A statistically justified stopping decision.
- Explicit uncertainty and assumption warnings.

This is a **weak-absence finding**. It does not prove that no private or undocumented system implements similar methods.

### Method

For one discovery campaign:

1. Fix the keyword, location, entity types, time window, and probe budget.
2. Generate deterministic, versioned query variants.
3. Run each query and retain result rank, source, health state, and raw record.
4. Canonicalize results by stable identifier or normalized URL.
5. Calculate:
   - Observed unique identifiers.
   - Singletons found by one probe.
   - Doubletons found by two probes.
   - Probe overlap.
   - New identifiers from the last three probes.
   - Rank instability.
6. Estimate the observable population using a bias-corrected capture–recapture estimator.
7. Bootstrap probe rows to produce a heuristic interval.
8. Return `STOP`, `CONTINUE`, or `INCONCLUSIVE`.

### Required guardrails

Return `INCONCLUSIVE` when:

- A discovery source reports overflow.
- A probe fails or produces an unhealthy response.
- Too few probes completed.
- Result overlap is insufficient for a stable estimate.
- The result population changes too quickly.
- Canonicalization quality falls below its release threshold.

Never describe the estimate as total Facebook coverage.

### CLI

```powershell
fbintel discover start `
  --keyword "live music" `
  --location "London" `
  --types page,group,event,post `
  --probe-set locale-v1 `
  --max-probes 12 `
  --stop-at 0.80 `
  --max-targets 100

fbintel discover status DISCOVERY_ID
fbintel discover report DISCOVERY_ID --format json
fbintel discover promote DISCOVERY_ID --top 100 --require-saturation 0.80
```

### Minimum data model

```text
discovery_campaign
  id
  keyword
  location
  entity_types
  probe_set_version
  maximum_probes
  stop_threshold
  status

discovery_probe
  id
  campaign_id
  ordinal
  family
  query
  result_count
  overflow
  health_state

discovery_hit
  probe_id
  canonical_id
  entity_type
  source_url
  result_rank
  raw_record

discovery_estimate
  campaign_id
  observed_count
  singleton_count
  doubleton_count
  estimated_observable_count
  coverage_estimate
  interval_low
  interval_high
  recent_new_count
  decision
  assumption_flags
```

### Acceptance test

Use synthetic hidden populations and deterministic probe-result fixtures.

Pass only when:

- Estimated population error is within ±20% across 50 seeded high-overlap simulations.
- The estimator never returns `STOP` during overflow or unhealthy probes.
- At least six probes complete before `STOP`.
- The last three probes add at most 2% new identifiers.
- The lower interval reaches the configured 80% coverage threshold.
- Identical input and seed produce byte-stable reports.

### Main limitation

Search probes are not statistically independent. Ranked results can bias capture–recapture estimates.

The product must expose assumptions, intervals, and failure flags instead of presenting false precision.

## Finding 2: Message Family Query Expansion

### Finding

Detect parameterized reused-message families and convert their rare stable phrases into precise discovery probes.

Example:

```text
"Join us this {DATE} at {PLACE} for the annual [STABLE PHRASE]"
```

The stable phrase can find relevant targets that broad keywords miss.

### What makes it useful

Ordinary discovery relies on the operator already knowing the correct keywords.

Observed Facebook content can reveal:

- Campaign slogans.
- Event-series names.
- Repeated calls to action.
- Local abbreviations.
- Organization-specific phrases.
- Shared announcements.

These phrases can become high-precision queries for new Pages, Groups, Events, and Posts.

### Boundary

The system detects **reused-message families**.

It does not assert:

- Coordination.
- Common authorship.
- Causation.
- Original publication.
- Organizational relationships.

Use **first locally observed**, not **originated by**.

### Method

1. Normalize Unicode, case, URLs, mentions, dates, times, amounts, numbers, and hashtags.
2. Generate word and character shingles.
3. Use MinHash and locality-sensitive hashing to find candidate pairs.
4. Align candidate texts.
5. Retain stable spans of at least four tokens.
6. Convert changing spans into typed slots.
7. Require two stable anchors and sufficient anchor coverage.
8. Group accepted pairs into conservative message families.
9. Select rare, discriminative anchors.
10. Generate bounded discovery queries using anchors, locations, and observed slot values.

### CLI

```powershell
fbintel families build --since 30d
fbintel families list --min-targets 2
fbintel families show FAMILY_ID
fbintel families queries FAMILY_ID --location "London" --limit 20
fbintel discover start --from-family FAMILY_ID
```

### Acceptance test

Create a blinded 600-pair evaluation set:

- 250 same-template pairs.
- 200 topically similar but different templates.
- 100 unrelated pairs.
- 50 short or generic pairs.

Pass only when:

- Accepted-pair precision is at least 95%.
- Same-template recall is at least 80% for texts of 40 characters or more.
- No generic pair is accepted.
- Family purity is at least 90% for families containing three or more items.
- Fingerprint-derived discovery improves precision by at least 20 percentage points over baseline keyword-and-location discovery.
- Build time remains below five minutes for 10,000 items on a four-core Windows computer.

### Main limitation

Boilerplate, quotations, shared news headlines, and platform-generated text can create false families.

Mitigations:

- Maintain a generic-anchor denylist.
- Require two long anchors.
- Exclude platform interface text.
- Cap free-text slot length.
- Split families when anchor coverage declines.
- Show the exact matching anchors.

## Combined innovation: Coverage-Guided Query Evolution

### Product concept

The recommended integration joins both findings into one bounded learning loop.

1. Begin with user keywords and locations.
2. Run deterministic discovery probes.
3. Collect content from discovered targets.
4. Extract reusable message families.
5. Generate rare-anchor probes.
6. Run those probes.
7. Measure how many new canonical entities they add.
8. Recalculate observable discovery saturation.
9. Stop only when the guarded threshold is satisfied.

### Why the combination is stronger

The Saturation Estimator supplies the stopping rule.

Message Family Query Expansion supplies evidence-driven new probes when ordinary keywords begin to saturate.

Together they create:

- Adaptive discovery without a paid model.
- Explainable query generation.
- Measured marginal discovery value.
- Bounded execution.
- Auditable stopping decisions.
- A dataset that improves future discovery.

### Defensibility

The statistical estimators and text-reuse algorithms are individually reproducible.

The defensible asset becomes the accumulated local system:

- Versioned probe sets.
- Canonicalization rules.
- Message-family labels.
- Query-yield history.
- Source-specific bias measurements.
- Calibration fixtures.
- Failure and assumption models.

This improves through actual use while keeping customer data local.

## Recommended implementation order

### Phase 1: Instrument discovery

- Store every probe, result, rank, source, and health state.
- Implement canonical identifiers and URL normalization.
- Export discovery receipts.

### Phase 2: Saturation estimation

- Add overlap statistics and guarded capture–recapture estimates.
- Implement `STOP`, `CONTINUE`, and `INCONCLUSIVE`.
- Validate exclusively on synthetic populations first.

### Phase 3: Message families

- Add deterministic normalization, shingles, MinHash, alignment, and template induction.
- Build labelled fixtures before enabling query generation.

### Phase 4: Close the loop

- Feed approved family queries into discovery campaigns.
- Measure marginal target yield.
- Recalculate saturation.
- Promote only high-confidence candidates to the 100-target watchlist.

## Go/no-go decision

Proceed with a prototype if:

- Discovery sources expose repeatable ranked result sets.
- Stable identifiers or canonical URLs can deduplicate results.
- At least six meaningfully different probe families can be generated.
- Synthetic testing shows useful estimator calibration.

Stop or restrict the feature if:

- Ranking volatility prevents stable overlap.
- Identifier quality causes excessive singleton inflation.
- Most probes terminate at hidden result caps.
- The estimator frequently produces unstable or unbounded intervals.
- Message-family queries do not improve discovery precision by 20 percentage points.

## Evidence

### Competitor and adjacent-product evidence

- [Bright Data Facebook Scraper documentation](https://docs.brightdata.com/datasets/scrapers/facebook/introduction)
- [Apify Facebook Search Scraper](https://apify.com/scrapesmith/facebook-search-scraper)
- [Data365 product presentation](https://data365.co/fr/presentation)
- [ScrapeCreators](https://scrapecreators.com/)
- [Thunderbit FAQ](https://thunderbit.com/docs/guides/faq)
- [PhantomBuster automation model](https://support.phantombuster.com/hc/en-us/articles/22306827153810-Understand-how-PhantomBuster-Works-and-What-you-can-Automate)
- [changedetection.io API](https://changedetection.io/docs/api_v1/index.html)
- [Maltego Evidence](https://support.maltego.com/en/support/solutions/articles/15000059648-maltego-evidence-transforms-in-maltego-graph)

### Technical foundations

- [Ranked deep-Web capture–recapture limitations](https://www.sciencedirect.com/science/article/pii/S0169023X10000447)
- [Capture–recapture identification constraints](https://arxiv.org/abs/2105.05373)
- [Text reuse in social networks](https://aclanthology.org/W14-2707.pdf)
- [Anti-unification survey](https://arxiv.org/abs/2302.00277)
- [`datasketch` MinHash and LSH](https://github.com/ekzhu/datasketch)
- [Meta Group privacy](https://www.facebook.com/help/220336891328465?locale=en_GB)

## Final recommendation

Build the **Discovery Saturation Estimator** first.

Add **Message Family Query Expansion** only after sufficient text history and labelled evaluation data exist.

Market the combined capability as:

> **Coverage-guided Facebook discovery with explainable query evolution and explicit uncertainty.**

Do not market it as complete Facebook discovery.

