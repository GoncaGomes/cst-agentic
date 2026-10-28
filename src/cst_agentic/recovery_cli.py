"""Application-owned local human reconciliation; no provider or transport access."""

from .recovery import Incident, RecoveryError, RecoveryStore


def _report(record: Incident) -> None:
    print(f"Incident {record.id}: {record.state}; operation={record.operation}")
    print(f"Task: {record.task_id}; instance: {record.instance_id or 'unknown'}")
    print(f"Affected project: {record.project.path if record.project else 'unknown scope'}")
    print(
        f"Human findings: {len(record.findings)}; effects resolved={record.effects_resolved}; "
        f"activity resolved={record.activity_resolved}; "
        f"previous instance closed={record.instance_closed}"
    )


def _finding(prompt: str) -> bool:
    while True:
        answer = input(prompt + " [yes/no]: ").strip().lower()
        if answer in {"yes", "no"}:
            return answer == "yes"
        print("Enter yes or no based on your local inspection; unknown means no.")


def run_local_recovery(action: str, incident_id: str | None = None) -> int:
    """Hold the same exclusive lease, without constructing a Controller client."""
    with RecoveryStore().session() as store:
        print(
            "Local recovery only: no CST calls. Findings are human-provided, "
            "not independently verified. Closing CST or restarting Windows alone "
            "does not resolve uncertain effects."
        )
        records = store.incidents()
        if action == "status":
            for record in records:
                _report(record)
            if not records:
                print("No recorded incidents; this does not verify live CST or solver state.")
            return 0
        record = next((r for r in records if r.id == incident_id), None)
        if record is None:
            raise RecoveryError("Recovery record was not found.")
        if record.state in {"settled", "reconciled"}:
            raise RecoveryError("Recovery record is already finalized.")
        _report(record)
        print(
            "Inspect affected work locally. Address partial effects, stop/resolve continuing "
            "solver activity, and close the previous CST instance. Unknown findings stay pending."
        )
        try:
            project = _finding("Have you identified all affected work, including unknown scope?")
            effects = _finding("Have you inspected and addressed the operation's partial effects?")
            activity = _finding("Have you resolved all continuing solver/activity from this work?")
            closed = _finding("Have you closed the previous CST instance?")
        except (EOFError, KeyboardInterrupt):
            print("Reconciliation interrupted; no new findings recorded; incident remains pending.")
            return 1
        store.reconcile(
            record.id,
            project_confirmed=project,
            effects_resolved=effects,
            activity_resolved=activity,
            instance_closed=closed,
        )
        if store.incidents(unresolved_only=True):
            print("Findings recorded; unresolved incidents still block all new CST work.")
            return 1
        print(
            "Findings recorded. Start a fresh Controller session and explicit new task with CST "
            "initially closed; ordinary live-target prerequisites still apply. No work is replayed."
        )
        return 0
