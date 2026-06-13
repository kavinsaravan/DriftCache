"""
Agent Tool Registry

Central registry for all LangChain tools available to agents
"""
from typing import List
from langchain.tools import BaseTool
import logging

from app.agents.tools.drift_tools import get_drift_tools
from app.agents.tools.cache_tools import get_cache_tools
from app.agents.tools.metrics_tools import get_metrics_tools
from app.agents.tools.threshold_tools import get_threshold_tools
from app.agents.tools.index_tools import get_index_tools

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry for agent tools

    Provides organized access to all infrastructure operation tools
    """

    @staticmethod
    def get_all_tools() -> List[BaseTool]:
        """
        Get complete list of all available tools

        Returns all tools across all categories:
        - Drift analysis (2 tools)
        - Cache management (2 tools)
        - Metrics retrieval (2 tools)
        - Threshold management (2 tools)
        - Index operations (2 tools)

        Total: 10 tools for Week 6
        """
        tools = []

        # Add drift tools
        tools.extend(get_drift_tools())
        logger.info(f"Registered {len(get_drift_tools())} drift tools")

        # Add cache tools
        tools.extend(get_cache_tools())
        logger.info(f"Registered {len(get_cache_tools())} cache tools")

        # Add metrics tools
        tools.extend(get_metrics_tools())
        logger.info(f"Registered {len(get_metrics_tools())} metrics tools")

        # Add threshold tools
        tools.extend(get_threshold_tools())
        logger.info(f"Registered {len(get_threshold_tools())} threshold tools")

        # Add index tools
        tools.extend(get_index_tools())
        logger.info(f"Registered {len(get_index_tools())} index tools")

        logger.info(f"Total tools registered: {len(tools)}")
        return tools

    @staticmethod
    def get_tools_by_category(category: str) -> List[BaseTool]:
        """
        Get tools for a specific category

        Args:
            category: Tool category (drift, cache, metrics, threshold, index)

        Returns:
            List of tools in that category
        """
        category_map = {
            "drift": get_drift_tools,
            "cache": get_cache_tools,
            "metrics": get_metrics_tools,
            "threshold": get_threshold_tools,
            "index": get_index_tools,
        }

        if category not in category_map:
            logger.warning(f"Unknown category: {category}")
            return []

        return category_map[category]()

    @staticmethod
    def get_observability_tools() -> List[BaseTool]:
        """
        Get tools for observability (read-only operations)

        Returns:
            Tools for reading system state without modifications
        """
        tools = []
        tools.extend(get_drift_tools())
        tools.extend(get_cache_tools())  # get_cache_quality is read-only
        tools.extend(get_metrics_tools())
        # Exclude write operations like threshold updates and rebuilds
        return tools

    @staticmethod
    def get_action_tools() -> List[BaseTool]:
        """
        Get tools for actions (write operations)

        Returns:
            Tools that modify system state
        """
        tools = []
        tools.extend(get_threshold_tools())
        tools.extend(get_index_tools())
        # Note: cache invalidation is in cache_tools but is an action
        return tools

    @staticmethod
    def list_tool_names() -> List[str]:
        """
        Get list of all tool names

        Useful for debugging and documentation
        """
        tools = ToolRegistry.get_all_tools()
        return [tool.name for tool in tools]

    @staticmethod
    def get_tool_summaries() -> dict:
        """
        Get summary information about all tools

        Returns:
            Dict with tool names, descriptions, and categories
        """
        summaries = {
            "drift_analysis": [
                {
                    "name": tool.name,
                    "description": tool.description.strip(),
                }
                for tool in get_drift_tools()
            ],
            "cache_management": [
                {
                    "name": tool.name,
                    "description": tool.description.strip(),
                }
                for tool in get_cache_tools()
            ],
            "metrics_retrieval": [
                {
                    "name": tool.name,
                    "description": tool.description.strip(),
                }
                for tool in get_metrics_tools()
            ],
            "threshold_management": [
                {
                    "name": tool.name,
                    "description": tool.description.strip(),
                }
                for tool in get_threshold_tools()
            ],
            "index_operations": [
                {
                    "name": tool.name,
                    "description": tool.description.strip(),
                }
                for tool in get_index_tools()
            ],
        }

        return summaries


# Convenience function for LangGraph workflows
def get_agent_tools() -> List[BaseTool]:
    """
    Convenience function to get all tools for agent use

    This is the primary function LangGraph workflows should call
    """
    return ToolRegistry.get_all_tools()


# Export for easy imports
__all__ = [
    "ToolRegistry",
    "get_agent_tools",
]
