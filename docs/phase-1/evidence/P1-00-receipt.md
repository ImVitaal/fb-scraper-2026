# P1-00 evidence receipt

## Identity

- Work item: `P1-00`
- Baseline commit: `9cc24763bdf446faf1efce1b6392667664285175`
- Branch: `main`
- Verification date: `2026-07-29`
- Verification state: passed

## Exact commands

```powershell
git status --porcelain=v1
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
Get-FileHash AGENTS.md -Algorithm SHA256
Get-FileHash README.md -Algorithm SHA256
Get-FileHash FACEBOOK_PRODUCT_DISCOVERY_ANSWERS.md -Algorithm SHA256
Get-FileHash PHASE_1_OPTIMAL_PLAN.md -Algorithm SHA256
Get-FileHash PHASE_1_CRITICAL_REVIEW.md -Algorithm SHA256
Select-String -Path $files -Pattern 'private.Group|30 days|top-level comments|Windows|resume|replay'
```

## Tool versions

- Git: recorded by the repository commit.
- PowerShell: native Windows verification shell.

## Results

- Repository: present.
- Branch: `main`.
- Working tree before receipt creation: clean.
- Local branch position: one commit ahead of `origin/main`.
- Product package state: not started.
- Existing work-item records before this receipt: zero.
- Tests: not applicable to the documentation baseline.

## Control-document hashes

| Artifact | SHA-256 |
|---|---|
| `AGENTS.md` | `28ffb9a7e2e26a49b74247fee3a5176f024e78fcc02d8b95578fe4789c8b1918` |
| `README.md` | `b25958d14a173153315f0e132dafe88cb366ef8ba4018f038144d332f634e533` |
| `FACEBOOK_PRODUCT_DISCOVERY_ANSWERS.md` | `b8913a208793ab7de2f78159a760549291e7ca0541456bb4f9a936db6a04096c` |
| `PHASE_1_OPTIMAL_PLAN.md` | `4c9f2b581657fbf6df98a486e71b36d58b4206f661d92ea830bfc4d4671bce12` |
| `PHASE_1_CRITICAL_REVIEW.md` | `59e5b66b1ab66ef1144ddfdb57f3432a5ce8d2551bfca1ae50f2f620dca2db27` |

## Acceptance-gate mapping

| Gate | Evidence | Result |
|---|---|---|
| Repository exists | Git commands completed | Pass |
| Baseline commit exists | Commit `9cc24763bdf446faf1efce1b6392667664285175` | Pass |
| Controls align | Required Phase 1 terms occur across all five controls | Pass |
| Phase 1 source is explicit | `PHASE_1_OPTIMAL_PLAN.md` Revision 3 | Pass |
| Later phases remain gated | README, plan, and review preserve four-phase order | Pass |

## Limitations and open defects

No implementation existed at this gate. `P1-01` owns package and tooling creation.
