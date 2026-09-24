"""Representative static LangGraph construction patterns."""


class StateGraph:
    """Small stand-in that keeps this static example importable."""

    def add_edge(self, source: str, target: str) -> None:
        del source, target

    def add_conditional_edges(self, source: str, route: object, path_map: dict[str, str]) -> None:
        del source, route, path_map


def route_refund() -> str:
    return "automatic"


graph = StateGraph()

graph.add_edge("lookup_payment", "issue_refund")
graph.add_conditional_edges(
    "issue_refund",
    route_refund,
    {
        "automatic": "process_refund",
        "review": "human_review",
        "fallback": "manual_review_fallback",
    },
)
