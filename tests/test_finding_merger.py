"""
Unit tests for the FindingMerger and Deduplication Engine.
"""

from app.schemas.review import Finding, Severity
from app.services.orchestrator.merger import FindingMerger


def test_merger_combines_duplicates_on_same_line() -> None:
    """Verifies that two agents flagging the same line in a file are merged into one finding."""
    f1 = Finding(
        agent_name="static_analysis_agent",
        title="Unsanitized SQL concatenation",
        description="SQL statement formatted with raw user input",
        severity=Severity.HIGH,
        confidence=0.85,
        file_path="src/database.py",
        line_number=25,
        code_snippet="query = f'SELECT * FROM users WHERE name = {name}'",
        suggested_fix="Use parameterized queries",
        reasoning="Direct string interpolation",
    )
    f2 = Finding(
        agent_name="security_agent",
        title="SQL Injection Vulnerability",
        description="High risk SQL injection vulnerability (OWASP A03)",
        severity=Severity.CRITICAL,
        confidence=0.98,
        file_path="src/database.py",
        line_number=25,
        code_snippet="query = f'SELECT * FROM users WHERE name = {name}'",
        suggested_fix="Use cursor.execute(query, (name,))",
        reasoning="Untrusted variable interpolated into SQL command",
    )

    merger = FindingMerger()
    merged = merger.merge({"static": [f1], "security": [f2]})

    assert len(merged) == 1
    result = merged[0]
    # Highest severity retained
    assert result.severity == Severity.CRITICAL
    # Highest confidence retained
    assert result.confidence == 0.98
    # Combined contributing agents
    assert "security_agent" in result.agent_name
    assert "static_analysis_agent" in result.agent_name
    assert result.file_path == "src/database.py"
    assert result.line_number == 25


def test_merger_preserves_distinct_issues_in_same_file() -> None:
    """Verifies that distinct issues in the same file are NOT removed."""
    f1 = Finding(
        agent_name="static_analysis_agent",
        title="Unused variable 'counter'",
        description="Variable is declared but never referenced",
        severity=Severity.LOW,
        confidence=0.90,
        file_path="src/service.py",
        line_number=10,
        reasoning="Variable dead store",
    )
    f2 = Finding(
        agent_name="security_agent",
        title="Hardcoded API Secret",
        description="Found production API secret in source code",
        severity=Severity.CRITICAL,
        confidence=0.99,
        file_path="src/service.py",
        line_number=88,
        code_snippet="API_SECRET = 'sk_live_12345'",
        suggested_fix="Move secret to environment variable",
        reasoning="Literal credential in file",
    )

    merger = FindingMerger()
    merged = merger.merge({"static": [f1], "security": [f2]})

    assert len(merged) == 2
    # Ranked by severity weight: CRITICAL first, then LOW
    assert merged[0].severity == Severity.CRITICAL
    assert merged[0].title == "Hardcoded API Secret"
    assert merged[1].severity == Severity.LOW
    assert merged[1].title == "Unused variable 'counter'"


def test_merger_severity_sorting() -> None:
    """Verifies findings are strictly sorted by severity rank."""
    findings = [
        Finding(
            agent_name="style_agent",
            title="Non-idiomatic variable name",
            description="",
            severity=Severity.INFO,
            file_path="a.py",
            reasoning="",
        ),
        Finding(
            agent_name="security_agent",
            title="Command Injection",
            description="",
            severity=Severity.CRITICAL,
            file_path="b.py",
            reasoning="",
        ),
        Finding(
            agent_name="architecture_agent",
            title="Cyclic Dependency",
            description="",
            severity=Severity.MEDIUM,
            file_path="c.py",
            reasoning="",
        ),
    ]

    merger = FindingMerger()
    merged = merger.merge({"agents": findings})

    assert [f.severity for f in merged] == [Severity.CRITICAL, Severity.MEDIUM, Severity.INFO]
