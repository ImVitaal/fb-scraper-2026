# Phase 2 running log

## Current state

- Phase 1 fixture-backed gate: passed in `94b80fb`.
- Phase 2 ten-Group fixture gate: passed.
- Active milestone: Phase 3 fixture comparison.
- Worker limit: 1.

## Delivery

- Added ten distinct synthetic Group fixtures.
- Reused the Phase 1 fixture workflow without changing its record contracts.
- Added sequential collection for one through ten Groups.
- Added explicit per-Group succeeded and failed terminal states.
- Added durable batch progress after every Group.
- Added failure isolation and incomplete-Group resume.
- Preserved completed Groups during resume.
- Added aggregate duration, CPU, memory, storage, retry, completeness, and throughput metrics.
- Kept the worker limit at one because no measured concurrency improvement exists.

## Verification

- Ten Groups reached succeeded terminal states.
- One injected failure left nine completed Groups intact.
- Resume retried only the failed Group.
- Resumed and uninterrupted identifier and normalized-hash sets matched.
- The ten-Group CLI produced one receipt and one Markdown metrics report.
