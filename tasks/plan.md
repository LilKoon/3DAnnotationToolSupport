# V4: phased implementation
Authorized by user 2026-10-03: design and implement V4 based on V3, complete tests.

1. Foundation + regression baseline + data audit.
2. Ground segmentation/display/supported surface + scene focus/contact.
3. Calibration/projection + image detection + evidence/missing-object review.
4. Geometry measurements + evaluation/diagnostics.
5. Full regression, browser E2E, performance, documentation and source integrity review.

V4 data is isolated. V3 files unchanged. Camera fusion requires valid reviewed calibration and known frame pairing; no image-only invented metric boxes. Reuse existing V3 checkpoint files through read-only reference. Fully learned fusion and temporal aggregation are research gates, not falsely presented as implemented detector models.
Acceptance: all V3 regression tests; new unit/API tests for each feature; browser flows including missing calibration; actual image model smoke when a checkpoint/runtime is available. Report unavailable dataset accuracy/held-out GT honestly.
No destructive file modifications. New files written exclusively; fixes preserve old content via additive modules where possible. Root plans remain intact; this file supersedes their V3 implementation target.

## Completion 2026-10-03
Phases 1–5 delivered; 93 Python tests, 8 JavaScript groups, 18 Chrome checks passed. Evidence and remaining research gates: ../TEST_REPORT.md and todo.md. Learned fusion/temporal are not production implementations and require verified calibration/time/pose and held-out labels.
