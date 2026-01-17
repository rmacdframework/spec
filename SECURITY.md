# Security Policy

## Reporting a Vulnerability

The RMACD Framework team takes security vulnerabilities seriously. We appreciate your efforts to responsibly disclose your findings.

### How to Report

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please report security vulnerabilities by emailing:

**security@rmacd-framework.org**

Include the following information in your report:

- Type of vulnerability (e.g., schema bypass, privilege escalation pattern, compliance gap)
- Full path to the affected file(s) or schema
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if applicable)
- Impact assessment of the vulnerability
- Any suggested remediation

### What to Expect

| Timeline | Action |
|----------|--------|
| **24 hours** | Acknowledgment of your report |
| **72 hours** | Initial assessment and severity classification |
| **7 days** | Detailed response with remediation plan |
| **90 days** | Target resolution for confirmed vulnerabilities |

### Scope

The following are in scope for security reports:

| In Scope | Examples |
|----------|----------|
| **Schema vulnerabilities** | Bypass patterns, missing validations, constraint weaknesses |
| **Governance matrix gaps** | Autonomy level assignments that violate security principles |
| **Profile template flaws** | Default profiles that create security risks |
| **Compliance mapping errors** | Incorrect regulatory mappings that could cause violations |
| **Implementation guidance issues** | Patterns that could lead to insecure deployments |

### Out of Scope

- Vulnerabilities in third-party implementations of RMACD
- Issues in platforms that integrate RMACD (report to those vendors)
- Theoretical attacks without practical exploitation path
- Social engineering attacks

### Disclosure Policy

We follow a **90-day responsible disclosure** policy:

1. Reporter submits vulnerability privately
2. RMACD team acknowledges and investigates
3. Fix is developed and tested
4. Security advisory is prepared
5. Fix is released with coordinated disclosure
6. Reporter is credited (unless anonymity requested)

### Security Advisories

Security advisories will be published in:

- [GitHub Security Advisories](https://github.com/rmacdframework/spec/security/advisories)
- CHANGELOG.md (with CVE reference if applicable)
- Announcement on project communication channels

### Recognition

We believe in recognizing security researchers who help improve the framework:

- Credit in the security advisory (with permission)
- Acknowledgment in CHANGELOG.md
- Listing in a future Security Hall of Fame

### Safe Harbor

We consider security research conducted consistent with this policy to be:

- Authorized and lawful
- Helpful to the community
- Conducted in good faith

We will not pursue legal action against researchers who:

- Make a good faith effort to avoid privacy violations and data destruction
- Only interact with accounts they own or have explicit permission to test
- Do not exploit vulnerabilities beyond what is necessary to demonstrate the issue
- Report vulnerabilities promptly and do not publicly disclose before resolution

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.1.x | Yes |
| 1.0.x | Security fixes only |
| < 1.0 | No |

## Security Best Practices for Implementers

When implementing RMACD in production environments:

### Profile Management

- Store permission profiles in encrypted, access-controlled repositories
- Implement profile signing to prevent tampering
- Version control all profile changes with audit trails
- Review profiles quarterly for privilege creep

### Policy Enforcement

- Deploy Policy Decision Points (PDP) with high availability
- Implement defense-in-depth (don't rely solely on RMACD)
- Log all policy decisions with tamper-evident logging
- Monitor for anomalous permission patterns

### Data Classification

- Classify all data sources before granting agent access
- Re-validate classifications periodically
- Default to higher classification when uncertain
- Implement automated classification verification

### Approval Workflows

- Require multi-factor authentication for approvers
- Implement approval timeouts (don't allow indefinite pending)
- Log all approval decisions with justification
- Separate approval authority from agent operators

### Audit and Compliance

- Retain audit logs per regulatory requirements (minimum 1 year)
- Implement real-time alerting for Restricted data operations
- Conduct regular compliance audits against governance matrix
- Test incident response procedures quarterly

## Contact

- **Security issues**: security@rmacd-framework.org
- **General questions**: contact@rmacd-framework.org
- **GitHub**: https://github.com/rmacdframework/spec

---

*This security policy is effective as of January 2026 and will be reviewed quarterly.*
