## What changes and why

<!-- One or two sentences a business owner can read. -->

## Definitions touched

<!-- Delete this section if no metric, rule or golden question changes. -->

- Metric(s): <!-- e.g. available_stock -->
- Decision record: <!-- new DR-0xx, or DR-0xx superseded by DR-0yy. A record is never edited to change its decision. -->
- Golden questions added or updated: <!-- ids -->

## Affected metrics and exposures

<!-- Paste the output of `make affected BASE=origin/main`. -->

## Checklist

- [ ] `make build`, `make lint` and `make test` pass locally
- [ ] Expected values re-frozen (`make golden-freeze`) if the reference or the data changed, and the diff of `golden/expected/` reviewed
- [ ] `governance/registry.md` regenerated (`make registry`) if a metric's owner, status or version changed
- [ ] `version` bumped and `certified_on` updated on every certified metric whose number moves
- [ ] The business owner of each touched metric has approved (CODEOWNERS requests them)
- [ ] Owners of the affected exposures above know the number will move
