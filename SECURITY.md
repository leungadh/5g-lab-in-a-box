# Security Policy & Authorized Use

## This is a security lab. Read this first.

`5g-lab-in-a-box` includes scripts under [`attacks/`](attacks/) that generate malformed and high-volume GTP-U (N3) and PFCP (N4) traffic, plus signaling churn. They exist to test **a 5G core you own and operate** and to produce labeled traffic for anomaly-detection research.

**Authorized use only.** Point these tools only at lab infrastructure you control and are explicitly permitted to test. Unauthorized interference with telecommunications networks is illegal in most jurisdictions. See [`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md) for the full scope.

## Built-in guardrails

Every attack script imports `attacks/_common.py::assert_lab_target()`, which refuses to send unless:

1. the destination is loopback or an RFC-1918 private address, **and**
2. the operator passes the explicit `--i-own-this-lab` acknowledgement flag.

This is deliberate friction to prevent accidental misuse. Do not remove it. Captured pcaps and derived datasets are git-ignored and must not contain real subscriber data.

## Reporting a vulnerability

If you find a security issue in this project's own code (for example, the guardrail can be bypassed, or a script behaves unsafely against a lab target), please open a private report via GitHub Security Advisories, or email the maintainer rather than filing a public issue. Please do not include exploit traffic or captures against third-party networks.

## Scope

In scope: bugs in this repository's scripts, configs, and IaC.
Out of scope: vulnerabilities in Open5GS, free5GC, UERANSIM, or other upstream projects — report those to their respective maintainers.
