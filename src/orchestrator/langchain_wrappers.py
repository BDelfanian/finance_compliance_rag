"""
STEP 6.3 — LangChain Agent Wrappers (Final, Polished)
------------------------------------------------------
Provides RunnableLambda wrappers for STEP 6 agents, with a helper
`make_chain` for easy mocking in tests.

IMPORTANT:
- No logic is added
- No prompts are introduced
- No behavior is changed
"""

from langchain_core.runnables import RunnableLambda

from src.agents.citation_agent import citation_agent
from src.agents.retrieval_agent import retrieval_agent
from src.agents.risk_assessment_agent import risk_assessment_agent
from src.agents.summarization_agent import summarization_agent


# -------------------------------
# Helper for test-friendly chain creation
# -------------------------------
def make_chain(async_fn):
    """
    Wraps an async function in a RunnableLambda.

    This is test-friendly and allows patching chains easily.

    Args:
        async_fn (coroutine function): The async function to wrap.

    Returns:
        RunnableLambda: Async-safe wrapper around the function.
    """
    return RunnableLambda(lambda x: x, afunc=async_fn)


# -------------------------------
# Runnable wrappers (async-safe)
# -------------------------------

retrieval_chain = make_chain(retrieval_agent)
"""Async-safe wrapper for the retrieval agent."""

citation_chain = make_chain(
    lambda inputs: citation_agent(
        query=inputs["query"],
        retrieval_result=inputs["retrieval_result"],
    )
)
"""Async-safe wrapper for the citation agent."""

summarization_chain = make_chain(
    lambda inputs: summarization_agent(
        citation_result=inputs["citation_result"],
        mode=inputs.get("mode", "executive"),
    )
)
"""Async-safe wrapper for the summarization agent."""

risk_assessment_chain = make_chain(
    lambda inputs: risk_assessment_agent(
        citation_result=inputs["citation_result"],
        retrieval_result=inputs["retrieval_result"],
    )
)
"""Async-safe wrapper for the risk assessment agent."""
