# Additional Facebook scraper research

**Research date:** 2026-07-29  
**Status:** Revision 2 complete

## Recommended MVP decision

Build a **hybrid public-business intelligence product**.

- Build canonical schemas, job orchestration, checkpoints, replay, monitoring, validation, and delivery.
- Use managed providers as temporary collection adapters and benchmark references.
- Use Meta APIs as official validation sources where access permits.
- Start with Pages, public Page posts, Ads, and Events.
- Defer personal profiles, Group members, Comments at scale, and Marketplace until proof tests pass.

### MVP release gate

Release only when:

1. Required identifiers achieve 100% precision.
2. Supported required fields achieve at least 99% accuracy.
3. Pagination achieves at least 99.5% completeness on labelled fixtures.
4. Interrupted jobs resume without loss.
5. Every missing field has a null reason.
6. Every output field has provenance.
7. Measured cost stays within the approved complete-record ceiling.

## Executive summary

Two research lanes evaluated managed Facebook data products, generic extraction infrastructure, official Meta APIs, and open-source implementations.

### Main findings

1. **Bright Data** is the strongest enterprise benchmark for coverage, batching, webhooks, and warehouse delivery.
2. **ScrapeCreators** has the broadest documented developer-focused Facebook API and the clearest endpoint benchmark.
3. **Apify's maintained scraper** provides the strongest no-code workflow, scheduling, datasets, exports, and integrations.
4. **Data365** provides a useful asynchronous monitoring model based on jobs, polling, and callbacks.
5. **Meta APIs** provide the official validation baseline for connected assets and advertising data.
6. **Apify All-in-One** advertises broad coverage, but cookie dependence and third-party maintenance require proof tests.
7. **`kevinzg/facebook-scraper`** provides a rich historical field inventory, but its parser and dependencies have high drift risk.
8. **Oxylabs, Zyte, and Decodo** are infrastructure references rather than complete Facebook-specific products.
9. **`andriy-koz/facebook-scraper`** is an Apify enrichment pipeline rather than an independent Facebook scraper.

## Recommended product direction

Build the product around:

- Synchronous and asynchronous jobs.
- Stable normalized schemas.
- Durable checkpoints and idempotent retries.
- Raw-response storage and parser replay.
- Field-level provenance, null reasons, and confidence.
- Drift detection and versioned fixture tests.
- API access, schedules, signed webhooks, and warehouse delivery.
- Published completeness, reliability, latency, and cost benchmarks.

## Priority research targets

1. Bright Data Facebook Scraper API.
2. ScrapeCreators Facebook API.
3. Apify-maintained Facebook Pages Scraper.
4. Data365 Facebook API.
5. Meta Graph API and Ad Library API.
6. Apify All-in-One Facebook Scraper.
7. `kevinzg/facebook-scraper`.
8. Zyte, Oxylabs, and Decodo infrastructure.
9. `andriy-koz/facebook-scraper`.

## Initial product implications

- Match competitor breadth only after proving core-field completeness.
- Use official Meta sources as validation references where access permits.
- Adopt rich field inventories without copying fragile parser architecture.
- Use stable entity identifiers for checkpoints instead of line counts.
- Differentiate through replay, lineage, confidence scoring, and measured completeness.

## Evidence classification

- **Documented** — current primary documentation describes the behavior.
- **Code-verified** — inspected source code implements the behavior.
- **Runtime-tested** — a controlled execution reproduced the behavior.
- **Independently reproduced** — repeated testing confirmed the result across fixtures or runs.
- **Claim** — marketing or product copy lacks a reproducible receipt.
- **Unknown** — current primary-source evidence was not found.

The coverage tables report documentation evidence only. They do not indicate runtime reproduction.

## Documented surface coverage

| Surface | Bright Data | ScrapeCreators | Apify official | Apify All-in-One | Data365 |
|---|---|---|---|---|---|
| Page/profile metadata | Documented | Documented | Documented | Claim | Claim |
| Page posts | Documented | Partial endpoint coverage | Limited recent-post field | Claim | Claim |
| Single posts and reels | Documented | Documented | Unknown | Claim | Documented sample |
| Comments and replies | Documented | Documented | Unknown | Claim | Claim |
| Group posts | Documented | Documented | Unknown | Claim | Claim |
| Events | Documented | Documented | Unknown | Claim | Unknown |
| Marketplace | Documented | Documented | Unknown | Claim | Unknown |
| Ad Library | No dedicated contract found | Documented | Ad status only | Claim | Unknown |
| Reviews | Documented | Unknown | Rating summary | Claim | Unknown |
| Scheduling or monitoring | External workflow | Client-built | Documented platform feature | Platform feature | Claimed automatic updates |

