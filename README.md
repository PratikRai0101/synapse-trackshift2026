# GRID//OPS — energy and overtake decision support

This workspace currently contains research and development specifications, not a validated racing controller.

**Start here: [corrected development package](docs/development/README.md).** It contains the PRD, four-horizon architecture, physical models, data contracts, validation protocol, two-person 24-hour build path, proposed tickets, glossary, novelty analysis and pitch references.

For a fresh implementation session, use the [developer handoff](docs/development/12-developer-handoff.md). Domain terminology lives in [CONTEXT.md](CONTEXT.md). The main acceptance seam is a complete action-responsive simulation episode with hidden rival truth inaccessible to the controller.

The older HTML in `outputs/` is illustrative. Its displayed scores, confidence and timings are not measured research results. Earlier proposals and literature notes remain background; the corrected package takes precedence where implementation guidance conflicts.

No external issues have been published, no organizer permissions have been assumed, and no application dependencies were installed by the documentation task. Proposed decisions/backlog remain subject to review.

Documentation checks can be repeated with:

```sh
node work/validate-development-docs.mjs
```

These checks validate document structure and references only—not vehicle physics, algorithm performance or real-world compliance.
