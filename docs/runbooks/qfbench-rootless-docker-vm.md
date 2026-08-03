# QFBench Rootless Docker VM Runbook

This runbook deploys a committed rootless-backend branch to the shared `bc` host and runs staged QFBench full-harness experiments. Rootless Docker is the default backend; E2B is an explicit fallback. The current gate permits the five-task one-iteration protocol only. Keep local Git as the source of truth and use the VM as a trusted coordinator plus Linux/rootless-Docker execution node.

## Safety Boundaries

- Never copy the repository recursively, transfer `.env`, or place a provider token in Git, a Docker environment variable, an image layer, a process argument, or a host bind mount.
- Never check out, copy, upload, or run official `solution/` blobs. The QFBench source is a blob-filtered bare repository; the materializer fetches only public inputs and verifier tests.
- Keep official tests only under `~/qea/runtime/trusted-verifier/`, mode `700`; workers receive only the separate public root.
- Use only `unix:///run/user/1013/docker.sock`. `/var/run/docker.sock`, privileged containers, host networking, and host mounts are forbidden.
- Never run `docker system prune`, wildcard cleanup, or label-wide deletion. Record and remove exact QEA container/network IDs only.
- Do not merge this branch. Stop after the currently accepted rollout stage; do not start three iterations, 30 tasks, or 30×5 scoring until the newest decision's recovery and cost gates pass.

## 1. Verify the Route, SSH, Identity, and Capacity

On the local Mac, verify that the VPN owns only the intended route and that SSH agent forwarding is active:

```bash
route -n get 192.168.1.251
ssh-add -L
ssh -o BatchMode=yes bc 'printf "host="; hostname; printf "uid="; id -u; printf "user="; id -un'
ssh bc 'ssh -T -p 443 git@ssh.github.com'
```

Confirm the saved host key independently before unattended use. The expected login is `julius`, UID `1013`; the GitHub command may return GitHub's normal “authenticated, no shell access” message.

Collect a shared-host snapshot before every live stage:

```bash
ssh bc 'uptime; getconf _NPROCESSORS_ONLN; awk "/MemTotal|MemAvailable/ {print}" /proc/meminfo; df -h "$HOME"; ps -eo pid,user,%cpu,%mem,cmd --sort=-%cpu | head -15'
```

Stop if load, free memory, or disk headroom is materially worse than the recorded baseline.

## 2. Create the User-Owned Layout

Run on `bc` as `julius`; no `sudo` is used:

```bash
install -d -m 700 "$HOME/qea"
install -d -m 700 "$HOME/qea/git" "$HOME/qea/worktrees" "$HOME/qea/runs"
install -d -m 700 "$HOME/qea/runtime"
install -d -m 700 "$HOME/qea/runtime/images"
install -d -m 700 "$HOME/qea/runtime/qfbench-public"
install -d -m 700 "$HOME/qea/runtime/trusted-verifier"
install -d -m 700 "$HOME/qea/runtime/secrets"
install -d -m 700 "$HOME/qea/runtime/replay"
install -d -m 700 "$HOME/qea/runtime/venvs"
```

Verify every directory is owned by UID 1013 and mode `700`:

```bash
stat -c '%a %u %n' "$HOME/qea" "$HOME/qea/git" "$HOME/qea/worktrees" "$HOME/qea/runtime" "$HOME/qea/runtime/secrets" "$HOME/qea/runs"
```

## 3. Push Only Committed Project Source

Initialize the bare destination once on `bc`:

```bash
git init --bare "$HOME/qea/git/evolving-quant-agent.git"
```

From the isolated local worktree, require a clean branch and push only that branch:

```bash
git status --short --branch
git rev-parse HEAD
git push bc:~/qea/git/evolving-quant-agent.git qfbench-selfhosted-vm-backend:refs/heads/qfbench-selfhosted-vm-backend
```

On `bc`, create the named worktree from the bare repository:

```bash
git --git-dir="$HOME/qea/git/evolving-quant-agent.git" worktree add "$HOME/qea/worktrees/qfbench-selfhosted-vm-backend" qfbench-selfhosted-vm-backend
git -C "$HOME/qea/worktrees/qfbench-selfhosted-vm-backend" status --short --branch
git -C "$HOME/qea/worktrees/qfbench-selfhosted-vm-backend" rev-parse HEAD
```

If a tested follow-up commit is required after the worktree exists, push a new,
non-checked-out branch and switch the clean execution worktree to it:

