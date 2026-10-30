"""Inspect Task definitions. Trusted side: never model-visible."""
import os

from inspect_ai import Task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.solver import generate, solver, system_message, use_tools
from inspect_ai.tool import bash, python

from .collect import (EXECUTION_KEY, bind_run, collect_on_cleanup, collect_outputs_scorer,
                      run_binding, sample_dir)
from .tools import render_document, view_image

HERE = os.path.dirname(os.path.abspath(__file__))
COMPOSE = os.path.join(HERE, "compose.yaml")
with open(os.path.join(HERE, "system_prompt_draft.txt"), encoding="utf-8") as _f:
    SYSTEM_PROMPT_DRAFT = _f.read().strip()


@solver
def bind_execution(runs_root: str, run_label: str | None):
    async def solve(state, generate):
        bind_run(sample_dir(runs_root, state), run_binding(state), run_label, "solver")
        state.store.set(EXECUTION_KEY, {"solver_finished": False})
        return state
    return solve


@solver
def execution_finished():
    async def solve(state, generate):
        progress = dict(state.store.get(EXECUTION_KEY, {}))
        progress["solver_finished"] = True
        state.store.set(EXECUTION_KEY, progress)
        return state
    return solve


def make_task(samples: list[Sample], runs_root: str, run_id: str | None = None, tool_timeout: int = 600,
              time_limit: int | None = None, system_prompt: str = SYSTEM_PROMPT_DRAFT, name: str = "gdpval",
              _simulate_read_failure: set[str] | None = None) -> tuple[Task, str]:
    """Return (task, runs_root); no execution identity or directory is created here.

    Each actual execution collects into runs_root/TaskState.uuid. Legacy run_id is only a
    launcher label in run.json; it cannot select/reuse a collection directory. Binding occurs
    at the first trusted TaskState, with cleanup as fallback if earlier stages never ran.
    """
    task = Task(
        name=name,
        dataset=MemoryDataset(samples),
        solver=[
            bind_execution(runs_root, run_id),
            system_message(system_prompt),
            use_tools([bash(timeout=tool_timeout), python(timeout=tool_timeout), view_image(), render_document()]),
            generate(tool_calls="loop"),
            execution_finished(),
        ],
        scorer=collect_outputs_scorer(runs_root, run_id, _simulate_read_failure=_simulate_read_failure),
        cleanup=collect_on_cleanup(runs_root, run_id),
        sandbox=("docker", COMPOSE),
        time_limit=time_limit,
    )
    return task, runs_root
