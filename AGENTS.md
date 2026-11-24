# Agent instructions

CI rebuilds the bundled third-party packages (`resources/python`) for pull
requests that change a `requirements.txt` file, unless the source branch ends
with `-no-rebuild`. It then opens a second pull request from a
`<branch>-automated` branch (never use that suffix yourself).
See [resources/python/README.md](resources/python/README.md).

Before creating a branch or pull request:

1. Guess if the change needs the rebuild. Likely yes if a `requirements.txt`
   file changes, likely no for anything else (code, tests, docs, CI). Changes
   to the install scripts in `resources/python` alone do not trigger it.
2. Tell the user your guess and the branch name you will use, and ask for
   confirmation.
3. No rebuild: end the branch name with `-no-rebuild`, for example
   `ticket/SG-12345-fix-docs-no-rebuild`. Rebuild: no suffix.
4. Pull request already opened from the wrong branch name: it cannot be renamed.
   Ask before closing it and reopening from a new branch. Never force push.