```bash
git push bc:~/qea/git/evolving-quant-agent.git HEAD:refs/heads/qfbench-rootless-reviewed-COMMIT
ssh bc 'git -C "$HOME/qea/worktrees/qfbench-selfhosted-vm-backend" status --short'
ssh bc 'git -C "$HOME/qea/worktrees/qfbench-selfhosted-vm-backend" switch qfbench-rootless-reviewed-COMMIT'
```

Replace `COMMIT` with a short immutable commit identity. Stop if the remote
worktree is dirty. Do not push over a checked-out ref, merge experiment branches,
use `rsync` for the repo, or create a second source of truth on the VM.

## 4. Create a Blob-Filtered QFBench Object Store

Create a bare, no-checkout source store. Tree metadata includes denied path identities, but only requested public/test blobs are fetched by the role materializer; no solution worktree is created:

```bash
git clone --bare --filter=blob:none ssh://git@ssh.github.com:443/QF-Bench/QuantitativeFinance-Bench.git "$HOME/qea/git/qfbench.git"
git --git-dir="$HOME/qea/git/qfbench.git" fetch --filter=blob:none origin 024921eb507fcc0c4ffe3e0a96802724be1ae84a
git --git-dir="$HOME/qea/git/qfbench.git" cat-file -t 024921eb507fcc0c4ffe3e0a96802724be1ae84a
```

The SSH/443 URL is the measured `bc-server` transport only; the pinned panel and materialized manifests retain the official HTTPS repository identity. Do not run `git checkout`, `git show ...:tasks/.../solution/...`, or an unfiltered clone.

## 5. Install and Pin Rootless Docker

The `uidmap` helpers and rootless setup tool are already system-installed. Verify them, then install the user daemon:

```bash
command -v newuidmap newgidmap dockerd-rootless-setuptool.sh dockerd-rootless.sh
stat -c '%a:%u:%n' /usr/bin/newuidmap /usr/bin/newgidmap
grep '^julius:' /etc/subuid /etc/subgid
dockerd-rootless-setuptool.sh install
systemctl --user status docker --no-pager
loginctl show-user julius -p Linger --value
```

In each experiment shell, set only the rootless endpoint:

```bash
export DOCKER_HOST=unix:///run/user/1013/docker.sock
test -S /run/user/1013/docker.sock
docker version
docker info --format '{{json .SecurityOptions}}'
```

Require `name=rootless`, a user-owned Docker data root, and the measured native `overlayfs`/containerd snapshotter on ext4. Do not add `julius` to a system Docker group.

Create a coordinator venv outside the worktree:

```bash
python3 -m venv "$HOME/qea/runtime/venvs/rootless"
"$HOME/qea/runtime/venvs/rootless/bin/python" -m pip install --upgrade pip
"$HOME/qea/runtime/venvs/rootless/bin/python" -m pip install -e "$HOME/qea/worktrees/qfbench-selfhosted-vm-backend"
```

Create the provider-token file interactively; do not paste it into shell history:

```bash
umask 077
read -r -s -p 'Model provider token: ' QEA_MODEL_TOKEN; printf '\n'
printf '%s\n' "$QEA_MODEL_TOKEN" > "$HOME/qea/runtime/secrets/model-token"
unset QEA_MODEL_TOKEN
chmod 600 "$HOME/qea/runtime/secrets/model-token"
stat -c '%a:%u:%F' "$HOME/qea/runtime/secrets/model-token"
```

## 6. Run the Read-Only Host Gate

Set the exact committed source identity; the checker performs no install, service start, secret write, or Docker mutation:

```bash
QEA_SOURCE_COMMIT=$(git -C "$HOME/qea/worktrees/qfbench-selfhosted-vm-backend" rev-parse HEAD)
"$HOME/qea/runtime/venvs/rootless/bin/python" "$HOME/qea/worktrees/qfbench-selfhosted-vm-backend/scripts/check_qfbench_rootless_host.py" \
  --expected-uid 1013 \
  --username julius \
  --docker-host unix:///run/user/1013/docker.sock \
  --source-root "$HOME/qea/worktrees/qfbench-selfhosted-vm-backend" \
  --source-commit "$QEA_SOURCE_COMMIT" \
  --runtime-root "$HOME/qea/runtime" \
  --secret-file "$HOME/qea/runtime/secrets/model-token"
```

Continue only if JSON says `"ready": true` and the human summary says `READY`.

