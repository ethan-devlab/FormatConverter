# Validation status

The current version is a Windows x64 developer preview. This summary records
previous bounded verification; it is not a certification, capacity guarantee or
claim that every environment has been tested. Per-run logs, local paths, QA
screenshots and exploratory scripts are not part of the public source tree.

## Windows coverage

The source publication check on 2026-10-27 passed TypeScript checking, 18 Node
tests, 116 Python tests, both production frontend builds, documentation links
and the source-archive byte/exclusion checks. Python integration tests used a
fresh short OS temporary path. The checks exposed and corrected a browser
startup race: a successful Edge launcher can exit before its owned CDP endpoint
is available. Successful handoff now keeps the existing bounded wait; nonzero
launcher failures still fail immediately. Two regression cases cover this rule.
The existing portable executable was not rebuilt or revalidated in this source
publication round. Production build chunk-size warnings remain advisory.

Prior automated, browser, portable and user acceptance rounds covered conversion
and Preview/Convert, PDF password roles, OCR, HEIF/ICO, multi-frame inputs,
compression, partial batch failures, cancellation/retry, file operations,
overlapping roots, selection, shortcuts, language/preferences, Save As and
multi-monitor dialog DPI. Desktop narrow layouts were checked; this does not
establish physical mobile-device support.

Maintained automated checks are under tests/. Reproduction commands and the
optional installed-browser/portable smoke scripts are in development.md. Results
from a previous executable do not establish behavior of a newly built package.

## Bounded performance observations

An earlier synthetic Windows workload used 20 logical CPUs and about 32 GiB RAM.
Twenty-four 6000x4000 images took 26.889 seconds with one worker and 12.638 seconds
with four. Sampled aggregate process-tree RSS peaked near 2024.75 MiB in the
four-worker run. Shared memory can be counted more than once. These were single
observations, with a cold first pool and reused workers later, not a promise of
speedup or maximum supported batch size.

Other completed samples included 200-page text extraction/rendering/lossless
optimization, 100-page scan compression, ten-page OCR and a 100-file browser
upload. Manual foreground page-visit INP observations were 16 ms for a control
page, 56 ms for a large directory with 100 queue items, and 72 ms during a
background OCR visit. Earlier automated measurements were affected by foreground/
frame throttling and were not accepted as product INP. These measurements used
synthetic data on one system and do not measure real-world OCR accuracy.

## Safari and macOS

Actual Safari foreground GUI feasibility research produced standard/custom paper
PDFs on one Mac. It is not integrated with the product. Safari remains disabled;
the maintainer plans further validation. Do not infer macOS service, filesystem,
portable or unattended-engine support from that research. No Safari probe or
machine-specific automation configuration is required to build the Windows app.

## Remaining gates

- Clean Windows without developer runtimes.
- Physical mobile devices and other operating systems.
- Larger tier-B workloads and long-duration endurance.
- Wider real-world document layouts, OCR languages and HDR/high-bit-depth fidelity.
- Safari product integration, crash-safe paper recovery, cancellation and user validation.
- Public binary-release signing and native dependency corresponding-source review.
