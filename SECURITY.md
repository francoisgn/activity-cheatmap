# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report them privately from the repository's **Security** tab:
**Report a vulnerability** (GitHub private vulnerability reporting).
The report is only visible to you and the maintainer.

Please include what you found, how to reproduce it and the impact you
expect. You should get an answer within a week.

## Supported versions

Only the latest version on `main` is supported.

## Scope

activity-cheatmap runs locally and only talks to GitHub through `git`
(`ls-remote`, `push`) and one public profile page per year for `--compare`.
Relevant reports include, for example: command or option injection into
`git`, writing or deleting files outside the output directory, or leaking
credentials.
