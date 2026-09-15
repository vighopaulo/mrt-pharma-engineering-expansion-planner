"""Repository-wide static guard for the four-quantity production doctrine (Build 3B).

INVARIANT UNDER TEST
--------------------
No authoritative, executable production-feasibility / optimization / ranking / capacity /
CapEx path may derive PHYSICAL radioactive-production capacity (MBq/day EOB or its
dose-equivalent throughput) from:

    * dose count                          (``current_usable_doses_per_day`` as a ceiling)
    * production blocks                   (``production_blocks`` driving physical capacity)
    * 10% block expressions               (``* (1 + blocks * 0.1)`` / ``* 0.10`` inflation)
    * ``production_expansion_capex_per_10pct`` used as a physical-capacity multiplier
    * any equivalent synthetic capacity expression

The canonical physical chain (see ``operational_day_orchestrator.compute_radioactive_
production_chain``) instead resolves an *installed* EOB capacity and reports
``NOT_CALIBRATED`` when none exists -- it never fabricates a number.

WHY A STATIC GUARD
------------------
Behavioral tests (see ``test_production_capacity_behavioral_closure.py``) prove the runtime
outputs are correct. This guard additionally prevents *reintroduction* of the legacy model
into the authoritative modules by inspecting their EXECUTABLE source (AST), while allowing
the historical vocabulary to survive in comments, docstrings, migration notes, and
explicitly non-authoritative compatibility structures.

The guard is deliberately NOT a naive substring scan of one module; it covers the full set
of authoritative production/optimization/capacity modules named by the pre-AWS audit.
"""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

import pytest

# Authoritative modules that participate in production feasibility, optimization, ranking,
# capacity or CapEx. The prohibited physical-capacity model must not be EXECUTABLE in any
# of these.
AUTHORITATIVE_PRODUCTION_MODULES = (
    "equal_budget.py",
    "optimization.py",
    "cyclotron_production_estimation_authority.py",
    "cycle_relative_production_requirement.py",
    "operational_day_orchestrator.py",
    "shared_network.py",
)

# The prohibited legacy dose-count / production-block physical-capacity token combinations.
# These describe *executable* patterns; comments/strings are stripped before matching.
_DOSE_COUNT_TOKEN = "current_usable_doses_per_day"
_PRODUCTION_BLOCKS_TOKEN = "production_blocks"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _executable_source(path: Path) -> str:
    """Return module source with comments AND string literals removed.

    Comments and string literals (docstrings, ledger labels, provenance notes, the
    doctrine-explaining banner in operational_day_orchestrator) are legitimate places for
    the historical vocabulary to appear. Only genuinely executable code should be matched.
    """
    src = path.read_text(encoding="utf-8")
    out: list[str] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(src).readlines().__iter__().__next__)
        for tok in tokens:
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                # Replace with a neutral placeholder preserving line structure.
                out.append(" ")
                continue
            out.append(tok.string)
    except (tokenize.TokenError, IndentationError):
        # Fall back to raw source if tokenization fails; better to over-report than miss.
        return src
    return " ".join(out)


def _executable_lines(path: Path) -> list[tuple[int, str]]:
    """Return (lineno, code-without-comment) for lines whose EXECUTABLE portion is non-empty."""
    src_lines = path.read_text(encoding="utf-8").splitlines()
    result: list[tuple[int, str]] = []
    try:
        readline = io.StringIO("\n".join(src_lines) + "\n").readline
        # Build a per-line mask of code vs comment/string via token positions.
        code_only = [""] * (len(src_lines) + 2)
        for tok in tokenize.generate_tokens(readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE):
                continue
            if tok.type in (tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER, tokenize.ENCODING):
                continue
            start_line = tok.start[0]
            if 1 <= start_line <= len(src_lines):
                code_only[start_line] += tok.string + " "
    except (tokenize.TokenError, IndentationError):
        return [(i + 1, ln) for i, ln in enumerate(src_lines)]
    for i, code in enumerate(code_only):
        if code.strip():
            result.append((i, code))
    return result


