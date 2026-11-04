"""
LangGraph Multi-Agent Workflow Definition.
Builds and compiles the StateGraph workflow connecting agents and merger.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import ReviewGraphNodes
from app.graph.state import ReviewGraphState


def create_review_graph(nodes: ReviewGraphNodes) -> Any:
    """Builds and compiles the sequential multi-agent review graph.

    Note: Configured for sequential agent execution to respect Groq free-tier
    token and RPM rate limits and conserve memory on 8 GB RAM machines.
    Can be switched to parallel branching when quota is increased.
    """
    workflow = StateGraph(ReviewGraphState)

    # Register Nodes
    workflow.add_node("static_analysis", nodes.static_analysis_node)
    workflow.add_node("security_review", nodes.security_review_node)
    workflow.add_node("architecture_review", nodes.architecture_review_node)
    workflow.add_node("style_review", nodes.style_review_node)
    workflow.add_node("merge_findings", nodes.merge_findings_node)
    workflow.add_node("synthesize_review", nodes.synthesize_review_node)

    # Connect Edges Sequentially
    workflow.add_edge(START, "static_analysis")
    workflow.add_edge("static_analysis", "security_review")
    workflow.add_edge("security_review", "architecture_review")
    workflow.add_edge("architecture_review", "style_review")
    workflow.add_edge("style_review", "merge_findings")
    workflow.add_edge("merge_findings", "synthesize_review")
    workflow.add_edge("synthesize_review", END)

    return workflow.compile()
