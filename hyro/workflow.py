from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from hyro.activities import build_queries, evaluate_candidates, fetch_provider, normalize_results, set_run_state


@workflow.defn
class ResearchCandidatesWorkflow:
    @workflow.run
    async def run(self, run_id: str):
        short = {"start_to_close_timeout": timedelta(seconds=30), "retry_policy": RetryPolicy(maximum_attempts=3)}
        long = {"start_to_close_timeout": timedelta(minutes=10), "heartbeat_timeout": timedelta(seconds=30), "retry_policy": RetryPolicy(maximum_attempts=3)}
        try:
            await workflow.execute_activity(set_run_state, args=[run_id, "running", None], **short)
            queries = await workflow.execute_activity(build_queries, run_id, **short)
            for source, query in queries.items():
                await workflow.execute_activity(fetch_provider, args=[run_id, source, query], **long)
            await workflow.execute_activity(normalize_results, run_id, **short)
            await workflow.execute_activity(evaluate_candidates, run_id, **short)
            await workflow.execute_activity(set_run_state, args=[run_id, "completed", None], **short)
        except Exception as exc:
            await workflow.execute_activity(set_run_state, args=[run_id, "failed", str(exc)[:1000]], **short)
            raise
