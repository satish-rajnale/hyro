import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from hyro.activities import build_queries, evaluate_candidates, fetch_provider, normalize_results, set_run_state
from hyro.config import settings
from hyro.startup import migrate_and_seed
from hyro.workflow import ResearchCandidatesWorkflow


async def main():
    migrate_and_seed()
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    worker = Worker(client, task_queue=settings.temporal_task_queue, workflows=[ResearchCandidatesWorkflow], activities=[set_run_state, build_queries, fetch_provider, normalize_results, evaluate_candidates])
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
