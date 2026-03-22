# cron-tools Plugin — Design Spec

**Date:** 2026-03-22
**Status:** Approved

---

## Goal

Add a `cron-tools` plugin to `ayder-plugins` that lets the LLM schedule recurring jobs (shell commands and LLM prompts) with project-local persistence. Jobs survive ayder restarts and fire reliably inside an in-process scheduler thread.

---

## Architecture

### Plugin location

```
ayder-plugins/cron-tools/
├── plugin.toml
├── cron_definitions.py   # TOOL_DEFINITIONS tuple
├── cron_scheduler.py     # BackgroundScheduler singleton + job runners
```

No changes to `ayder-cli` core.

### ToolDefinition format

`cron_definitions.py` follows the exact same `ToolDefinition` pattern used by existing plugins (`venv-tools`, `mcp-tool`). Refer to those as implementation reference. Key fields: `name`, `description`, `func_ref` (e.g. `"cron_scheduler:schedule_job"`), `parameters` (JSON Schema object), `permission`, `safe_mode_blocked`.

The registry injects `project_ctx` transparently into any tool function whose signature includes that parameter (signature inspection, same as all other plugins). `project_ctx` is never included in the LLM-facing JSON Schema.

### Scheduler

**Library:** APScheduler v3.x (`BackgroundScheduler` + `SQLAlchemyJobStore`).

**Lifecycle:** Lazy start — the scheduler is created and started on the first tool call in a given process. An `atexit` handler shuts it down cleanly. Each ayder instance runs its own `BackgroundScheduler` against its own project's DB.

**Persistence:** SQLite at `.ayder/cron/jobs.db` inside the active project root. `project_ctx.project_root` provides the path. The directory is created on first use.

**Multiple ayder instances:** Each project's ayder process owns its own DB and scheduler. Instances do not share state.

**Missed-run behaviour:** Jobs use `coalesce=True` and `misfire_grace_time=60`. This means: if ayder was offline and missed several scheduled runs, the job fires exactly once when ayder restarts (not once per missed run). If the scheduler comes back more than 60 seconds after the missed window, the run is skipped entirely. A job scheduled for 9 am that was missed because the machine was off fires once at the next scheduled time, not retroactively.

---

## Job Types (v1)

| Type | Execution | Notes |
|---|---|---|
| `shell` | `subprocess.Popen(shlex.split(command), cwd=project_root)` | Non-blocking; stdout/stderr appended to `.ayder/cron/logs/<name>.log` |
| `llm_prompt` | `subprocess.Popen(["ayder", "--headless", "--prompt", prompt], cwd=project_root)` | Spawns a new ayder process; no AgentRegistry injection needed |

`tool_call` type is deferred to v2 — LLM-prompt jobs cover the same ground.

Spawn errors (e.g. `ayder` binary not on PATH) are caught at fire time, written to the job's log file, and do not crash the scheduler.

**Log concurrency:** Each job has its own log file (keyed by name), so separate jobs do not interleave. If a recurring job fires simultaneously with a `run_job_now`-triggered instance of the same job, writes may interleave; this is acceptable for v1 (log files are diagnostic, not transactional).

**Security note:** `command_or_prompt` is not sanitised — the LLM is the trusted caller. An empty value is rejected at schedule time; all other content is passed through as-is.

---

## Tools

All four functions receive `project_ctx` via registry injection (not exposed in the LLM schema).

### `schedule_job`

Create or replace a recurring job.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Unique job slug — used as the APScheduler job ID |
| `cron` | string | yes | 5-field cron expression (`"0 9 * * 1"` = Monday 9 am) |
| `type` | `"shell"` \| `"llm_prompt"` | yes | Job execution type |
| `command_or_prompt` | string | yes | Shell command or LLM prompt text (must be non-empty) |

Returns: `ToolSuccess("Scheduled job '<name>'. Next run: <ISO8601 datetime>")`, or `ToolError` for invalid cron expression, unknown `type`, or empty `command_or_prompt`.

Behaviour: `replace_existing=True` — calling again with the same `name` updates the job.

Permission: `x`. Safe-mode blocked: **yes** (spawns processes).

---

### `list_jobs`

List all scheduled jobs for the current project.

No parameters (other than injected `project_ctx`).

Returns: `ToolSuccess(string)` — a markdown table with columns `name`, `type`, `cron`, `next_run` (ISO8601). Example:

