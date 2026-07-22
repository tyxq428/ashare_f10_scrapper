# Visual-first execution policy

The supported user path is the Web execution center, not manual CLI configuration.

## Windows

Double-click `scripts/start-web.bat`, or right-click `scripts/start-web.ps1` and run with PowerShell.
The launcher installs/updates the local editable package and opens:

```text
http://127.0.0.1:8000/run.html
```

All execution parameters are configured in the page:

- stock code;
- F10-only, F10 + Raw Pack, F10 + official validation, or complete research pack;
- concurrency;
- resume/cache reuse;
- automatic failed-group recovery;
- Raw Pack selection and document limit;
- official report years;
- task polling interval.

## Reliability contract

- completed sub-tasks are reused;
- only failed F10 groups are retried;
- transient network failures use finite exponential backoff;
- permission/captcha sources are recorded as `PERMISSION_BLOCKED` and are not looped;
- optional Raw Pack and official-validation stages run in parallel after a complete F10 core;
- `NO_MATCH` never means zero or non-existence.

The CLI remains available for CI and advanced operators, but user-facing instructions should prefer the Web page and the PowerShell launcher.