### Coverage conclusion

- Bright Data provides the broadest documented enterprise coverage.
- ScrapeCreators exposes the most inspectable Facebook-specific schemas.
- Apify official provides a focused Page product rather than full Facebook coverage.
- All-in-One needs controlled verification because most assurances come from its third-party author.
- Data365 needs trial access to verify its Facebook-specific contracts.

## Field-level findings

| Field group | Bright Data | ScrapeCreators | Apify official | Data365 |
|---|---|---|---|---|
| Stable IDs and canonical URLs | Documented | Documented | Documented | Documented sample |
| Names, categories, and biographies | Documented | Documented | Documented | Claimed |
| Followers and likes | Documented | Documented | Documented | Claimed |
| Public business contacts | Endpoint-dependent | Documented | Documented | Undocumented |
| Business hours and services | Endpoint-dependent | Documented | Documented | Unknown |
| Post text, date, and author | Documented | Documented | Limited | Documented sample |
| Reactions, comments, and shares | Documented | Documented | Unspecified | Documented sample |
| Comment threads | Documented | Documented | Unknown | Claimed |
| Event details | Documented | Documented | Unknown | Unknown |
| Marketplace price and seller fields | Documented | Documented | Unknown | Unknown |
| Field provenance, confidence, and null reasons | Unknown | Unknown | Unknown | Unknown |

No reviewed competitor documents a complete field-level provenance, confidence, and null-reason system. This remains a strong differentiation opportunity.

## Operational comparison

| Capability | Bright Data | ScrapeCreators | Apify | Data365 |
|---|---|---|---|---|
| Job model | Synchronous and asynchronous | Synchronous calls | Actor runs | Asynchronous update tasks |
| Batch behavior | Large snapshots and discovery jobs | Caller-managed | Platform-managed runs | Queued tasks |
| Pagination | Dataset-specific | Cursor-based endpoints | Dataset offset and limit | Contract-dependent |
| Partial failures | Successful batch can contain failed URLs | Per-request failures | Earlier dataset items can survive failed runs | Undocumented |
| Retries | Caller retries failed URLs | Caller backoff | Restart and resurrection features | Undocumented |
| Webhooks | Result delivery | Not found | Run-event webhooks | Completion callbacks |
| Exports | JSON, NDJSON, CSV, cloud warehouses | JSON | JSON, CSV, XML, Excel, HTML, JSONL | JSON |
| Resume primitive | Snapshot identifier | Caller-stored cursor | Run state and storage | Task identifier |
| Freshness control | Live collection claim | `cache_max_age` | No selector found | Fresh-data claim |

### Exact Apify run states

`READY`, `RUNNING`, `SUCCEEDED`, `FAILED`, `TIMING-OUT`, `TIMED-OUT`, `ABORTING`, and `ABORTED`.

### Recovery conclusion

No reviewed product exposes a complete public contract for item-level checkpoints, replay, idempotent recovery, and field lineage.

## Normalized pricing examples

**Pricing snapshot:** 2026-07-29.

These calculations exclude taxes and unlisted charges. They are planning estimates, not tested invoices.

| Product | Billing basis | Minimum purchase or plan | 1,000 Pages | 10,000 Posts | 100 Pages daily for 30 days | Failure-billing evidence | Confidence |
|---|---|---:|---:|---:|---:|---|---|
| Bright Data | Successful record; dataset-specific | Free credits published; paid minimum varies | From **$1** | From **$10** | From **$3** | Individual batch failures are documented; billed-result treatment needs testing | Medium |
| ScrapeCreators Business | API credits; most inspected calls cost one credit | **$497 / 500,000 credits** | **$0.99 consumed value** | **$9.90 consumed value** | **$2.97 consumed value** | HTTP failure and cache-credit behavior needs invoice testing | Medium |
| Apify official Pages | Actor results plus possible platform usage | Apify plan or usage balance | From **$5.40** | Not applicable | From **$16.20** | Actor and compute billing need run receipts | Medium-low |
| Apify All-in-One | Mode-specific pay per result plus platform usage | Apify plan or usage balance | **$7.20** | **$18.00** | **$21.60** | Third-party rates need billed-run confirmation | Low |
| Data365 Basic | Credit pool; nine credits per profile and one per post | **€300 / 500,000 credits monthly** | **€5.40 consumed value** | **€6.00 consumed value** | **€16.20 consumed value** | Contract-specific | Medium-low |

