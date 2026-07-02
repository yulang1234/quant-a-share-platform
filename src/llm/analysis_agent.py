"""
LLM analysis agent — generate natural-language insights from quantitative data.

This module is designed to be provider-agnostic so that different backends
(DeepSeek, GPT, Claude, local models) can be plugged in without changing
the analysis logic.

V0.1: skeleton only.
"""

from __future__ import annotations


class AnalysisAgent:
    """Generate structured analysis reports using an LLM backend.

    TODO(V1.9): implement prompt templates, structured output parsing, and
    provider dispatch (DeepSeek / GPT / Claude / local via Ollama).

    Parameters
    ----------
    provider : str
        Backend model provider, e.g. ``"deepseek"``, ``"openai"``, ``"claude"``.
    api_key : str, optional
        API key.  Read from environment if not provided.
    """

    def __init__(self, provider: str = "deepseek", api_key: str | None = None) -> None:
        self.provider = provider

    def analyze(self, data: dict) -> str:
        """Run analysis against the LLM and return a markdown report.

        TODO(V1.9): implement.

        Parameters
        ----------
        data : dict
            Structured quantitative data (factor scores, rankings, etc.).

        Returns
        -------
        str
            Natural-language analysis report.
        """
        raise NotImplementedError("LLM analysis is a V1.9 feature.")
