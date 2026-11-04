"""
Finding Merger and Deduplication Engine.
Normalizes, merges, and ranks findings across all four specialized agents.
"""


from app.core.logging import logger
from app.schemas.review import Finding, Severity

# Severity priority weights for ranking
SEVERITY_WEIGHTS = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
}


class FindingMerger:
    """Consolidates findings from multiple AI agents, eliminating duplicates while preserving evidence."""

    @staticmethod
    def _is_duplicate(f1: Finding, f2: Finding) -> bool:
        """Determines if two findings refer to the same underlying problem."""
        # Must be in the exact same file
        if f1.file_path != f2.file_path:
            return False

        # If both specify line numbers, match if within close proximity (<= 3 lines)
        if f1.line_number is not None and f2.line_number is not None:
            if abs(f1.line_number - f2.line_number) <= 3:
                # Compare title similarity or code snippet overlap
                if f1.title.lower() in f2.title.lower() or f2.title.lower() in f1.title.lower():
                    return True
                if f1.code_snippet and f2.code_snippet:
                    if f1.code_snippet in f2.code_snippet or f2.code_snippet in f1.code_snippet:
                        return True
                # If exact same line, treat as duplicate issue
                if f1.line_number == f2.line_number:
                    return True
            return False

        # If line numbers not present, match on identical snippet or identical titles in same file
        if f1.code_snippet and f2.code_snippet and f1.code_snippet.strip() == f2.code_snippet.strip():
            return True

        if f1.title.strip().lower() == f2.title.strip().lower():
            return True

        return False

    @staticmethod
    def _combine_findings(primary: Finding, secondary: Finding) -> Finding:
        """Merges two overlapping findings into a single high-fidelity finding."""
        # Determine highest severity
        w1 = SEVERITY_WEIGHTS.get(primary.severity, 1)
        w2 = SEVERITY_WEIGHTS.get(secondary.severity, 1)
        highest_severity = primary.severity if w1 >= w2 else secondary.severity

        # Combined contributing agents
        agents = set()
        for a in [primary.agent_name, secondary.agent_name]:
            agents.update(a.split(", "))
        combined_agent_name = ", ".join(sorted(agents))

        # Highest confidence
        max_confidence = max(primary.confidence, secondary.confidence)

        # Prefer line number if available
        line_num = primary.line_number if primary.line_number is not None else secondary.line_number

        # Best code snippet
        snippet = primary.code_snippet or secondary.code_snippet

        # Best suggested fix (longer / more detailed)
        fix1 = primary.suggested_fix or ""
        fix2 = secondary.suggested_fix or ""
        suggested_fix = fix1 if len(fix1) >= len(fix2) else fix2

        # Combined description if distinct
        desc = primary.description
        if secondary.description and secondary.description not in primary.description:
            desc = f"{primary.description}\n\nAdditional perspective ({secondary.agent_name}): {secondary.description}"

        # Combined reasoning
        reasoning = f"{primary.reasoning} | {secondary.reasoning}"

        return Finding(
            agent_name=combined_agent_name,
            title=primary.title if w1 >= w2 else secondary.title,
            description=desc,
            severity=highest_severity,
            confidence=max_confidence,
            file_path=primary.file_path,
            line_number=line_num,
            code_snippet=snippet,
            suggested_fix=suggested_fix if suggested_fix else None,
            reasoning=reasoning,
        )

    def merge(self, agent_findings_map: dict[str, list[Finding]]) -> list[Finding]:
        """Collects, deduplicates, and ranks findings from all agent outputs."""
        all_findings: list[Finding] = []
        for agent_name, findings in agent_findings_map.items():
            logger.debug(f"Merger received {len(findings)} findings from {agent_name}")
            all_findings.extend(findings)

        if not all_findings:
            logger.info("Merger received 0 total findings across all agents.")
            return []

        merged: list[Finding] = []

        for candidate in all_findings:
            matched_index = -1
            for idx, existing in enumerate(merged):
                if self._is_duplicate(existing, candidate):
                    matched_index = idx
                    break

            if matched_index >= 0:
                # Merge into existing finding
                merged[matched_index] = self._combine_findings(merged[matched_index], candidate)
            else:
                merged.append(candidate)

        # Rank findings: primary sort by severity weight (descending), secondary sort by confidence (descending)
        ranked = sorted(
            merged,
            key=lambda f: (SEVERITY_WEIGHTS.get(f.severity, 1), f.confidence),
            reverse=True,
        )

        logger.info(
            f"Merger deduplicated {len(all_findings)} raw findings down to {len(ranked)} consolidated findings."
        )
        return ranked