### Pricing interpretation

- Consumed value is not the minimum invoice.
- A complete entity can require multiple calls or records.
- Provider, compute, storage, proxy, retry, and delivery costs can accumulate.
- Report three unit costs: requested record, successful record, and complete record.
- Replace estimates with invoice-backed measurements during P1 cost testing.

## Canonical data contract

Use a shared record envelope:

```json
{
  "schema_version": "1.0.0",
  "record_type": "page|post|ad|event|comment|group",
  "source": "meta_graph|meta_ad_library|html_adapter|managed_api",
  "source_record_id": "STRING",
  "canonical_id": "STRING",
  "canonical_url": "URL",
  "collected_at": "RFC3339",
  "source_updated_at": null,
  "adapter_version": "STRING",
  "raw_capture_id": "STRING",
  "field_provenance": {},
  "null_reasons": {},
  "confidence": {}
}
```

Do not encode unavailable, hidden, missing, and parser-failed states as the same `null`.

### Core Page contract

- Identity: Page ID, name, username, canonical URL.
- Classification: category, verification status, availability.
- Description: intro, biography, website, public contact fields.
- Location: address, latitude, longitude.
- Metrics: followers and likes as timestamped observations.
- Media: profile and cover images.
- Context: source permissions, ownership, and collection session class.

### Core Post contract

- Post, Page, and author identifiers.
- Published and updated timestamps.
- Text, permalink, type, attachments, and external links.
- Reaction, comment, share, and view observations.
- Pinned, live, shared, parent, and availability states.

Store changing counters as observations:

```json
{
  "value": 123,
  "observed_at": "RFC3339",
  "source": "SOURCE"
}
```

### Core Ad contract

- Archive, Page, and collation identifiers.
- Creative bodies, titles, descriptions, captions, and snapshot URL.
- Platforms, languages, countries, delivery dates, and active state.
- Spend, impression, reach, demographic, and regional ranges where available.
- Category and funding entity.

An absent spend or demographic value does not mean zero.

### Core Event, Comment, and Group rules

- Events must preserve timezone, host, location, cancellation, and online status.
- Comments must use a flat adjacency list with `parent_comment_id`.
- Groups must record privacy, membership state, session class, and visibility context.

## Official validation boundaries

| Source | Strong use | Boundary |
|---|---|---|
| Meta Graph API | Connected Pages, approved fields, stable IDs, paging | Permissions, ownership, App Review, tokens, and API versions |
| Meta Ad Library | Ad presence, archive IDs, creative snapshots | Geography, category, query behavior, and field availability |
| Meta Content Library | Approved research validation | Restricted access and controlled research environments |

Use these validation labels:

- `official_exact`
- `official_derived`
- `cross_source_match`
- `source_observed`
- `unverified_claim`

## Open-source architecture findings

### `kevinzg/facebook-scraper`

