import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from agents.graph import AnalysisState, graph
from api.deps import get_current_user
from api.rate_limit import analytics_limiter

router = APIRouter(tags=["analytics"])


class AnalyticsRequest(BaseModel):
    question: str


class AnalyticsResponse(BaseModel):
    final_response: str
    sql_query: str
    query_results: list[dict]
    data_found: bool


@router.post("/", response_model=AnalyticsResponse)
def run_analytics(body: AnalyticsRequest, _user: dict = Depends(get_current_user)):
    analytics_limiter.check(f"analytics:{_user['sub']}")
    initial_state: AnalysisState = {
        "question": body.question,
        "schema_context": "",
        "sql_query": "",
        "sql_valid": False,
        "analytics_valid": False,
        "validation_error": "",
        "query_results": [],
        "data_found": False,
        "analysis": "",
        "final_response": "",
        "retry_count_sql": 0,
        "retry_count_analysis": 0,
    }
    try:
        result = graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # query_results may contain non-serialisable types (e.g. date objects) —
    # round-trip through JSON to normalise them to strings
    raw_results = result.get("query_results", [])
    try:
        safe_results = json.loads(json.dumps(raw_results, default=str))
    except Exception:
        safe_results = []

    return AnalyticsResponse(
        final_response=result.get("final_response", ""),
        sql_query=result.get("sql_query", ""),
        query_results=safe_results,
        data_found=result.get("data_found", False),
    )