```
| name       | type         | cron       | next_run                  |
|------------|--------------|------------|---------------------------|
| daily-sync | shell        | 0 9 * * *  | 2026-03-23T09:00:00+00:00 |
| weekly-rep | llm_prompt   | 0 10 * * 1 | 2026-03-25T10:00:00+00:00 |
```

If no jobs are scheduled, returns `ToolSuccess("No jobs scheduled.")`.

In v1 all jobs are active; there is no paused state.

Permission: `r`. Safe-mode blocked: no.

---

### `remove_job`

Delete a job. Only modifies the scheduler DB; does not spawn processes.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Job slug to remove |

Returns: `ToolSuccess("Removed job '<name>'")` or `ToolError("Job '<name>' not found")`.

Permission: `w`. Safe-mode blocked: **no**.

---

### `run_job_now`

Trigger a job immediately, outside its schedule. The recurring schedule is not affected. Execution is asynchronous — the subprocess starts in the background; the tool returns immediately.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Job slug to trigger |

Returns: `ToolSuccess("Job '<name>' triggered at <ISO8601 datetime>")` or `ToolError("Job '<name>' not found")`.

Implementation: adds a one-time `DateTrigger` job (with a unique temporary ID) using the same function and kwargs as the existing recurring job.

Permission: `x`. Safe-mode blocked: **yes** (spawns processes).

---

## Implementation Details

### `cron_scheduler.py`

**Scheduler singleton:**

```python
_scheduler: BackgroundScheduler | None = None

def get_scheduler(project_root: Path) -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        db_path = project_root / ".ayder" / "cron" / "jobs.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        (project_root / ".ayder" / "cron" / "logs").mkdir(parents=True, exist_ok=True)
        jobstore = SQLAlchemyJobStore(url=f"sqlite:///{db_path}")
        _scheduler = BackgroundScheduler(
            jobstores={"default": jobstore},
            job_defaults={"coalesce": True, "misfire_grace_time": 60},
        )
        _scheduler.start()
        atexit.register(_scheduler.shutdown)
    return _scheduler
```

**Job runner functions** (module-level, picklable by APScheduler):

```python
def _run_shell(command: str, cwd: str, log_path: str) -> None:
    try:
        with open(log_path, "a") as log_file:
            subprocess.Popen(
                shlex.split(command), cwd=cwd,
                stdout=log_file, stderr=log_file,
                close_fds=True,
            )
        # The `with` block closes the parent's file object after Popen returns.
        # Popen internally calls dup2() to attach the file to the child's fd 1 and fd 2
        # before exec. close_fds=True closes non-standard FDs in the child, but fd 1 and
        # fd 2 (stdout/stderr) are preserved. The child writes uninterrupted.
    except Exception as exc:
        with open(log_path, "a") as f:
            f.write(f"[cron-tools] spawn error: {exc}\n")

def _run_llm_prompt(prompt: str, cwd: str, log_path: str) -> None:
    try:
        with open(log_path, "a") as log_file:
            subprocess.Popen(
                ["ayder", "--headless", "--prompt", prompt],
                cwd=cwd, stdout=log_file, stderr=log_file,
                close_fds=True,
            )
    except Exception as exc:
        with open(log_path, "a") as f:
            f.write(f"[cron-tools] spawn error: {exc}\n")
```

**`schedule_job` core logic:**

```python
def schedule_job(project_ctx, name, cron, type, command_or_prompt):
    if type not in ("shell", "llm_prompt"):
        return ToolError(f"Unknown job type '{type}'. Valid: shell, llm_prompt")
    if not command_or_prompt or not command_or_prompt.strip():
        return ToolError("command_or_prompt must not be empty")

    scheduler = get_scheduler(project_ctx.project_root)
    try:
        trigger = CronTrigger.from_crontab(cron)
    except ValueError as exc:
        return ToolError(f"Invalid cron expression: {exc}")

    log_path = str(
        project_ctx.project_root / ".ayder" / "cron" / "logs" / f"{name}.log"
    )
    if type == "shell":
        func, kwargs = _run_shell, {"command": command_or_prompt, "cwd": str(project_ctx.project_root), "log_path": log_path}
    else:
        func, kwargs = _run_llm_prompt, {"prompt": command_or_prompt, "cwd": str(project_ctx.project_root), "log_path": log_path}

    job = scheduler.add_job(func, trigger, id=name, name=name, kwargs=kwargs, replace_existing=True)
    return ToolSuccess(f"Scheduled job '{name}'. Next run: {job.next_run_time.isoformat()}")
```

