# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | ✅ Yes    |
| < 0.2   | ❌ No     |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Use GitHub's private vulnerability reporting:
**[Report a vulnerability](https://github.com/sellemain/galdr/security/advisories/new)**

If private vulnerability reporting is unavailable, contact [galdr@sellemain.com](mailto:galdr@sellemain.com).

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fix (optional)

You'll receive an acknowledgment within 48 hours. If the issue is confirmed, a patch will be released as quickly as possible (typically within 7 days for high-severity issues).

## Scope

galdr is a local audio analysis tool. It makes outbound network requests to:
- **YouTube** (via yt-dlp) — audio/metadata download
- **Genius** — lyric lookup
- **Wikipedia** — artist/song context

All user-supplied URLs are validated against a strict allowlist before being passed to subprocesses. All user-supplied slugs are validated against `[A-Za-z0-9._-]+` before filesystem use.