## 7. Plan, Materialize, and Build One Role at a Time

Define paths and run materialization without `--apply` first:

```bash
QEA_REPO="$HOME/qea/worktrees/qfbench-selfhosted-vm-backend"
QEA_PYTHON="$HOME/qea/runtime/venvs/rootless/bin/python"
QFBENCH_COMMIT=024921eb507fcc0c4ffe3e0a96802724be1ae84a
QFBENCH_PUBLIC="$HOME/qea/runtime/qfbench-public/024921eb-five-task"
QFBENCH_TRUSTED="$HOME/qea/runtime/trusted-verifier/024921eb-five-task"

"$QEA_PYTHON" "$QEA_REPO/scripts/materialize_qfbench_rootless_snapshot.py" \
  --source-tree "$HOME/qea/git/qfbench.git" \
  --task-panel-manifest "$QEA_REPO/data/qfbench/MANIFEST.json" \
  --public-root "$QFBENCH_PUBLIC" \
  --trusted-root "$QFBENCH_TRUSTED" \
  --plan-only
```

Require exactly five tasks, zero unexpected denied paths, and no solution output path. Then repeat the same command with `--apply`. Inspect both manifests and confirm no public `tests/` member and no `solution/` member in either root.

Resolve and record the official base `FROM` as an immutable repository digest before building. `QEA_UPSTREAM_DIGEST` must contain `@sha256:`; never pass a tag to the image builder:

```bash
QEA_UPSTREAM_TAG=$(awk 'toupper($1)=="FROM" {print $2; exit}' "$QFBENCH_PUBLIC/docker/sandbox.Dockerfile")
docker pull "$QEA_UPSTREAM_TAG"
QEA_UPSTREAM_DIGEST=$(docker image inspect --format '{{index .RepoDigests 0}}' "$QEA_UPSTREAM_TAG")
case "$QEA_UPSTREAM_DIGEST" in *@sha256:*) ;; *) printf 'un-pinned base image\n' >&2; exit 1;; esac
printf '%s\n' "$QEA_UPSTREAM_DIGEST"
```

Plan and build the base role; inspect the printed context list and manifest before proceeding:

```bash
"$QEA_PYTHON" "$QEA_REPO/scripts/build_qfbench_rootless_images.py" \
  --role base --public-root "$QFBENCH_PUBLIC" \
  --manifest-root "$HOME/qea/runtime/images" \
  --base-image-ref "$QEA_UPSTREAM_DIGEST" \
  --docker-host "$DOCKER_HOST" --expected-uid 1013 --plan-only
```

Repeat with `--build`, then copy the exact base `image_id` from its new `MANIFEST.json` into `QEA_BASE_IMAGE_ID`. Require `sha256:<64 hex>`.

```bash
"$QEA_PYTHON" "$QEA_REPO/scripts/build_qfbench_rootless_images.py" \
  --role base --public-root "$QFBENCH_PUBLIC" \
  --manifest-root "$HOME/qea/runtime/images" \
  --base-image-ref "$QEA_UPSTREAM_DIGEST" \
  --docker-host "$DOCKER_HOST" --expected-uid 1013 --build
```

For `historical-var-data-prep`, plan the worker and verifier separately:

```bash
"$QEA_PYTHON" "$QEA_REPO/scripts/build_qfbench_rootless_images.py" \
  --role worker --task-id historical-var-data-prep \
  --public-root "$QFBENCH_PUBLIC" \
  --manifest-root "$HOME/qea/runtime/images" \
  --base-image-ref "$QEA_BASE_IMAGE_ID" \
  --docker-host "$DOCKER_HOST" --expected-uid 1013 --plan-only

"$QEA_PYTHON" "$QEA_REPO/scripts/build_qfbench_rootless_images.py" \
  --role verifier --task-id historical-var-data-prep \
  --public-root "$QFBENCH_PUBLIC" --trusted-root "$QFBENCH_TRUSTED" \
  --manifest-root "$HOME/qea/runtime/images" \
  --base-image-ref "$QEA_BASE_IMAGE_ID" \
  --docker-host "$DOCKER_HOST" --expected-uid 1013 --plan-only
```

Inspect both plans, then repeat the exact worker command with `--build`; after it completes, repeat the exact verifier command with `--build`. Do not build roles concurrently.

## 8. Advance Infrastructure Canaries One Gate at a Time

The canary defaults to plan-only and has no formal-scoring command:

