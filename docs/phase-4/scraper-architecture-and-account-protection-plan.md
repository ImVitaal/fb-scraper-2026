# Simple scraper and account-protection plan

**Date:** 2026-07-30  
**Status:** Use this plan before the controlled APP run

## Goal

Collect visible Group Posts and top-level Comments without dense or repeated browser activity.

No published setting guarantees zero detection. Use low volume and stop at the first warning.

## How other scrapers work

| Scraper type | Method | Useful pattern | Main limit |
|---|---|---|---|
| Open-source Python scraper | Requests pages and parses HTML | Browser cookies, page limits, resume files | Private Groups and pagination can fail |
| Selenium scrapers | Open a browser, scroll, and expand content | Real rendering and simple CSV export | Older projects and slow comment collection |
| Hosted Group actors | Accept Group URLs and return datasets | Date limits, post caps, checkpoints | Many support public Groups only |
| Private-capable hosted actors | Import member cookies and capture rendered data | Incremental runs and partial-result storage | Cookie and account exposure remains |
| Managed scraper APIs | Send URLs and receive structured records | Scaling and managed parsing | Paid and unsuitable for the self-hosted core |

Common pattern:

```text
Saved session
    -> Group URL
    -> Scroll or cursor
    -> Save each page
    -> Parse Posts and Comments
    -> Save checkpoint
    -> Resume later
```

## What this project already does well

- Uses one browser worker.
- Uses one encrypted local session.
- Saves raw captures before parsing.
- Saves checkpoints before the next action.
- Stops on login, challenge, restriction, and layout failure.
- Supports resume and offline replay.

## What needs improvement

Current browser waits are only 50–100 milliseconds.

Add only these controls:

1. Wait several seconds between browser actions.
2. Stop immediately on any account warning.
3. Scan one Group at a time.
4. Reuse completed Post identifiers.
5. Pause before starting the next Group.

## Simple starting settings

| Setting | Value |
|---|---:|
| Workers | 1 |
| Groups at once | 1 |
| Delay after navigation | 10–20 seconds |
| Delay after scroll | 6–12 seconds |
| Delay after expansion | 3–7 seconds |
| Transient retries | 2 |
| Retry delays | 30 seconds, then 120 seconds |
| Delay between Groups | 15 minutes |
| First Group Post limit | 30 recent Posts |
| History window | 30 days |

These values are starting limits, not platform thresholds.

## Stop immediately when

- Login appears.
- A checkpoint or CAPTCHA appears.
- The account is locked or restricted.
- HTTP 401, 403, or 429 appears.
- Navigation fails repeatedly.
- The page layout is unsupported.

Save the checkpoint and close the browser after any stop condition.

## Session setup

1. Close Chrome.
2. Copy the `Default` profile.
3. Import the copied session.
4. Keep one browser and network connection.
5. Run a session-health check.
6. Keep all session material outside Git.

Do not rotate accounts, cookies, proxies, fingerprints, or browser identities.

## Group choice

Use live discovery with:

```text
KEYWORD=local community
LOCATION=London
```

Choose ten accessible Groups already visible through the saved account.

Use the lowest-volume valid Group first.

Exclude Groups showing warnings, join requests, access failures, or unsupported layouts.

Keep actual Group URLs in private operator configuration.

## Implementation order

1. Add configurable action delays.
2. Add immediate warning stops.
3. Add known-Post skipping.
4. Record delays and stop reasons in the receipt.
5. Run one Group.
6. Review the account and receipt.
7. Run the remaining nine Groups sequentially.

## Required checks

- Every browser action uses the configured delay.
- Warning pages receive zero retries.
- Completed Posts are not opened again.
- Raw capture and checkpoint precede the next action.
- Receipts contain no cookies or tokens.
- Only one Group runs at once.

## Sources

- Platform automated collection terms:  
  https://www.facebook.com/legal/automated_data_collection_terms
- Platform scraping and rate-limit description:  
  https://www.facebook.com/help/463983701520800
- Open-source Python scraper:  
  https://github.com/kevinzg/facebook-scraper
- Selenium Group scraper:  
  https://github.com/apurvmishra99/facebook-scraper-selenium
- Hosted Group scraper:  
  https://apify.com/apify/facebook-groups-scraper
- Managed scraper API:  
  https://docs.brightdata.com/datasets/scrapers/facebook/introduction
