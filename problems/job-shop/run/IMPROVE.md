# Job shop scheduling

Each job is a fixed sequence of operations, each on a named machine for a
known time. An operation cannot start until the one before it in its job has
finished and its machine is free. Finish every job as early as possible: the
score is the makespan, the moment the last operation ends.

`priority(ops, now)` is the whole decision. Whenever a machine could start
work, you are handed every operation that could start on it at this moment,
and you return one score per operation. The highest starts. You never see an
operation that could not start now, so you do not have to check.

Each `Op` carries:

- `duration` -- how long this operation takes
- `work_remaining` -- total time left in this job, this operation included
- `ops_remaining` -- how many operations are left in this job
- `job_work`, `job_ops` -- the job's totals, for normalising
- `ready_at` -- when this operation became able to start
- `machine`, `job` -- which machine, which job

The seed is most-work-remaining. It is a strong standard rule and it is
beatable. Its known weakness is that it looks only at the job in front of it:
it will start a long operation on a machine that several other jobs are
queuing for, and everything behind it waits.

Things that are true and worth using:

- A makespan cannot beat the critical path, so the job with the most work
  left is usually the one to hurry -- but only when it is not blocking others.
- `now - ready_at` is how long an operation has already waited.
- Dividing by `job_work` or `job_ops` turns any of these into a ratio, which
  compares jobs of different sizes more fairly than a raw total.

Constraints:

- Keep the whole function, including the `def priority(ops, now)` line. Only
  the marked region inside it is yours.
- Return exactly one number per operation, in the order given, and no NaN.
- No randomness. The same input must give the same output every time; the
  scorer runs the training set twice and rejects a rule whose two scores
  differ.
- Standard library only, and no I/O. You are scored on instances you cannot
  see.
