"""
LangGraph workflow that orchestrates the entire AI digest pipeline.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict, Protocol

from langgraph.graph import StateGraph, END


class BriefingState(TypedDict, total=False):
    """Shared state for the LangGraph pipeline."""

    params: Dict[str, Any]
    raw_items: List[Any]
    filtered_items: List[Any]  # 快速初评后的条目
    filter_stats: Dict[str, Any]  # 快速初评统计信息
    processed_items: List[Any]
    leaderboard: Dict[str, Any]
    market_insights: List[Dict[str, Any]]
    action_items: Dict[str, List[Dict[str, Any]]]
    learning_results: Dict[str, Any]
    report_path: Optional[str]
    errors: List[str]


class BriefingServices(Protocol):
    """Interface expected from WeeklyReportGenerator for LangGraph nodes."""

    def _collect_data(self, days_back: int) -> List[Any]: ...

    def _dump_collected_items(self, items: List[Any], days_back: int, output_dir: Optional[str]) -> None: ...

    def _collect_leaderboard(self) -> Dict[str, Any]: ...

    def _collect_market_insights(self) -> List[Dict[str, Any]]: ...

    def _process_with_ai(self, items: List[Any]) -> List[Any]: ...

    def _generate_action_items(self, processed_items: List[Any]) -> Dict[str, List[Dict[str, Any]]]: ...

    def _run_learning_cycle(self, processed_items: List[Any]) -> Dict[str, Any]: ...

    def _generate_report(
        self,
        processed_items: List[Any],
        action_items: Dict[str, List[Dict[str, Any]]],
        leaderboard_info: Dict[str, Any],
        market_insights: List[Dict[str, Any]],
        output_dir: Optional[str] = None,
        learning_results: Optional[Dict[str, Any]] = None,
    ) -> str: ...

    def _send_email_if_configured(self, report_path: Optional[str]) -> None: ...


def compile_briefing_graph(services: BriefingServices) -> Any:
    """Compile the LangGraph graph that drives the entire workflow."""

    graph = StateGraph(BriefingState)

    def _append_error(state: BriefingState, message: str) -> List[str]:
        errors = list(state.get("errors", []))
        errors.append(message)
        return errors

    def collect_node(state: BriefingState) -> BriefingState:
        params = state.get("params", {})
        days_back = int(params.get("days_back", 3) or 3)
        output_dir = params.get("output_dir")

        try:
            raw_items = services._collect_data(days_back)
            services._dump_collected_items(raw_items, days_back, output_dir)
            leaderboard = services._collect_leaderboard()
            market_insights = services._collect_market_insights()

            updates: BriefingState = {
                "raw_items": raw_items,
                "leaderboard": leaderboard or {"data": [], "update_time": ""},
                "market_insights": market_insights or [],
            }
            if not raw_items:
                updates["errors"] = _append_error(state, "数据采集阶段未获取到有效内容。")
            return updates
        except Exception as exc:  # pragma: no cover - defensive logging
            return {
                "raw_items": [],
                "leaderboard": {"data": [], "update_time": ""},
                "market_insights": [],
                "errors": _append_error(state, f"数据采集失败: {exc}"),
            }

    def quick_filter_node(state: BriefingState) -> BriefingState:
        raw_items = state.get("raw_items") or []
        if not raw_items:
            return {"filtered_items": []}
        try:
            filtered, stats = services._quick_filter_items(raw_items)
            updates: BriefingState = {"filtered_items": filtered or []}
            if stats:
                updates["filter_stats"] = stats
            if not filtered:
                updates["errors"] = _append_error(state, "快速初评后没有保留条目，后续流程可能跳过。")
            return updates
        except Exception as exc:  # pragma: no cover - defensive fallback
            return {
                "filtered_items": raw_items,
                "errors": _append_error(state, f"快速初评失败，使用原始数据: {exc}"),
            }

    def process_node(state: BriefingState) -> BriefingState:
        filtered = state.get("filtered_items")
        candidates = filtered if filtered is not None else state.get("raw_items") or []
        if not candidates:
            return {
                "processed_items": [],
                "errors": _append_error(state, "处理阶段没有可用的数据，跳过后续流程。"),
            }
        try:
            processed = services._process_with_ai(candidates)
            updates: BriefingState = {"processed_items": processed or []}
            if not processed:
                updates["errors"] = _append_error(state, "AI 处理后无有效条目，后续步骤可能跳过。")
            return updates
        except Exception as exc:  # pragma: no cover
            return {
                "processed_items": [],
                "errors": _append_error(state, f"AI 处理失败: {exc}"),
            }

    def action_node(state: BriefingState) -> BriefingState:
        processed = state.get("processed_items") or []
        if not processed:
            return {
                "action_items": {"must_do": [], "nice_to_have": []},
                "errors": _append_error(state, "无法生成行动清单：缺少处理后的条目。"),
            }
        try:
            action_items = services._generate_action_items(processed)
            return {"action_items": action_items or {"must_do": [], "nice_to_have": []}}
        except Exception as exc:  # pragma: no cover
            return {
                "action_items": {"must_do": [], "nice_to_have": []},
                "errors": _append_error(state, f"生成行动清单失败: {exc}"),
            }

    def learning_node(state: BriefingState) -> BriefingState:
        processed = state.get("processed_items") or []
        try:
            learning_results = services._run_learning_cycle(processed)
            return {"learning_results": learning_results or {}}
        except Exception as exc:  # pragma: no cover
            return {
                "learning_results": {},
                "errors": _append_error(state, f"自我学习循环失败: {exc}"),
            }

    def report_node(state: BriefingState) -> BriefingState:
        params = state.get("params", {})
        output_dir = params.get("output_dir")
        processed = state.get("processed_items") or []
        action_items = state.get("action_items") or {"must_do": [], "nice_to_have": []}
        leaderboard = state.get("leaderboard") or {"data": [], "update_time": ""}
        market_insights = state.get("market_insights") or []
        learning_results = state.get("learning_results") or {}

        if not processed:
            return {
                "report_path": None,
                "errors": _append_error(state, "没有可用的处理数据，无法生成周报。"),
            }
        try:
            report_path = services._generate_report(
                processed_items=processed,
                action_items=action_items,
                leaderboard_info=leaderboard,
                market_insights=market_insights,
                output_dir=output_dir,
                learning_results=learning_results,
            )
            return {"report_path": report_path}
        except Exception as exc:  # pragma: no cover
            return {
                "report_path": None,
                "errors": _append_error(state, f"生成周报失败: {exc}"),
            }

    def email_node(state: BriefingState) -> BriefingState:
        report_path = state.get("report_path")
        try:
            services._send_email_if_configured(report_path)
        except Exception as exc:  # pragma: no cover
            return {"errors": _append_error(state, f"发送邮件失败: {exc}")}
        return {}

    graph.add_node("collect", collect_node)
    graph.add_node("quick_filter", quick_filter_node)
    graph.add_node("process", process_node)
    graph.add_node("action", action_node)
    graph.add_node("learning", learning_node)
    graph.add_node("report", report_node)
    graph.add_node("email", email_node)

    graph.set_entry_point("collect")
    graph.add_edge("collect", "quick_filter")
    graph.add_edge("quick_filter", "process")

    def decide_action(state: BriefingState) -> str:
        params = state.get("params", {})
        learning_only = bool(params.get("learning_only"))
        processed = state.get("processed_items") or []
        if learning_only or not processed:
            return "skip_action"
        return "run_action"

    graph.add_conditional_edges(
        "process",
        decide_action,
        {
            "skip_action": "learning",
            "run_action": "action",
        },
    )

    graph.add_edge("action", "learning")

    def decide_report(state: BriefingState) -> str:
        params = state.get("params", {})
        learning_only = bool(params.get("learning_only"))
        if learning_only:
            return "skip_report"
        return "generate_report"

    graph.add_conditional_edges(
        "learning",
        decide_report,
        {
            "skip_report": END,
            "generate_report": "report",
        },
    )

    graph.add_edge("report", "email")
    graph.add_edge("email", END)

    return graph.compile()


