# Agent instructions

CI rebuilds the bundled third-party packages (`resources/python`) for pull
requests that change a `requirements.txt` file, unless the source branch ends
with `-no-rebuild`. It then opens a second pull request from a
`<branch>-automated` branch (never use that suffix yourself).
See [resources/python/README.md](resources/python/README.md).

CI decides from the pull request diff, so branch names need no suffix:

- Never end a branch name with `-automated`.
- Only end a branch name with `-no-rebuild` when the user explicitly asks to
  skip the rebuild for a pull request that changes a `requirements.txt` file.
