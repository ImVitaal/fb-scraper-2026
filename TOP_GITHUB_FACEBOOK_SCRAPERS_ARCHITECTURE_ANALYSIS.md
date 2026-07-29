# Top GitHub Facebook scrapers: architecture analysis

**Research date:** 2026-07-29  
**Purpose:** Understand implementation patterns that can inform FB Scraper 2026.  
**Decision:** Start fresh and selectively reuse compatible ideas.

## Selection method

The repositories were selected from GitHub's repository search for **Facebook scraper** in repository names or descriptions, sorted by stars.

Stars measure attention, not current reliability.

The five highest results at the research date were:

| Rank | Repository | Stars | Inspected commit | Default-branch commit date |
|---:|---|---:|---|---|
| 1 | [`kevinzg/facebook-scraper`](https://github.com/kevinzg/facebook-scraper) | 3,241 | [`567711f`](https://github.com/kevinzg/facebook-scraper/tree/567711fbab3e014504a1d4f33f882c2b29d71584) | 2023-10-30 |
| 2 | [`harismuneer/Ultimate-Social-Scrapers`](https://github.com/harismuneer/Ultimate-Social-Scrapers) | 3,143 | [`21976a3`](https://github.com/harismuneer/Ultimate-Social-Scrapers/tree/21976a3eb127699cf07e107f767711ae42b656c3) | 2025-06-07 |
| 3 | [`minimaxir/facebook-page-post-scraper`](https://github.com/minimaxir/facebook-page-post-scraper) | 2,132 | [`275711f`](https://github.com/minimaxir/facebook-page-post-scraper/tree/275711ffaec6a959a1802d9ac3df710e33920a77) | 2017-12-25 |
| 4 | [`passivebot/facebook-marketplace-scraper`](https://github.com/passivebot/facebook-marketplace-scraper) | 392 | [`bf3d371`](https://github.com/passivebot/facebook-marketplace-scraper/tree/bf3d37174e6e2cddaa35b69526bbf7f67a09a911) | 2024-01-16 |
| 5 | [`brutalsavage/facebook-post-scraper`](https://github.com/brutalsavage/facebook-post-scraper) | 364 | [`acf0bfd`](https://github.com/brutalsavage/facebook-post-scraper/tree/acf0bfdf7463c22811b39c9e0fd5654b7f8bf8b7) | 2020-09-09 |

## Comparative overview

| Repository | Transport | Parsing | Pagination | Session | Output | Tests | License |
|---|---|---|---|---|---|---|---|
| `kevinzg` | `requests-html` mobile requests | Selectors, embedded JSON and regex | Mobile next-page URLs and cursor regexes | Anonymous, cookies or login | Python dictionaries, JSON and CSV | 10 tests and 8 recorded fixtures | MIT |
| `Ultimate-Social-Scrapers` | None in current repository | None | None | None | README only | None | None detected |
| `minimaxir` | Historical Graph API v2.9 | API JSON mapping | Graph cursors, `after`, `until` and paging tokens | App ID and secret | CSV | None | MIT stated in README |
| `passivebot` | Playwright | BeautifulSoup and CSS classes | Infinite page scroll | Browser context | FastAPI JSON and Streamlit display | None | None detected |
| `brutalsavage` | Selenium Chrome | BeautifulSoup and old DOM classes | Scroll and click expansion | Email and password file | Dictionary, JSON and CSV | None | GPL-3.0 |

## 1. `kevinzg/facebook-scraper`

### Architecture

```text
CLI or Python API
    ↓
FacebookScraper session
    ↓
Page iterator
    ↓
Mobile Facebook HTML or JSON wrapper
    ↓
PostExtractor
    ↓
Optional detail requests
    ↓
Python record
    ↓
JSON or CSV
```

### Public interface

The package exposes focused functions for:

- Page and profile information.
- Group information.
- Posts by Page, Group, search or direct URL.
- Photos.
- Reactions and reactors.
- Comments and replies.
- Friends and shop records.
- Group and post search.

This creates a useful high-level interface while hiding transport details.

### Session design

The implementation uses a persistent `requests-html.HTMLSession`.

It supports:

- Anonymous requests.
- Caller-supplied sessions.
- Cookie files.
- Cookie dictionaries and cookie jars.
- Browser-cookie import.
- Direct login.
- Proxy configuration.
- Custom user agents.
- A `noscript` response mode.

The response layer classifies several source states:

- Not found.
- Temporarily blocked.
- Account disabled.
- Invalid cookies.
- Login required.
- Login failure.
- Unexpected response.

### Pagination design

The generic page iterator:

1. Requests a starting mobile URL.
2. Retries HTTP 500 responses.
3. Increases waits between repeated failures.
4. Switches response mode after several failures.
5. Parses HTML or a `for (;;);` JSON action wrapper.
6. Finds a next-page URL using response-specific patterns.
7. Repeats until no cursor remains.

Specialized iterators handle Page, Group, Photo, Search and Hashtag routes.

### Parsing design

`PostExtractor` acts as a field-oriented parser.

Separate methods extract:

- Post identifier.
- Author and Page information.
- Text.
- Timestamp.
- Links.
- Images and video.
- Likes, comments and shares.
- Reaction breakdowns.
- Reactors.
- Comments and replies.
- Shared-post information.
- Availability.
- Fact-check fields.

Some fields require additional requests after the initial post response.

### Output model

The output is a large, loosely typed dictionary.

Useful field families include:

- Identity.
- Text and publication time.
- Canonical links.
- Media variants.
- Engagement counters.
- Reaction breakdowns.
- Nested comments and replies.
- Shared-post relationships.
- Collection time.

### Testing model

The repository includes:

- Unit tests for dates and durations.
- Post and Group smoke tests.
- Recorded VCR response fixtures.
- Field-presence assertions.

The fixtures demonstrate historical parser behavior. They do not prove current source compatibility.

### Ideas worth adopting

1. **Small public functions** for each user workflow.
2. **Transport hidden behind a session object.**
3. **Separate iterator classes** for different surface types.
4. **One extractor method per field family.**
5. **Explicit response-state exceptions.**
6. **Optional detail requests** controlled by configuration.
7. **Recorded source fixtures** for offline parser tests.
8. **A broad canonical field inventory.**

### Ideas to replace

1. Replace loose dictionaries with versioned schemas.
2. Replace bare `None` with structured null reasons.
3. Replace regex-dependent cursor handling with adapter-specific cursor contracts.
4. Persist cursors before requesting the next page.
5. Store raw captures before parsing.
6. Separate interactive authentication from unattended collection workers.
7. Replace process-only iteration with durable jobs.
8. Replace nested-only comments with a flat adjacency model.
9. Use current Python and maintained dependencies.

### Recommended use

Use this repository as:

- A field-contract reference.
- A parser decomposition reference.
- A historical fixture source.
- An optional comparison adapter.

Do not fork it as the main product.

## 2. `harismuneer/Ultimate-Social-Scrapers`

### Current state

The inspected default branch contains one file: `README.md`.

The README states that Cyfy Labs is no longer active.

There is no current Facebook scraper implementation to inspect.

### What the repository demonstrates

Its star count reflects historical interest, branding and earlier product visibility. It does not represent reusable current source code.

### Ideas worth adopting

- Clear use-case positioning.
- Cross-platform social-data vocabulary.
- A focus on business outcomes instead of transport details.

### Ideas to avoid

- Treating stars as an engineering-quality signal.
- Depending on externally hosted tools without source or maintenance receipts.
- Marketing broad coverage without testable schemas and benchmark evidence.

### Recommended use

Use it only as a positioning reference.

## 3. `minimaxir/facebook-page-post-scraper`

### Architecture

```text
Configuration constants
    ↓
Graph API v2.9 request
    ↓
Retry-until-success wrapper
    ↓
JSON response
    ↓
Record normalization
    ↓
Cursor extraction
    ↓
CSV writer
```

Separate scripts collect:

- Page posts.
- Open Group posts.
- Comments and replies for previously collected posts.

### Authentication

The scripts construct an app access token from:

```text
APP_ID | APP_SECRET
```

The token is included in Graph API request URLs.

### Pagination

Page posts use Graph API cursor fields:

- `paging.cursors.after`

Group scripts also parse:

- `until`
- `__paging_token`

Comments and replies use independent cursor loops.

### Data flow

The post script first creates a status CSV.

The comment script then reads post identifiers from that CSV and writes a related comments CSV.

Relationships are retained through:

- Status identifier.
- Comment identifier.
- Parent-comment identifier.

### Useful architectural idea

This is a simple staged pipeline:

```text
Posts dataset
    ↓
Post identifiers
    ↓
Comment collection
    ↓
Related comments dataset
```

It avoids forcing every expansion into one large in-memory object.

### Known limitation

The README warns that the source API returned only approximately 5–10% of expected posts during its final maintenance period.

The repository is archived and its API version is obsolete.

### Ideas worth adopting

1. Separate primary records from expensive child expansions.
2. Preserve stable foreign-key relationships.
3. Use bounded date windows.
4. Treat Page, Group and Comment collection as separate jobs.
5. Export relational tables that analysts can join.

### Ideas to replace

1. Do not store credentials in source constants or URLs.
2. Do not retry indefinitely.
3. Do not write directly to CSV during collection.
4. Do not bind schemas to one historical API version.
5. Do not treat a completed request as proof of completeness.

### Recommended use

Reuse the staged relational-export concept, not the implementation.

## 4. `passivebot/facebook-marketplace-scraper`

### Architecture

```text
Streamlit form
    ↓
Local FastAPI endpoint
    ↓
Playwright Chromium
    ↓
Marketplace navigation and scrolling
    ↓
Rendered HTML
    ↓
BeautifulSoup selectors
    ↓
JSON response
    ↓
Streamlit results
```

### Browser flow

The FastAPI route:

1. Opens a Playwright browser.
2. Creates a page.
3. Navigates to Facebook Marketplace.
4. Builds a location and search URL.
5. Scrolls the result page.
6. reads the resulting HTML.
7. Parses listings with BeautifulSoup.
8. Returns structured JSON.

### Parsing model

The parser relies on long generated Facebook CSS-class combinations.

It extracts Marketplace fields such as:

- Listing name.
- Price.
- Location.
- Image.
- Listing URL.

### Application split

The repository separates:

- Browser and parsing logic in a FastAPI service.
- Operator interaction in a Streamlit client.

This is a useful separation even though both components run locally.

### Ideas worth adopting

1. Keep browser work behind a local service or adapter interface.
2. Return structured responses rather than exposing browser objects.
3. Separate the operator interface from collection logic.
4. Use an explicit browser lifecycle.
5. Make location and query first-class inputs.

### Ideas to replace

1. Do not use generated CSS-class strings as primary selectors.
2. Do not combine navigation, parsing and API response construction in one function.
3. Do not depend on an untested infinite-scroll loop.
4. Do not start a fresh browser for every small operation unless isolation requires it.
5. Do not include unrelated IP-check requests in the product path.
6. Add schemas, checkpoints, fixtures and health states.

### Recommended use

Reuse only the local adapter boundary and location-query input pattern.

The repository is Marketplace-specific and outside the current MVP.

## 5. `brutalsavage/facebook-post-scraper`

### Architecture

```text
CLI arguments
    ↓
Selenium Chrome
    ↓
Username and password login
    ↓
Scroll Page
    ↓
Click comment-expansion controls
    ↓
Capture full rendered HTML
    ↓
BeautifulSoup parser
    ↓
Dictionary
    ↓
JSON, CSV or terminal
```

### Browser behavior

The scraper:

- Starts Chrome using a local ChromeDriver executable.
- Reads credentials from `facebook_credentials.txt`.
- Logs in through visible form identifiers.
- Calculates an approximate number of scrolls.
- Expands comments through XPath and CSS classes.
- Captures the final HTML only after interaction finishes.

### Parsing model

Dedicated functions parse:

- Post text.
- Post link.
- Post identifier.
- Image.
- Shares.
- Comments and replies.
- Top reactions.

The functions rely on historic DOM classes and `data-testid` attributes.

### Output

The main extraction function returns a list of dictionaries.

The CLI can:

- Print results.
- Write JSON.
- Write CSV.

### Ideas worth adopting

1. Separate small extraction functions by field.
2. Allow users to control expansion depth.
3. Capture the rendered state after interaction.
4. Provide both library and CLI entry points.
5. Keep comments optional because they greatly increase work.

### Ideas to replace

1. Do not store account passwords in repository files.
2. Do not manage ChromeDriver manually.
3. Do not depend on obsolete Selenium APIs.
4. Do not use scroll-count estimates as checkpoints.
5. Do not capture only the final combined page state.
6. Do not parse generated classes without structural alternatives.
7. Do not silently mix collection, expansion and parsing failures.

### License consideration

This repository uses GPL-3.0.

Copying implementation code can impose redistribution obligations. Use its concepts as references unless the project deliberately adopts compatible licensing.

### Recommended use

Use only as a historical browser-interaction reference.

## Cross-repository patterns

### Pattern A: Layered field extractors

Both `kevinzg` and `brutalsavage` use separate functions for individual field families.

Adopt this pattern:

```text
Raw capture
    ↓
Identity extractor
Content extractor
Media extractor
Engagement extractor
Relationship extractor
Availability extractor
```

Each extractor should return:

```json
{
  "value": "VALUE",
  "source_path": "PATH_OR_SELECTOR",
  "status": "observed|missing|invalid|unsupported",
  "confidence": 1.0
}
```

### Pattern B: Surface-specific iterators

Pages, Groups, Events, Posts and search results have different pagination behavior.

Use one interface with specialized implementations:

```python
class SurfaceIterator:
    def first_request(self, target): ...
    def parse_page(self, capture): ...
    def next_cursor(self, capture): ...
    def checkpoint(self): ...
```

Do not build one universal cursor parser.

### Pattern C: Optional expansions

Comments, reactions, full media and extra details increase cost and failure probability.

Represent them as explicit expansion jobs:

```text
Collect post
    ├── expand comments
    ├── expand reactions
    ├── expand media
    └── expand shared post
```

This follows useful ideas from `kevinzg` and `minimaxir`.

### Pattern D: Relational exports

Use separate related tables instead of one deeply nested CSV:

```text
pages.csv
groups.csv
events.csv
posts.csv
comments.csv
media.csv
observations.csv
failures.csv
```

Every child table must retain its parent identifier.

### Pattern E: Browser adapter boundary

Follow the useful separation demonstrated by the Marketplace application:

```text
Guided CLI
    ↓
Collection job
    ↓
Browser adapter
    ↓
Capture receipt
```

The CLI must not directly manipulate browser selectors.

### Pattern F: Response-state classification

Expand `kevinzg`'s exception taxonomy into durable collection states:

```text
observed
unchanged
partial
unavailable
access_limited
membership_required
session_expired
temporarily_blocked
rate_limited
parser_drift
network_failed
```

Persist these states with every target attempt.

## Recommended FB Scraper 2026 architecture

```text
Guided CLI
    ↓
Discovery campaign
    ↓
Target qualification
    ↓
Durable job planner
    ↓
┌──────────────────────────────┐
│ Public-web adapter           │
│ Cookie-session adapter       │
│ Replay adapter               │
└──────────────────────────────┘
    ↓
Immutable raw capture
    ↓
Surface-specific parser
    ↓
Versioned canonical contract
    ↓
SQLite observations and checkpoints
    ↓
Discovery saturation and changes
    ↓
CSV, JSON and manifest exports
```

## Proposed adapter contract

```python
class CollectionAdapter:
    def discover(
        self,
        query: str,
        location: str | None,
        cursor: str | None,
    ) -> CaptureResult:
        ...

    def capture(
        self,
        target: Target,
        cursor: str | None,
    ) -> CaptureResult:
        ...

    def classify(
        self,
        capture: RawCapture,
    ) -> CollectionHealth:
        ...
```

```python
class SurfaceParser:
    surface: str
    version: str

    def parse(
        self,
        capture: RawCapture,
    ) -> list[CanonicalRecord]:
        ...

    def next_cursor(
        self,
        capture: RawCapture,
    ) -> str | None:
        ...
```

## Reuse matrix

| Idea | Source inspiration | Action |
|---|---|---|
| Field inventory | `kevinzg` | Translate into versioned contracts |
| Parser decomposition | `kevinzg`, `brutalsavage` | Implement new typed extractors |
| Surface iterators | `kevinzg` | Implement with durable cursor checkpoints |
| Recorded fixtures | `kevinzg` | Create current redacted fixtures and mutations |
| Relational expansions | `minimaxir` | Use separate child jobs and tables |
| Date-window inputs | `minimaxir` | Standardize on UTC ranges |
| Local browser boundary | `passivebot` | Build a replaceable adapter |
| Query and location inputs | `passivebot` | Integrate into discovery campaigns |
| Optional comment expansion | `kevinzg`, `brutalsavage` | Keep outside the default MVP path |
| Multiple export formats | All implemented scrapers | Export CSV, JSON and manifest |

## Do-not-copy list

- Historic Facebook API endpoints.
- Generated CSS-class strings.
- Regex-only cursor extraction.
- Plaintext credentials.
- Secrets inside URLs.
- Manual ChromeDriver management.
- Infinite retries.
- Scroll counts as progress.
- Final-page-only captures.
- Nested-only comments.
- Direct CSV writes during collection.
- Bare null values.
- Process-memory-only cursors.
- Unlicensed source code.
- GPL implementation code without an explicit licensing decision.

## Final decision

Start FB Scraper 2026 from a clean repository.

Use the inspected projects as a design library:

1. Take `kevinzg`'s field breadth, iterator separation and extractor decomposition.
2. Take `minimaxir`'s staged relational collection pattern.
3. Take `passivebot`'s local browser-service boundary.
4. Take `brutalsavage`'s optional rendered-page expansion concept.
5. Reject their outdated transport, secret handling, retry and checkpoint designs.

This approach preserves the strongest ideas without inheriting obsolete dependencies or architectural constraints.