```bash
"$QEA_PYTHON" "$QEA_REPO/scripts/run_qfbench_rootless_canary.py" \
  --config "$QEA_REPO/configs/qfbench_rootless_canary.json" \
  --runtime-root "$HOME/qea" \
  --source-commit "$QEA_SOURCE_COMMIT" \
  --plan-only
```

Run long coordinators inside `tmux`, record the tmux name and coordinator PID, and stop at the exact requested boundary:

```bash
tmux new-session -s qea-rootless-canary
printf 'coordinator_pid=%s\n' "$$"
"$QEA_PYTHON" "$QEA_REPO/scripts/run_qfbench_rootless_canary.py" \
  --config "$QEA_REPO/configs/qfbench_rootless_canary.json" \
  --runtime-root "$HOME/qea" \
  --source-commit "$QEA_SOURCE_COMMIT" \
  --apply --through-stage force-kill-reap-resume
```

After every stage, inspect its JSON, record exact container/network IDs and hashes, and require an empty managed-container inventory before advancing. A canary result is infrastructure evidence and does not replace the production full-harness stage below.

## 9. Run the Staged Rootless Full Harness

Use the production CLI; `rootless-docker` is explicit here even though it is the
QFBench default. Keep every runtime config, image-set manifest, feedback
manifest, criteria map, and provider token outside Git with owner-only modes.
Record their hashes before launch:

```bash
export QEA_ROOTLESS_CONFIG=/owner-only/path/rootless-config.json
export QEA_IMAGE_SET=/owner-only/path/image-set.json
export QEA_FEEDBACK_MANIFEST=/owner-only/path/optimize-feedback.json
export QEA_CRITERIA_MAP=/owner-only/path/verifier-criteria.json
export QEA_RUN_ID=qfbench-rootless-five-rich-1x-YYYYMMDD-rN
chmod 600 "$QEA_ROOTLESS_CONFIG" "$QEA_IMAGE_SET" "$QEA_FEEDBACK_MANIFEST" "$QEA_CRITERIA_MAP"
sha256sum "$QEA_ROOTLESS_CONFIG" "$QEA_IMAGE_SET" "$QEA_FEEDBACK_MANIFEST" "$QEA_CRITERIA_MAP"
stat -c '%a:%u:%n' "$HOME/qea/runtime/secrets/model-token"
```

Preflight the host, require an empty QEA-managed inventory, and inspect the
configured worker/verifier concurrency plus weighted host limits. The current
measured host policy reserved 48 CPU, 96 GiB, and 24 simultaneous sandboxes,
with worker and verifier concurrency four; treat these as a measured ceiling,
not a mandatory setting.

Launch from the committed worktree so relative worker paths resolve correctly:

```bash
cd "$QEA_REPO"
"$QEA_PYTHON" run.py \
  --benchmark qfbench --executor rootless-docker \
  --qfbench-root "$QFBENCH_PUBLIC" \
  --qfbench-manifest data/qfbench/MANIFEST.json \
  --rootless-config "$QEA_ROOTLESS_CONFIG" \
  --rootless-image-set-manifest "$QEA_IMAGE_SET" \
  --feedback-mode rich \
  --feedback-manifest "$QEA_FEEDBACK_MANIFEST" \
  --verifier-criteria-map "$QEA_CRITERIA_MAP" \
  --run-id "$QEA_RUN_ID" --iters 1 \
  --results-dir "$HOME/qea/runs" --approve-external-run
```

Use `tmux` when available. Otherwise use a detached owner-only log/PID wrapper,
but still `cd` into the worktree before starting. Never pass the token value in
argv or the container environment. The credential proxy alone reads the token
file and injects authorization.

To resume, first verify the exact run ID, immutable config hashes, source
commit, empty-or-reconciled lifecycle inventory, and provider-request state.
Then repeat the exact command with `--resume`. A request quarantined after
possible upstream acceptance must not be retried under the same attempt
identity. A pre-upstream connection/readiness failure may be archived and
retried exactly once after its audit proves `upstream_status` is absent.

After completion require:

- the preregistered score count and split schedule;
- independent `--network none` verifier lifecycles and trusted-input hashes;
- zero official tests/reference data, solutions, credentials, `.env`, or
  held-out evidence on worker/evolver surfaces;
- canonical request states reconciled with any archived quarantine records;
- zero recorded unfinished containers and zero run-owned networks;
- provider usage and cost persisted as numbers, or explicitly `null` when the
  provider does not expose them. Never translate unavailable cost to zero.