Inspected commit: [`567711fbab3e014504a1d4f33f882c2b29d71584`](https://github.com/kevinzg/facebook-scraper/tree/567711fbab3e014504a1d4f33f882c2b29d71584)

Architecture:

- Python library and command-line interface.
- Persistent `requests-html` session.
- Mobile HTML, selectors, embedded JSON, regex, and additional detail requests.
- Cookie files, browser cookies, direct login, proxies, and custom sessions.
- Specialized Page, Group, Photo, Search, and Hashtag iterators.
- Rich post, media, reaction, comment, reply, and profile field inventory.

Pagination:

1. Request a mobile page.
2. Retry HTTP 500 responses with increasing waits.
3. Switch response mode after repeated failures.
4. Parse HTML or a Facebook JSON action wrapper.
5. Find the next URL using cursor regexes.
6. Stop when no cursor remains.

Main weaknesses:

- No durable cursor checkpoint.
- No raw-response store.
- No idempotent output sink.
- Interactive login is unsuitable for unattended workers.
- Parser failures often become bare `None`.
- Default branch last changed in 2023.
- Old fixtures do not prove current compatibility.

### `andriy-koz/facebook-scraper`

Inspected commit: [`f47d73819d7e169d77001e474a29ddd044e4b082`](https://github.com/andriy-koz/facebook-scraper/tree/f47d73819d7e169d77001e474a29ddd044e4b082)

```text
CSV → JSONL → SearXNG discovery → Apify Actor → JSONL checkpoint → CSV
```

Useful patterns:

- Streaming JSONL.
- Separation of discovery from extraction.
- Append-only progress.
- Dockerized discovery service.

Weak patterns:

- First-result entity matching.
- Line-count resume semantics.
- Query-string API token.
- External Actor schema dependence.
- No automated tests, fixtures, CI, releases, or schema versioning.

## Patterns to adopt

- Separate session, transport, parser, normalization, and storage adapters.
- Use independent extractors for related field groups.
- Combine HTML and embedded-JSON strategies.
- Isolate cursor discovery behind an iterator interface.
- Store raw captures before normalization.
- Replay raw captures for parser regression tests.
- Stream normalized records through JSONL or durable queues.
- Persist cursors and source state before requesting the next page.
- Classify login, consent, block, deletion, and parser failures explicitly.
- Compare supported records against official APIs.

## Patterns to reject

- Regex-only cursor discovery.
- Interactive login inside collection workers.
- Silent omission after parsing errors.
- Bare null values.
- Line-count checkpoints.
- First-search-result entity selection.
- Secrets in query strings.
- Mutable engagement counters without observation history.
- Old fixtures presented as current compatibility evidence.
- Normalized output without raw evidence.

## Evidence conflicts

All sources were retrieved or checked on 2026-07-29.

| Conflict | Evidence | Working assumption |
|---|---|---|
| Apify displays $5.40 per 1,000 Pages while older copy states $10. | [Actor page](https://apify.com/apify/facebook-pages-scraper), [Apify pricing](https://apify.com/pricing) | Use the current Store badge. Confirm with one billed run. |
| Apify documentation describes different unnamed-dataset retention periods. | [Dataset documentation](https://docs.apify.com/storage/dataset), [storage overview](https://docs.apify.com/storage) | Name production datasets and configure explicit retention. |
| ScrapeCreators markets fewer endpoints than its documentation exposes. | [Product page](https://scrapecreators.com/facebook-api), [documentation index](https://docs.scrapecreators.com/) | Generate inventory from current OpenAPI documents. |
| ScrapeCreators says no rate limits but recommends fewer than 500 concurrent calls. | [ScrapeCreators documentation](https://docs.scrapecreators.com/) | Treat 500 as an operational recommendation, not a guaranteed limit. |
| ScrapeCreators says real-time while supporting cached responses. | [ScrapeCreators documentation](https://docs.scrapecreators.com/) | Record `cached` and `cached_at`. Disable cache during freshness tests. |
| Bright Data describes live collection, but synchronous requests can become asynchronous. | [Facebook API introduction](https://docs.brightdata.com/datasets/scrapers/facebook/introduction), [sync versus async](https://docs.brightdata.com/datasets/scrapers/concepts/sync-vs-async) | Separate source freshness from delivery latency. |
| Bright Data documents batch limits using both URL count and input size. | [Facebook async requests](https://docs.brightdata.com/datasets/scrapers/facebook/async-requests), [sync versus async](https://docs.brightdata.com/datasets/scrapers/concepts/sync-vs-async) | Enforce the stricter tested limit. |
| Data365 publishes inconsistent uptime percentages. | [Product overview](https://data365.co/), [pricing](https://data365.co/pricing) | Record no contractual SLA before reviewing an agreement. |
| Data365 describes broad coverage while examples exclude login-required content. | [Facebook product page](https://data365.co/facebook), [API introduction](https://data365.co/intro) | Test logged-out public fixtures first. |
| Apify All-in-One combines HTTP-only and human-like claims without implementation receipts. | [All-in-One Actor](https://apify.com/get-leads/all-in-one-facebook-scraper) | Classify architecture and reliability as claims until controlled runs reproduce them. |

## Proof-test plan

### Ground-truth protocol

1. Capture the visible source, official API response where available, request metadata, headers, and collection time.
2. Assign two reviewers to label identifiers, fields, counters, timestamps, and availability states independently.
3. Resolve disagreements through a third review.
4. Freeze the adjudicated record, raw body hash, screenshot hash, and expected pagination set.
5. Preserve each source observation separately when counters change during collection.
6. Mark hidden, unavailable, deleted, gated, and parser-failed fields with different null reasons.

Ground truth is valid only for its recorded timestamp, session class, geography, and visibility context.

### P0: Contracts and coverage

Build at least 40 controlled fixtures across Pages, profiles, posts, reels, events, Marketplace, groups, comments, and ads.

Acceptance:

- Required identifier precision: **100%**.
- Required-field extraction: **at least 99%**.
- Optional-field extraction when visible: **at least 97%**.
- Duplicate canonical records: **at most 0.1%**.
- Schema validation: **100%**.

### P0: Pagination and recovery

Test zero-page, one-page, multi-page, deleted, gated, redirected, and interrupted collections.

Acceptance:

- Pagination completeness: **at least 99.5%**.
- Resume produces the same final identifier set.
- Mid-page sink failure causes no loss.
- Duplicate rate after recovery: **at most 0.1%**.
- Every input reaches success, explicit failure, or pending status.

### P0: Error classification

Create fixtures for login shells, consent pages, checkpoints, temporary blocks, HTTP 404, 429, and 500 responses.

Acceptance:

- Error classification: **100%**.
- Unsupported layouts reported as success: **0%**.
- Failed units can be retried independently.

### P1: Freshness and cache

Test controlled changes with frequent polling and explicit cache settings.

Acceptance:

- Fresh-mode p95 detection lag: **15 minutes or less**.
- Cached responses always include cache timestamps.
- Observation, collection, and delivery times remain separate.

### P1: Drift and replay

Refresh schemas and fixtures weekly.

Acceptance:

- Raw replay produces identical normalized hashes.
- Required-field decline above two percentage points triggers an alert.
- Type changes block release.
- Breaking changes require a schema-version increment.

### P1: Cost

Measure 1,000 Page requests and 10,000 Post requests.

Acceptance:

- Estimated and billed costs differ by no more than **10%**.
- Report requested-record, successful-record, and complete-record costs separately.
- Verify failed-call, cache, compute, proxy, and storage charges.

### P2: Monitoring endurance

Monitor 100 diverse Pages daily for 30 days.

Acceptance:

- Scheduled completion: **at least 99%**.
- Daily Page coverage: **at least 99.5%**.
- False change alerts: **at most 1%**.
- No unresolved gap persists longer than 24 hours.

## Recommended validation order

1. Bright Data.
2. ScrapeCreators.
3. Apify official.
4. Meta Ad Library and Graph API comparisons.
5. Data365 trial.
6. Apify All-in-One.
7. Open-source replay and parser experiments.

## Build, buy, and stop gates

| Decision | Trigger | Required evidence | Owner | Review point |
|---|---|---|---|---|
| **Build core platform** | Canonical contracts and replay provide cross-provider value | P0 schema, replay, pagination, and recovery tests pass | Product architecture | End of Phase 0 |
| **Buy collection adapter** | Provider meets field and reliability targets below internal complete-record cost | Invoice-backed cost and 30-day reliability receipt | Data operations | Per adapter |
| **Use hybrid adapter** | Managed collection accelerates launch but lacks lineage or checkpoints | Raw capture access, idempotent wrapper, and exit plan | Platform engineering | MVP gate |
| **Replace provider** | Required-field accuracy falls below 99% or gaps persist beyond 24 hours | Three confirmed failures or one schema-breaking incident without notice | Data operations | Incident review |
| **Build native adapter** | Provider costs exceed the approved ceiling or blocks required evidence controls | Cost model, fixture corpus, maintenance budget, and parser prototype | Engineering leadership | Phase 2 |
| **Stop a surface** | Pagination completeness remains below 99.5% after two adapter strategies | Labelled truth set and failure analysis | Product leadership | Surface gate |
| **Expand a surface** | Existing adapter passes three consecutive fixture refreshes | Release-gate report and rollback parser | Product and quality | Release review |

### Required ownership fields

Every adapter work item must specify:

- Product owner.
- Engineering owner.
- Data-quality owner.
- Monthly complete-record cost ceiling.
- Supported surfaces and fields.
- Recovery-point objective.
- Retention and deletion requirements.
- Review date and rollback path.

## Governance comparison

| Control | Bright Data | ScrapeCreators | Apify | Data365 | Product requirement |
|---|---|---|---|---|---|
| Configurable retention | Needs contract review | Undocumented | Platform storage controls documented | Undocumented | Per-tenant policy |
| Deletion workflow | Needs contract review | Undocumented | Dataset deletion available | Undocumented | Documented deletion receipt |
| Data residency | Plan-dependent | Undocumented | Platform-region review needed | Contract review needed | Recorded tenant region |
| Tenant isolation | Vendor responsibility | Vendor responsibility | Platform responsibility | Vendor responsibility | Application and storage isolation |
| Audit trail | Delivery/job evidence varies | Caller-managed | Run and dataset history | Task history | Immutable job, access, export, and deletion events |
| Raw-response access | Endpoint-dependent | JSON response | Dataset items; raw source varies | JSON result | Required for every supported adapter |

Unknown governance fields are procurement blockers for production use, not evidence of missing provider capability.

## Final build priorities

1. Define canonical Page, Post, Ad, Event, Comment, and Group contracts.
2. Build raw-capture storage and deterministic replay.
3. Implement durable source cursors and idempotent sinks.
4. Add explicit failure classes and null reasons.
5. Build official-source validation adapters.
6. Publish completeness, recovery, freshness, and cost results.
7. Add schedules, signed webhooks, API access, and warehouse delivery.
8. Expand surface coverage only after each adapter passes its release gate.

## Evidence ledger

| ID | Finding | Evidence class | Primary source | Date | Confidence | Next verification |
|---|---|---|---|---|---|---|
| E01 | Bright Data documents broad Facebook-specific coverage. | Documented | [Facebook API introduction](https://docs.brightdata.com/datasets/scrapers/facebook/introduction) | 2026-07-29 | High | Run the P0 coverage corpus. |
| E02 | Bright Data supports synchronous and asynchronous collection. | Documented | [Sync versus async](https://docs.brightdata.com/datasets/scrapers/concepts/sync-vs-async) | 2026-07-29 | High | Measure conversion, latency, and partial failures. |
| E03 | ScrapeCreators exposes profiles, posts, comments, Groups, Events, Marketplace, and Ad Library routes. | Documented | [Documentation index](https://docs.scrapecreators.com/) | 2026-07-29 | High | Generate and diff the OpenAPI inventory. |
| E04 | ScrapeCreators uses cursor pagination on several endpoints. | Documented | [Facebook comments](https://docs.scrapecreators.com/v1/facebook/post/comments/) | 2026-07-29 | High | Test replay and completeness. |
| E05 | Apify's maintained Actor focuses on Page and profile metadata. | Documented | [Official Actor](https://apify.com/apify/facebook-pages-scraper) | 2026-07-29 | High | Run sparse, business, and personal fixtures. |
| E06 | Apify All-in-One advertises broad multi-mode coverage. | Claim | [All-in-One Actor](https://apify.com/get-leads/all-in-one-facebook-scraper) | 2026-07-29 | Low | Test every mode with receipts. |
| E07 | Data365 uses asynchronous update tasks. | Documented | [API introduction](https://data365.co/intro) | 2026-07-29 | Medium | Confirm exact states and retries during a trial. |
| E08 | Meta Graph provides official versioned objects and fields for permitted assets. | Documented | [Graph API overview](https://developers.facebook.com/docs/graph-api/overview/) | 2026-07-29 | High | Compare owned test Pages. |
| E09 | Meta Ad Library provides the official advertising baseline. | Documented | [Ads archive reference](https://developers.facebook.com/docs/graph-api/reference/ads_archive/) | 2026-07-29 | High | Reconcile API and visible UI identifiers. |
| E10 | `kevinzg/facebook-scraper` implements a rich mobile-HTML parser without durable checkpoints. | Code-verified | [`567711f`](https://github.com/kevinzg/facebook-scraper/tree/567711fbab3e014504a1d4f33f882c2b29d71584) | 2026-07-29 | High | Replay current redacted fixtures. |
| E11 | `andriy-koz/facebook-scraper` delegates extraction to Apify and resumes by line count. | Code-verified | [`f47d738`](https://github.com/andriy-koz/facebook-scraper/tree/f47d73819d7e169d77001e474a29ddd044e4b082) | 2026-07-29 | High | Add a mocked Actor contract test. |
| E12 | No reviewed competitor documents complete field provenance, confidence, and null reasons. | Documented search result | Reviewed primary documentation | 2026-07-29 | Medium | Confirm through trials and sales documentation. |

## Primary references

- [Bright Data Facebook Scraper API](https://docs.brightdata.com/datasets/scrapers/facebook/introduction)
- [ScrapeCreators API documentation](https://docs.scrapecreators.com/)
- [Apify Facebook Pages Scraper](https://apify.com/apify/facebook-pages-scraper)
- [Data365 API introduction](https://data365.co/intro)
- [Meta Graph API overview](https://developers.facebook.com/docs/graph-api/overview/)
- [Meta Ad Library API](https://developers.facebook.com/docs/graph-api/reference/ads_archive/)
