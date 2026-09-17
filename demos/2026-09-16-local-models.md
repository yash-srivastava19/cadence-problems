# 2026-09-16 — a local model, and where the markers sit

Two runs on this machine's own compute, no key, no quota, $0.00.
`20260916-165725-cb1725` and `20260916-170103-1b7370`, 10 trials each,
`arms/bin-packing-local.cadence`. Both scored nothing.

## The result

Twenty trials, twenty crashes, the same one every time:

    IndentationError: unexpected indent   at heuristic.py line 14

Both runs finished cleanly and reported the **baseline** as best rather than a
broken child, which is `_winner`'s seed fallback working as written.

## Why, and it is not what it looks like

The raw response, verbatim:

    ```python
        scores = []
        for bin_capacity in bins:
            scores.append(float(bin_capacity))
        return scores
    ```

That is best fit, correctly reimplemented, properly indented. The model can do
the task. What it returned is the function's **body**; what the markers wrap is
the **whole function**, `def` line included. Splice a body where a function
belongs and you get an indented block with no `def` above it.

The `region` template says "Reply with the replacement for the marked section
only ... Do not include the marker lines themselves." For a 4B model, "the
marked section" reads as the body.

**Marker placement is part of the problem statement.** Wrapping the whole
function works only for a model that infers the contract. Wrapping the body
would have made this model's output correct as-is. circle-packing gets away
with the former because gemini-3.6-flash fills the gap in silently.

## What did not fix it

Adding an explicit constraint to `IMPROVE.md` -- "Keep the whole function,
including the `def priority(item, bins)` line" -- changed nothing. Ten more
crashes, identical. `tokens_in` rose 7259 -> 7549, so the line was in the
prompt and was ignored. Reverted, because editing `IMPROVE.md` changes the
prompt digest and would refuse the resume of `20260916-095047-a3b334`.

## qwen3:4b cannot be used at all, for a separate reason

Not capability. It never answers. Through ollama's OpenAI-dialect `/v1`
endpoint, which is the one cadence calls, qwen3 puts everything in a
`reasoning` field and leaves `content` empty:

    prompt: "Return only a Python one-liner ..."
    finish_reason: length | reasoning 5028 chars | content 0 chars

`/no_think` in the prompt does not help. Through ollama's **native**
`/api/chat` with `think: false`, thinking drops to 0 and content fills. So the
gap is that cadence's ollama backend speaks `/v1` and cannot send `think`.

Worth fixing: reasoning models are most of what is worth running locally, and
cadence can currently drive none of them.

## Throughput, measured

    qwen3:4b          7.7 tok/s generation, CPU, Intel Iris Xe, 15GB RAM

    circle packing    6109 tokens out per call -> ~13 min/call   unusable
    bin packing        423 tokens out per call -> ~0.9 min/call  practical

Bin packing is the local-friendly problem: small prompts, small answers, 0.2s
scoring. Roughly a trial a minute, so an overnight run is hundreds of trials
against gemini's twenty a day.

## Next, in order

1. Move the markers inside `priority` so the region is the body. Cheapest test
   of the diagnosis, and it costs nothing to run.
2. Send `think: false` from the ollama backend, so reasoning models work.
3. Then the control arm: IID random sampling is free locally, and it is the
   hole every published number in this repo inherits.