Stop immediately on identity drift, unexpected task IDs, missing dependency
locks, verifier egress, trusted-data exposure, ambiguous request acceptance,
host-capacity failure, or broad cleanup pressure. Under the 2026-07-31 gate,
also stop before three iterations or any 30-task run until a deliberate
production coordinator-kill/reaper/resume and cost reconciliation are recorded.

## 10. Exact-ID Recovery and Rollback

The canary lifecycle files under `~/qea/runs/qfbench-rootless-canary-20260728/` are authoritative. Use the canary's built-in dry reaper/apply sequence. For manual incident inspection, record an exact ID from one lifecycle, then verify all ownership labels before removal:

```bash
docker --host unix:///run/user/1013/docker.sock container inspect EXACT_CONTAINER_ID --format '{{json .Config.Labels}}'
docker --host unix:///run/user/1013/docker.sock rm -f EXACT_CONTAINER_ID
docker --host unix:///run/user/1013/docker.sock network inspect qea-qfbench-rootless-canary-20260728-internal --format '{{json .Labels}}'
docker --host unix:///run/user/1013/docker.sock network rm qea-qfbench-rootless-canary-20260728-internal
```

Replace `EXACT_CONTAINER_ID` only after matching `qea.managed=true`, `qea.backend=rootless-docker`, the run ID, attempt ID, and spec SHA from the lifecycle. Do not translate these commands into a wildcard, `xargs`, a broad label filter, or `docker system prune`.

To stop the runtime without deleting evidence:

```bash
systemctl --user stop docker
systemctl --user status docker --no-pager
```

Do not remove the bare Git repository, committed worktree, role manifests, lifecycle JSON, or verifier evidence during rollback. Restart only after the prior exact-ID inventory is reconciled.

## 11. Five-Repetition Baseline Scheduler Epoch Transition

For run
`qfbench-rootless-base-85x5-official-deepseek-v4-flash-noreplay-recovery2-20260803`,
do not edit the schema-v1 checkpoint or start repetition 02 manually. Recovery
must run through the committed process-group supervisor and pre-exec gate at
worker/verifier concurrency `4/3`. Attach the boundary guard and run-aware watch
to the exact child PID, PGID, start ticks, argv digest, run ID, and source commit
before releasing the gate.

The boundary is eligible only at 85 repetition-01 terminal scores with
`next_repetition=2`, `phase=primary`, null `pending_primary`, no repetition-02
evidence, and zero run-owned containers/networks. Freeze the evidence manifest,
terminate the stopped legacy process group, and publish the schema-v2 checkpoint
only after those facts remain true. Preserve all previous scores, ledgers,
lifecycles, and hard-stop records byte-for-byte.

Epoch 2 uses schema-3 config label `repetitions-02-through-05`, concurrency
`12/3`, capacity `48 CPU / 98,304 MiB / 8,192 PIDs / 40,960 MiB tmpfs / 24
sandboxes`, maximum load 56, and minimum Linux `MemAvailable` 16,384 MiB. Before
resume, run the no-model import canary and then:

```bash
"$QEA_PYTHON" scripts/smoke_qfbench_full_harness.py \
  --executor rootless-docker --mode paid-baseline-batch \
  --qfbench-root "$QFBENCH_PUBLIC" \
  --manifest data/qfbench/MANIFEST_85_BASELINE.json \
  --rootless-config "$QEA_EPOCH2_CONFIG" \
  --rootless-image-set-manifest "$QEA_IMAGE_SET" \
  --run-id "$QEA_EPOCH2_CANARY_RUN_ID" \
  --results-dir "$HOME/qea/runs" --approve-external-run
```

Require `worker_overlap=12`, model `deepseek/deepseek-v4-flash`, provider
`deepseek`, `fallbacks_allowed=false`, only completed HTTP-200 proxy records,
complete cost accounting, no within-attempt replay, verifier network policy
`none`, complete exact-ID cleanup, and zero residual resources. Any failure
blocks epoch 2; do not silently fall back to a lower concurrency under the same
epoch identity.

Launch repetitions 02–05 only through the new supervisor/watch/sentinel unit
generation and keep the Mac repair controller under `caffeinate -i`. At final
completion require five repetitions, 425 terminal scores, zero residual
resources, a passing firewall scan, and per-epoch plus combined reporting with
the scheduler batch-effect warning.
