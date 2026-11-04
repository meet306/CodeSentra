"""
Unit tests for the four specialized review agents.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.architecture_agent import ArchitectureAgent
from app.agents.security_agent import SecurityAgent
from app.agents.static_agent import StaticAnalysisAgent
from app.agents.style_agent import CodeStyleAgent
from app.config import Settings
from app.integrations.groq import GroqClient
from app.schemas.github import PRDiffData
from app.schemas.review import Severity


@pytest.fixture
def mock_groq_client(test_settings: Settings) -> GroqClient:
    mock_client = MagicMock(spec=GroqClient)
    real_client = GroqClient(settings=test_settings)
    mock_client.parse_findings_from_dict = real_client.parse_findings_from_dict
    return mock_client


@pytest.mark.asyncio
async def test_static_agent_identifies_bug(
    test_settings: Settings,
    sample_diff_data: PRDiffData,
    mock_groq_client: GroqClient,
) -> None:
    mock_groq_client.generate_completion_with_retry = AsyncMock(
        return_value={
            "data": {
                "findings": [
                    {
                        "title": "Index Out of Range",
                        "description": "Accessing items[10] without checking list length",
                        "severity": "HIGH",
                        "confidence": 0.9,
                        "file_path": "src/auth.py",
                        "line_number": 3,
                        "reasoning": "Unchecked index access",
                    }
                ]
            }
        }
    )

    agent = StaticAnalysisAgent(groq_client=mock_groq_client, settings=test_settings)
    findings = await agent.analyze(sample_diff_data)

    assert len(findings) == 1
    assert findings[0].agent_name == "static_analysis_agent"
    assert findings[0].severity == Severity.HIGH
    assert findings[0].file_path == "src/auth.py"


@pytest.mark.asyncio
async def test_security_agent_identifies_vulnerability(
    test_settings: Settings,
    sample_diff_data: PRDiffData,
    mock_groq_client: GroqClient,
) -> None:
    mock_groq_client.generate_completion_with_retry = AsyncMock(
        return_value={
            "data": {
                "findings": [
                    {
                        "title": "Insecure Deserialization",
                        "description": "Use of unsafe pickle.loads on untrusted data",
                        "severity": "CRITICAL",
                        "confidence": 0.99,
                        "file_path": "src/auth.py",
                        "line_number": 4,
                        "reasoning": "pickle is vulnerable to arbitrary code execution",
                    }
                ]
            }
        }
    )

    agent = SecurityAgent(groq_client=mock_groq_client, settings=test_settings)
    findings = await agent.analyze(sample_diff_data)

    assert len(findings) == 1
    assert findings[0].agent_name == "security_agent"
    assert findings[0].severity == Severity.CRITICAL


@pytest.mark.asyncio
async def test_architecture_agent_evaluates_structure(
    test_settings: Settings,
    sample_diff_data: PRDiffData,
    mock_groq_client: GroqClient,
) -> None:
    mock_groq_client.generate_completion_with_retry = AsyncMock(
        return_value={
            "data": {
                "findings": [
                    {
                        "title": "Tight Coupling",
                        "description": "Auth service directly instantiates database connection pool",
                        "severity": "MEDIUM",
                        "confidence": 0.85,
                        "file_path": "src/auth.py",
                        "line_number": 2,
                        "reasoning": "Violates dependency injection",
                    }
                ]
            }
        }
    )

    agent = ArchitectureAgent(groq_client=mock_groq_client, settings=test_settings)
    findings = await agent.analyze(sample_diff_data)

    assert len(findings) == 1
    assert findings[0].agent_name == "architecture_agent"
    assert findings[0].severity == Severity.MEDIUM


@pytest.mark.asyncio
async def test_style_agent_uses_learned_patterns(
    test_settings: Settings,
    sample_diff_data: PRDiffData,
    mock_groq_client: GroqClient,
) -> None:
    mock_groq_client.generate_completion_with_retry = AsyncMock(
        return_value={
            "data": {
                "findings": [
                    {
                        "title": "Naming Convention Violation",
                        "description": "Function name uses camelCase instead of snake_case",
                        "severity": "LOW",
                        "confidence": 0.95,
                        "file_path": "src/auth.py",
                        "line_number": 5,
                        "reasoning": "Repository standard mandates snake_case",
                    }
                ]
            }
        }
    )

    agent = CodeStyleAgent(groq_client=mock_groq_client, settings=test_settings)
    findings = await agent.analyze(sample_diff_data, learned_patterns=["Use snake_case for all functions"])

    assert len(findings) == 1
    assert findings[0].agent_name == "code_style_agent"
    assert findings[0].severity == Severity.LOW
