# Security Policy

[pychess.org](https://github.com/pychess/pychess-variants/) is a free and open source chess server powered by volunteers and donations. We are a non-profit and don't answer to any shareholders, only our users. That is reflected in our discussions and decisions every day.

Like all contributions to Pychess, security reviews and pentesting are appreciated.

If you believe you've found a security issue in our platform, we encourage you to notify us. We welcome working with you to resolve the issue promptly.
## Reporting vulnerabilities

Please report security issues through [GitHub security advisory](https://github.com/pychess/pychess-variants/security/advisories/new).

Vulnerabilities are relevant even when they are not directly exploitable, for example XSS mitigated by CSP.

## Rules for testing production infrastructure

* Perform testing only on assets that are in scope.
* Make good faith efforts to avoid privacy violations, destruction of data, interruption or degradation of service, and any annoyance or inconvenience to Pychess users, including spam.
* If a vulnerability provides unintended access to data, limit the amount of data you access to the minimum required for effectively demonstrating a Proof of Concept.
* Do not create more than 5 user accounts.
* All forms of social engineering (e.g., phishing) are strictly prohibited.
* Respect HTTP rate limits, i.e., slow down when you receive HTTP 429.

## Exclusions

Please do not submit issues regarding:

* Theoretical vulnerabilities without any proof or demonstration of the real presence of the vulnerability
* Findings from automated tools without providing a Proof of Concept
(D)DoS
* Missing X-Content-Type-Options, Referrer-Policy or Feature-Policy headers
* Non-sensitive data disclosure, including software version information, confirmation that a specific email address is in use, confirming the existence (but not content) of sensitive information
* Content spoofing and text injection issues without showing an attack vector/without being able to modify HTML/CSS
* Previously known vulnerable software or libraries without a working Proof of Concept
* Vulnerabilities requiring access to a user’s browser, or a smartphone, or email account
* CSRF from local files (file://) using [https://bugzilla.mozilla.org/show_bug.cgi?id=1608391](https://bugzilla.mozilla.org/show_bug.cgi?id=1608391)
* Cheating at puzzles, including /training, /racer, /storm, /streak and /learn. They're about training, not competition.

## Response targets

We aim to meet the following response targets:

* Time to first response: 2 days after report submission
* Time to resolution: 30 days

## Disclosure

All vulnerabilities will be disclosed via GitHub once they have been confirmed and resolved.
## Rewards

We do not currently pay cash bounties.
## Safe Harbor

Any activities conducted in a manner consistent with this policy will be considered authorized conduct (even without prior coordination) and we will not initiate legal action against you. If legal action is initiated by a third party against you in connection with activities conducted under this policy, we will take steps to make it known that your actions were conducted in compliance with this policy.

Thank you for helping keep Pychess users safe!
