# Facebook product discovery answers

**Recorded:** 2026-07-29  
**Purpose:** Capture the operator's selected product requirements without replacing unanswered decisions.

## Product objective

| Question | Answer |
|---|---|
| Most important outcome | Business intelligence |
| Main workflow | Competitor monitoring |
| First paying customer | Free |
| First operator | The owner personally |
| Most important success metric | Reliability |

### Interpretation note

The answer **“Free”** was given to the customer question. A later answer selected **free self-hosted** as the access model.

## Product and access model

| Question | Answer |
|---|---|
| Launch access model | Free self-hosted |
| Paid collection dependencies | No paid dependencies |
| Primary interface | Command line |
| Command-line style | Single guided command |
| First deployment target | Native Windows |
| Scheduling | Manual command |

## Facebook scope

| Question | Answer |
|---|---|
| MVP surfaces | Pages, Groups, Events, and Posts |
| Group coverage | Public and user-accessible Groups |
| Signed-in Group session method | Cookie import |
| Historical collection depth | Last 30 days |
| Engagement depth | Not answered |
| Personal profiles | Not selected for the MVP |
| Ads | Not selected for the MVP |
| Marketplace | Not selected for the MVP |

## Discovery and monitoring

| Question | Answer |
|---|---|
| Target selection | Automatic discovery |
| Discovery inputs | Keywords and locations |
| Discovery engine | Not answered |
| Default monitoring frequency | Weekly |
| Weekly target capacity | Up to 100 targets |
| Run notification | Local report only |

## Data and exports

| Question | Answer |
|---|---|
| Primary delivery | Downloadable datasets |
| Export formats | CSV and JSON |
| Analysis before export | Raw structured data |
| Repeated collections | Append snapshots |
| Media handling | Store metadata and source URLs |
| Export layout | Not answered |
| Local storage model | Not answered |
| Default retention | 90 days |

## Session and secret handling

| Question | Answer |
|---|---|
| Initial session choice | Unsure |
| Final session choice | Cookie import |
| Cookie storage | Encrypted local file |
| Encryption-key method | Not answered |

## User experience

The planned workflow currently implies:

1. Start one guided command.
2. Enter keywords and locations.
3. Import a Facebook cookie when user-accessible Group collection requires it.
4. Discover relevant Pages, Groups, Events, and Posts.
5. Collect the previous 30 days.
6. Store media metadata and URLs without downloading media.
7. Append a new weekly snapshot.
8. Generate local CSV, JSON, and run-report files.

## Confirmed priorities

1. Reliability is more important than completeness or speed.
2. The product must run locally on Windows.
3. Core collection must avoid paid dependencies.
4. The first release must be self-hosted and free.
5. The first release must prioritize downloadable structured datasets.
6. The product must support public and user-accessible Groups.
7. Weekly monitoring must support up to 100 targets.

## Decisions still open

1. Choose SQLite with raw files, JSONL only, or PostgreSQL.
2. Choose pluggable web search, Facebook search, or required SearXNG.
3. Choose post counters only, full comments, or content only.
4. Choose worldwide, UK-first, or single-country discovery.
5. Choose separate entity files, one flattened file, or one nested bundle.
6. Choose Windows user encryption, passphrase encryption, or an environment key.
7. Define the exact first-user audience beyond the owner.
8. Define acceptable reliability, completeness, duplicate, and freshness thresholds.

