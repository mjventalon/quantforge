# Security policy

## Supported versions

Only the latest release receives security fixes.

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's *Report a vulnerability* (Security →
Advisories) on this repository, or write to the project contact address listed on the
*Creator* page of the official deployment. You will get an answer within 7 days.

Please include steps to reproduce, the affected version and the impact.

## Design notes for operators

* **Never** set `QUANTFORGE_ALLOW_CODE_EXECUTION=1` on a public server: it lets the Academy run
  submitted code on the machine. On servers, Python exercises run in the visitor's browser.
* Keep `QUANTFORGE_CERT_SECRET` secret and backed up; anyone who has it can forge certificates.
* API keys typed by visitors live only in their session memory; they are never written to disk
  or logs by quantforge. Do not add logging that would capture them.
* `.env` is git-ignored. Never commit keys.
