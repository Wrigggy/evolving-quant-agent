# AP-3 r4 AppleDouble setup failure

Date: 2026-08-20

AP-3 r4 started from a new answer-blind Quant-H0 T26 Worker. The H0 attempt
completed 27 model requests, scored 13/17 with reward zero, and cost
$0.121280528. Evolver round one then ran for 20 model requests, wrote a
candidate snapshot, and cost $0.116974576.

The coordinator failed before it could write a valid round-one `LIVE-RESULT`,
append the candidate to runtime history, launch the selected Worker probe, or
make a second Evolver decision. The observed exception was
`worker snapshot contains non-UTF8 source: ._agent.yaml`.

`._agent.yaml` was not authored by the Evolver. It was a macOS AppleDouble
sidecar introduced when the incremental source archive preserved extended
metadata during transfer to Linux. Similar sidecars were present beside the
synchronized Python, prompt, YAML, and test files. They were removed only from
the remote deploy; the r4 run directory and failure evidence were retained.
The Quant-H0 worker tree then passed the same history-tree preflight before r5
was launched. Future archive syncs disable macOS metadata rather than adding a
new runtime defense.

The retained r4 cost is $0.238255104 for 47 completed model requests. The H0
13/17 observation is valid, but r4 as a campaign is setup-invalid. It cannot
support a claim about candidate admission, runtime-experience update, final
Worker performance, or autonomous H0 improvement.

Evidence is mirrored at
`results/bc-mirror/qce-t26-ap3-20260820-r4/`; the compact record is
`data/quantcodeeval/AP3_R4_SETUP_FAILURE_RESULT.json`.
