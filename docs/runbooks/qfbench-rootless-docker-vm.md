# QFBench Rootless Docker VM Runbook

This runbook deploys the committed `qfbench-selfhosted-vm-backend` branch to the shared `bc` host and runs only the staged five-task backend canary. It does not authorize formal 30-task or five-iteration scoring. Keep local Git as the source of truth; use the VM only as a Linux/rootless-Docker execution node.

## Safety Boundaries

- Never copy the repository recursively, transfer `.env`, or place a provider token in Git, a Docker environment variable, an image layer, a process argument, or a host bind mount.
- Never check out, copy, upload, or run official `solution/` blobs. The QFBench source is a blob-filtered bare repository; the materializer fetches only public inputs and verifier tests.
- Keep official tests only under `~/qea/runtime/trusted-verifier/`, mode `700`; workers receive only the separate public root.
- Use only `unix:///run/user/1013/docker.sock`. `/var/run/docker.sock`, privileged containers, host networking, and host mounts are forbidden.
- Never run `docker system prune`, wildcard cleanup, or label-wide deletion. Record and remove exact QEA container/network IDs only.
- Do not merge this branch. Stop after the one fresh seed-worker canary; do not start 30×5 scoring.

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

If a tested follow-up commit is required after the worktree exists, use a non-checked-out incoming ref:

```bash
git push bc:~/qea/git/evolving-quant-agent.git HEAD:refs/heads/qfbench-selfhosted-vm-backend-incoming
ssh bc 'git -C "$HOME/qea/worktrees/qfbench-selfhosted-vm-backend" merge --ff-only qfbench-selfhosted-vm-backend-incoming'
```

Do not push over a checked-out ref, use `rsync` for the repo, or create a second source of truth on the VM.

## 4. Create a Blob-Filtered QFBench Object Store

Create a bare, no-checkout source store. Tree metadata includes denied path identities, but only requested public/test blobs are fetched by the role materializer; no solution worktree is created:

```bash
git clone --bare --filter=blob:none https://github.com/QF-Bench/QuantitativeFinance-Bench.git "$HOME/qea/git/qfbench.git"
git --git-dir="$HOME/qea/git/qfbench.git" fetch --filter=blob:none origin 024921eb507fcc0c4ffe3e0a96802724be1ae84a
git --git-dir="$HOME/qea/git/qfbench.git" cat-file -t 024921eb507fcc0c4ffe3e0a96802724be1ae84a
```

Do not run `git checkout`, `git show ...:tasks/.../solution/...`, or an unfiltered clone.

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

## 8. Advance the Canary One Gate at a Time

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

After every stage, inspect its JSON, record exact container/network IDs and hashes, and require an empty managed-container inventory before advancing. Verifier replay and the one paid fresh seed-worker are separate later approvals in the execution plan; this runbook does not combine them with formal scoring.

## 9. Exact-ID Recovery and Rollback

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
