# Phase 3 fixture comparison completion report

**Date:** 2026-07-29
**Release class:** Reproducible synthetic comparison command

## Result

The Phase 3 fixture gate passes.

- Both inputs use the same 30-identifier workload.
- Each measured value traces to an exact input SHA-256.
- The output Markdown traces to an exact SHA-256 in the receipt.
- Missing fields appear as unsupported.
- Measurements and conclusions use separate report sections.

## Input and output hashes

- Local JSON input SHA-256:
  `4ea49865a5a4717a5a49ff6a478275688a2a92b5016ab2defd101784775d24e5`
- Comparison CSV input SHA-256:
  `0b49762c96ef06a4a944ab22cc783c64e47745fd6af042015803f7a6154a5b77`
- Markdown report SHA-256:
  `1a1d32efed03328174d613728c8ab23e34e1881c93aa9232949e3f930b1f54e4`
- JSON receipt SHA-256:
  `63312d796565e381472959181cba0394ebadd924752f3c713e3b26718d2dbeb3`

## Measured fixture values

| Tool | Identifier completeness | Required-field completeness | Duplicates | Duration | Throughput | Cost |
|---|---:|---:|---:|---:|---:|---:|
| local-fixture | 100% | 100% | 0 | 1.6 seconds | 1125 records/minute | 0 |
| competitor-fixture | 93.3333% | 81.6667% | 1 | 4.2 seconds | 400 records/minute | 25 |

`competitor-fixture` marks `media.source_url` as unsupported.

## Conclusions

For this synthetic fixture only, `local-fixture` leads every measured criterion.

This result does not describe a named external service.
Use direct measured exports before making an external product claim.

## Command

```powershell
uv run pgscan compare `
  --first tests/fixtures/comparison/local-results.json `
  --second tests/fixtures/comparison/competitor-results.csv `
  --output OUTPUT
```
