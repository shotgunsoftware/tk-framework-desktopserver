[![Supported VFX Platform: CY2022 - CY2026](https://img.shields.io/badge/VFX_Reference_Platform-CY2022_|_CY2023_|_CY2024_|_CY2025_|_CY2026-blue)](http://www.vfxplatform.com/ "Supported VFX Reference Platform versions")
[![Supported Python versions: 3.9, 3.10, 3.11, 3.13](https://img.shields.io/badge/Python-3.9_|_3.10_|_3.11_|_3.13-blue?logo=python&logoColor=f5f5f5)](https://www.python.org/ "Supported Python versions")

[![Build Status](https://dev.azure.com/shotgun-ecosystem/Toolkit/_apis/build/status/shotgunsoftware.tk-framework-desktopserver?branchName=master)](https://dev.azure.com/shotgun-ecosystem/Toolkit/_build/latest?definitionId=81&branchName=master)
[![codecov](https://codecov.io/gh/shotgunsoftware/tk-framework-desktopserver/branch/master/graph/badge.svg)](https://codecov.io/gh/shotgunsoftware/tk-framework-desktopserver)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# Toolkit Framework Desktop Server

This framework manages the integration between Flow Production Tracking and
Flow Production Tracking Web (browser integration).

## Documentation
This repository is a part of the Flow Production Tracking Toolkit.

- For more information about this framework and for release notes, *see the wiki section*.
- For general information and documentation, click here: https://developer.shotgridsoftware.com/d587be80/?title=Integrations+User+Guide
- For information about Flow Production Tracking in general, click here: https://help.autodesk.com/view/SGSUB/ENU

## Using this framework in your Setup
All the frameworks that are part of our standard framework suite are pushed to our App Store.
This is where you typically go if you want to install a framework into a project you are
working on. For an overview of all the Apps and Engines in the Toolkit App Store,
click here: https://developer.shotgridsoftware.com/162eaa4b/?title=Pipeline+Integration+Components

## Regenerating 3rd-Party Packages

The bundled 3rd-party packages (`resources/python/src/` and `resources/python/bin/`)
are regenerated automatically by Azure Pipelines. This is an **opt-in** process - it
only runs when the PR branch name **ends with `-rebuild-pkgs`**.

The generated branch is named `<your-branch>-automated`, which does not end with
`-rebuild-pkgs`, so regeneration can never trigger itself recursively.

### How to trigger package regeneration

1. Create a branch whose name ends with `-rebuild-pkgs`:
   ```
   git switch -c ticket/SG-1234-rebuild-pkgs
   ```
2. Open a Pull Request from that branch.
3. Azure Pipelines will automatically run the `Py 3rd-Party Pkgs` jobs across all
   Python versions (3.7, 3.9, 3.10, 3.11, 3.13) and platforms (Linux, Mac, Windows).
4. The regenerated packages are committed to a new branch named
   `ticket/SG-1234-rebuild-pkgs-automated` and pushed to the repository.

Any branch that does not end with `-rebuild-pkgs` skips all regeneration jobs entirely.

### Git hook (recommended)

A `post-checkout` hook is provided to warn you whenever you switch to a branch that
will trigger regeneration. The executable bit is stored in git, so no `chmod` is needed.
To activate it, run once in the repo root:

```
git config core.hooksPath .githooks
```

## Have a Question?
Don't hesitate to contact us! You can find us on https://www.autodesk.com/support
