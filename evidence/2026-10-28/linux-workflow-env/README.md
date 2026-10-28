# ARM64 workflow runner-path repair

The native Linux workflow placed `${{ runner.temp }}` in `jobs.native.env`,
where the runner context is unavailable. The source path is now appended to
`GITHUB_ENV` inside the existing first validation step, using the runtime
`RUNNER_TEMP` variable. Later fetch/build/test steps retain the same private
temporary checkout path. Runner labels, source pins, read-only permissions,
sanitizer flags and selected suites remain unchanged.

The focused tests execute the actual workflow bootstrap with an existing env
file and a path containing spaces. Invalid relative/newline paths fail before
writing. A context-availability regression checks the job-level expressions.
The remaining workflow contracts still reject skipped/empty/failed suites and
parse all embedded Python blocks. These local tests are not hosted GitHub
Actions or native AArch64 acceptance. No Pi, robot, service or release is used.

References: GitHub's
[context-availability table](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability)
and [environment-file contract](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#setting-an-environment-variable).
The prior `0de8754` publication denial remains isolated. This follow-up is local;
no push, dispatch, deployment, main/GP, protected P4 or paused SFC change occurs.