@pytest.mark.parametrize("module_name", AUTHORITATIVE_PRODUCTION_MODULES)
def test_no_ten_percent_block_capacity_expression(module_name: str) -> None:
    """No authoritative module may contain an executable 10%-block capacity inflation."""
    path = _repo_root() / module_name
    assert path.exists(), f"authoritative module missing: {module_name}"

    offenders: list[str] = []
    for lineno, code in _executable_lines(path):
        compact = code.replace(" ", "")
        # `current_usable_doses_per_day * (1 + ... * 0.1)` style inflation, in any spacing.
        if _DOSE_COUNT_TOKEN in compact and ("*(1" in compact or "*(1.0" in compact):
            offenders.append(f"{module_name}:{lineno}: {code.strip()}")
        # `... * 0.10` or `... * 0.1)` capacity inflation coupled with production blocks.
        if _PRODUCTION_BLOCKS_TOKEN in compact and ("*0.1" in compact or "*0.10" in compact):
            offenders.append(f"{module_name}:{lineno}: {code.strip()}")

    assert not offenders, (
        "Legacy 10% dose-count production-block physical-capacity expression reintroduced "
        "into authoritative executable code:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("module_name", AUTHORITATIVE_PRODUCTION_MODULES)
def test_dose_count_not_used_as_physical_capacity_multiplier(module_name: str) -> None:
    """`current_usable_doses_per_day` must not be multiplied by a (1 + blocks*0.1) factor.

    It may still legitimately appear as an OBSERVED CURRENT baseline reference
    (e.g. ``current_usable_doses_per_day * retained`` in a baseline comparator), which is
    not a fabricated physical-capacity ceiling. The prohibited pattern is specifically the
    block-inflation multiplier.
    """
    path = _repo_root() / module_name
    exec_src = _executable_source(path).replace(" ", "")

    # Prohibited: current_usable_doses_per_day * (1 + production_blocks * 0.1) and variants.
    prohibited_fragments = (
        f"{_DOSE_COUNT_TOKEN}*(1.0+{_PRODUCTION_BLOCKS_TOKEN}",
        f"{_DOSE_COUNT_TOKEN}*(1+{_PRODUCTION_BLOCKS_TOKEN}",
        "*(1.0+production_blocks*0.1",
        "*(1+production_blocks*0.1",
        "*(1.0+0.1*production_blocks",
        "*(1+0.1*production_blocks",
    )
    hits = [frag for frag in prohibited_fragments if frag in exec_src]
    assert not hits, (
        f"{module_name}: prohibited dose-count block-inflation multiplier found in executable "
        f"code: {hits}"
    )


@pytest.mark.parametrize("module_name", AUTHORITATIVE_PRODUCTION_MODULES)
def test_no_production_block_multiplier_helper(module_name: str) -> None:
    """No authoritative module may define/consume a `production_block_multiplier` that
    inflates a calibrated physical capacity (the removed
    `_cyclotron_eob_capacity_mbq_per_day(..., production_block_multiplier)` pattern)."""
    path = _repo_root() / module_name
    tree = ast.parse(path.read_text(encoding="utf-8"))

    offenders: list[str] = []
    for node in ast.walk(tree):
        # A function parameter literally named production_block_multiplier is the removed
        # legacy signature; flag it.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arg_names = {a.arg for a in node.args.args} | {a.arg for a in node.args.kwonlyargs}
            if "production_block_multiplier" in arg_names:
                offenders.append(f"{module_name}: {node.name}() takes production_block_multiplier")

    assert not offenders, (
        "Legacy production-block capacity-multiplier helper reintroduced:\n  "
        + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------------------
# Pre-AWS adjudication — uncalibrated-production multiplier static guards
# ---------------------------------------------------------------------------
import inspect  # noqa: E402


def test_uncalibrated_multiplier_never_references_dose_count() -> None:
    """The decay-optimal release-level helper must never read current_usable_doses_per_day or
    production blocks (it is a pure decay-physics device, not a capacity authority)."""
    import equal_budget as eb

    src = inspect.getsource(eb._uncalibrated_production_gross_multiplier)
    assert "current_usable_doses_per_day" not in src
    assert "production_blocks" not in src
    assert "production_expansion_capex_per_10pct" not in src


def test_uncalibrated_multiplier_only_called_in_uncalibrated_branch() -> None:
    """The multiplier must be called exactly once, and only inside the uncalibrated (else)
    branch of `_build_mrt_economic_candidate` -- never from the calibrated branch."""
    import equal_budget as eb

    cand_src = inspect.getsource(eb._build_mrt_economic_candidate)
    assert cand_src.count("_uncalibrated_production_gross_multiplier(") == 1
    # The single call must appear AFTER the `else:` of `if capacity_is_calibrated:` and never
    # inside the calibrated branch. Verify the calibrated branch (before the else) has no call.
    calibrated_branch, _, uncalibrated_branch = cand_src.partition("    else:")
    assert "_uncalibrated_production_gross_multiplier(" not in calibrated_branch
    assert "_uncalibrated_production_gross_multiplier(" in uncalibrated_branch
