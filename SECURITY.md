# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | ✅ Yes    |
| < 0.2   | ❌ No     |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Contact [galdr@sellemain.com](mailto:galdr@sellemain.com).

If GitHub private vulnerability reporting is enabled for the repository, you may also use the private reporting flow from the repository security tab.

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
