"""AI Agent modules for the briefing system."""

# 只导入存在的模块，避免导入错误
from src.agents.quick_filter_agent import QuickFilterAgent

try:
    from src.agents.proactive_agent import ProactiveAgent
except ImportError:
    ProactiveAgent = None

# 以下模块可能尚未实现，使用条件导入避免错误
try:
    from src.agents.state import BriefingAgentState
except ImportError:
    BriefingAgentState = None

try:
    from src.agents.triage_agent import TriageAgent
except ImportError:
    TriageAgent = None

try:
    from src.agents.cluster_agent import ClusterAgent
except ImportError:
    ClusterAgent = None

try:
    from src.agents.differential_agent import DifferentialAgent
except ImportError:
    DifferentialAgent = None

try:
    from src.agents.critique_agent import CritiqueAgent
except ImportError:
    CritiqueAgent = None

try:
    from src.agents.briefing_graph import build_briefing_graph
except ImportError:
    build_briefing_graph = None

__all__ = [
    "QuickFilterAgent",
    "ProactiveAgent",
    "BriefingAgentState",
    "TriageAgent",
    "ClusterAgent",
    "DifferentialAgent",
    "CritiqueAgent",
    "build_briefing_graph",
]