**`list_jobs` core logic:**

```python
def list_jobs(project_ctx):
    scheduler = get_scheduler(project_ctx.project_root)
    jobs = scheduler.get_jobs()
    if not jobs:
        return ToolSuccess("No jobs scheduled.")

    rows = ["| name | type | cron | next_run |", "|------|------|------|----------|"]
    for job in jobs:
        job_type = "shell" if job.func == _run_shell else "llm_prompt"
        cron_str = str(job.trigger)  # APScheduler CronTrigger.__str__ returns human-readable cron
        next_run = job.next_run_time.isoformat() if job.next_run_time else "paused"
        rows.append(f"| {job.id} | {job_type} | {cron_str} | {next_run} |")
    return ToolSuccess("\n".join(rows))
```

**`remove_job` core logic:**

```python
def remove_job(project_ctx, name):
    scheduler = get_scheduler(project_ctx.project_root)
    if scheduler.get_job(name) is None:
        return ToolError(f"Job '{name}' not found")
    scheduler.remove_job(name)
    return ToolSuccess(f"Removed job '{name}'")
```

**`run_job_now` core logic:**

```python
def run_job_now(project_ctx, name):
    scheduler = get_scheduler(project_ctx.project_root)
    job = scheduler.get_job(name)
    if job is None:
        return ToolError(f"Job '{name}' not found")
    now = datetime.now(timezone.utc)
    scheduler.add_job(
        job.func, "date",
        run_date=now,
        kwargs=job.kwargs,
        id=f"{name}_now_{int(now.timestamp())}",
    )
    return ToolSuccess(f"Job '{name}' triggered at {now.isoformat()}")
```

### Job payload pickling

APScheduler v3 pickles job payloads (function reference + kwargs) to SQLite. All kwargs are plain Python strings, which pickle safely. Runner functions are module-level, so their references are picklable.

### `plugin.toml`

```toml
[plugin]
name        = "cron-tools"
version     = "0.1.0"
api_version = 1
description = "Cron scheduler — schedule shell commands and LLM prompts as recurring jobs"
author      = "ayder"

[dependencies]
apscheduler = ">=3.10,<4.0"
sqlalchemy   = ">=1.4"

[tools]
definitions = "cron_definitions.py"
```

---

## Error Handling

| Situation | Behaviour |
|---|---|
| Invalid cron expression | `CronTrigger.from_crontab` raises `ValueError`; return `ToolError` |
| Unknown `type` value | Validated before APScheduler call; return `ToolError` |
| Empty `command_or_prompt` | Validated at schedule time; return `ToolError` |
| Job not found (`remove_job` / `run_job_now`) | `scheduler.get_job()` returns `None`; return `ToolError` |
| Subprocess spawn failure at fire time | Exception caught in runner function, written to `<name>.log`; scheduler continues |
| Log/DB directory missing | Both created in `get_scheduler()` at init |

---

## Out of Scope (v1)

- `tool_call` job type — deferred to v2
- Job pause/resume — deferred to v2
- Global (cross-project) persistence — project-local only by design
- Validation that `ayder` binary exists at schedule time — caught at fire time and logged
- Shell command sanitisation — LLM is the trusted caller

---

## Testing Strategy

- Unit-test `get_scheduler()` with a temp directory — verify DB file and logs dir are created, scheduler is running.
- Unit-test `schedule_job` with a real temp-dir scheduler — verify `add_job` is called with correct trigger, correct func (`_run_shell` vs `_run_llm_prompt`), and correct kwargs key (`command` vs `prompt`).
- Unit-test `replace_existing=True` — call `schedule_job` twice with the same name; verify only one job exists.
- Unit-test invalid cron expression returns `ToolError`.
- Unit-test unknown `type` value returns `ToolError`.
- Unit-test empty `command_or_prompt` returns `ToolError`.
- Unit-test `remove_job` with non-existent name returns `ToolError`.
- Unit-test `list_jobs` returns `ToolSuccess` with markdown table containing job name and ISO8601 `next_run`.
- Unit-test `list_jobs` with no jobs returns `ToolSuccess("No jobs scheduled.")`.
- Unit-test `run_job_now` adds a one-time date-triggered job without removing the recurring job.
- Integration test (tagged `slow`): schedule a `shell` job with `* * * * *`, wait up to 65 s for fire, verify `.ayder/cron/logs/<name>.log` is created and non-empty.
