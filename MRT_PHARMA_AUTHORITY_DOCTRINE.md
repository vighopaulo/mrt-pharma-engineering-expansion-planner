# MRT Pharma — Authority Doctrine (Governance)

**Build:** MRT Pharma Authority Consolidation (governance / traceability).
**Purpose:** the permanent repository doctrine for how authority, project truth,
and traceability are governed — so future work depends on **validated repository
authority** rather than session memory, conversation reconstruction, prompt
shorthand, or developer recollection.

This document changes no production-engine behavior. It is companion to
`MRT_PHARMA_AUTHORITY_INDEX.md` (the navigation map) and `MRT_PHARMA_OPEN_GAPS.md`
(the register of what is not yet implemented).

---

## 1. The authority-first governance rule

> **VALIDATED REPOSITORY AUTHORITY  >  SESSION MEMORY  >  PROMPT SHORTHAND.**

Before any future build **creates, redefines, or duplicates** an authority:

1. Read `MRT_PHARMA_AUTHORITY_INDEX.md`.
2. Locate the canonical implementation / document for the concern.
3. Inspect its focused tests.
4. Read `MRT_PHARMA_OPEN_GAPS.md`.
5. Determine whether the new instruction:
   - **(a) reuses** an existing authority,
   - **(b) extends** an existing authority,
   - **(c) explicitly supersedes** an existing authority (record it as
     `SUPERSEDED`, never delete the lineage), or
   - **(d) closes a real documented gap.**

Do **not** create a second authority merely because a later prompt uses different
terminology for the same concept. Terminology drift is not a new requirement.

If a prompt and the repository disagree, the **validated repository authority
wins** until the prompt explicitly and knowingly supersedes it.

---

## 2. Three classes of project truth

Every important MRT Pharma statement is classifiable as exactly one of:

### A. `LOCKED_PRODUCT_DOCTRINE`
A durable product decision. Example: "MRT Pharma = Capital Project + Operations";
"ENGINEERING ENGINE DECIDES → NVIDIA VISUALIZES"; "color is presentation metadata
only". Doctrine constrains implementation but is not itself code.

### B. `IMPLEMENTED_REPOSITORY_AUTHORITY`
Behavior physically represented in repository code **and** tests. Example: the
per-radionuclide cyclotron production resolver; `derive_physical_feasibility`; the
lockdown/what-if lineage registry.

### C. `PLANNED_REQUIREMENT`
Agreed future behavior not yet physically implemented. Example: the Cyclotron
Production Estimation Authority; live ARIA integration; CAD/BIM file ingestion
parsers; the NVIDIA Omniverse runtime.

> **The cardinal rule: never describe a `PLANNED_REQUIREMENT` (C) as an
> `IMPLEMENTED_REPOSITORY_AUTHORITY` (B).**

### Additional status vocabulary (preserve where useful)

`CONTROLLED_BENCHMARK` · `MODELED` · `NOT_CALIBRATED` · `NOT_MODELED` · `PARTIAL`
· `SUPERSEDED` · `NOT_APPLICABLE`.

These qualify a B-class authority's confidence/scope. In particular:

- `NOT_CALIBRATED` ≠ `ZERO`, and `NOT_CALIBRATED` ≠ infeasible. Honest unknowns
  are never fabricated and never silently coerced to 0.
- `CONTROLLED_BENCHMARK` is a fixed controlled scenario assumption (e.g. the
  6 scanners / 6 injection / 12 uptake Part 3D clinical benchmark), never
  presented as customer facility truth.
- `SUPERSEDED` marks a replaced authority whose lineage is preserved (e.g. legacy
  shims kept for compatibility).

---

## 3. Two products, one authority set

**MRT PHARMA = CAPITAL PROJECT + OPERATIONS**, sharing one validated set of
physical/engineering authorities.

- **Capital Project** determines the best facility/equipment/transport
  configuration under user constraints. Transport technologies are **composable
  building blocks**; **MRT is optional**; "NO BUILD" is a valid outcome.
- **Operations** manages/plans the operating facility from actual/planned demand
  and resources.

The `CAPITAL_PLANNING` vs `OPERATIONAL_ONLY` scope and the `CONVENTIONAL/MRT/
HYBRID` transport architecture are independent, composable axes (`study_scope.py`).

**Patient-source doctrine:** demand is upstream. In Capital Project, patients are
a synthetic/modeled population from project demand; cyclotron/generator/scanner/
transport capacity does **not** create patients. In Operations, the patient source
is the actual/planned population — with ARIA-class systems as the upstream
system-of-record feeding a vendor-neutral canonical model. MRT Pharma does not
replace ARIA.

---

## 4. Layer separation doctrine

- **BENTLEY / iTwin** = engineering/facility geometry & infrastructure context.
- **MRT PHARMA** = engineering logic + physics + optimization + economics +
  operations (the authority that **decides**).
- **NVIDIA / OpenUSD** = visualization / animation / interactive presentation
  (renders authoritative state; never changes physics).

These three layers must never be conflated. Neither Bentley nor NVIDIA replaces
MRT Pharma.

---

## 5. Radionuclide-specificity doctrine

**Calibration for radionuclide A does not qualify radionuclide B.** A calibrated
F-18 production record must never qualify C-11, N-13, O-15, Ga-68, Cu-64, Zr-89,
I-123, I-124, Tc-99m, or any other radionuclide. Every required radionuclide
resolves its own compatible production source and calibration status; supported
but uncalibrated → `NOT_CALIBRATED`; no compatible source → reported explicitly.
Normalization to common units (MBq) never makes radionuclides interchangeable.

---

## 6. Maintenance protocol

- When an authority changes, update its row in `MRT_PHARMA_AUTHORITY_INDEX.md`.
- When a `PLANNED_REQUIREMENT` is genuinely implemented, move it out of
  `MRT_PHARMA_OPEN_GAPS.md` (to a "Closed gaps" section with the closing
  build/commit) and flip its status to `IMPLEMENTED_REPOSITORY_AUTHORITY` in the
  index.
- When an authority is superseded, mark it `SUPERSEDED` and record the successor;
  never delete the lineage.
- Classification is evidence-based: verify against the physical repository (code +
  tests), not memory.

---

*This doctrine is a governance artifact and introduces no production-engine
behavior.*
