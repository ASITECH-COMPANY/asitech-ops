# Security Policy

## Supported versions

ASITECH OPS is in early development (0.x). Only the latest commit on `main`
receives security fixes until the first stable release; a support policy for
release lines will be published with 1.0.

## Reporting a vulnerability

**Please do not open a public issue, pull request or discussion.**

Report privately by one of these channels:

* E-mail: **security@asitechsolution.cloud**
* GitHub: *Security* tab → *Report a vulnerability* (private advisory), once the
  repository is public.

> Note: until the `security@asitechsolution.cloud` mailbox is confirmed active,
> use GitHub private vulnerability reporting.

Please include:

* affected component (Control Plane, dashboard, agent, installer, website) and version/commit;
* steps to reproduce or a proof of concept;
* impact as you understand it;
* whether you want to be credited.

## What to expect

| Step | Target |
|---|---|
| Acknowledgement | within 3 business days |
| Initial assessment | within 10 business days |
| Fix or mitigation for high/critical issues | as fast as possible, coordinated with you |
| Public disclosure | after a fix is available, typically within 90 days |

We credit reporters in the release notes unless they prefer otherwise. We will
not take legal action against good-faith research that respects this policy:
no data destruction, no privacy violations, no service disruption, and testing
only on instances you own or are authorized to test.

## Scope highlights

Of particular interest: tenant isolation bypasses, authentication or session
flaws, CSRF, privilege escalation between roles, agent/task authentication,
replay, command or container escape through the agent, Docker socket exposure,
installer integrity, secrets leaking into logs or API responses.

The security design is documented in
[docs/security/architecture.md](docs/security/architecture.md).
