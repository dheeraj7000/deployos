"""Prompt Injection Detection and Adversarial Pattern Analyzer."""

import re
from typing import NamedTuple


class InjectionScanResult(NamedTuple):
    is_suspicious: bool
    risk_score: float  # 0.0 to 1.0
    detected_patterns: list[str]
    details: str


class InjectionDetector:
    """Scans untrusted inputs (customer emails, PDFs, external web) for injection patterns."""

    PATTERNS = [
        (r"ignore\s+(?:all\s+)?previous\s+instructions", "INSTRUCTION_OVERRIDE", 0.95),
        (r"system\s+(?:prompt|instruction):", "SYSTEM_ROLE_MIMIC", 0.90),
        (r"you\s+are\s+now\s+(?:in|acting\s+as)", "ROLE_HIJACK", 0.85),
        (r"bypass\s+(?:policy|authorization|approval|security)", "POLICY_BYPASS_ATTEMPT", 0.95),
        (r"(?:issue|send|transfer)\s+(?:a\s+)?(?:\$[\d,]+|\d+\s*usd)\s+immediately", "FORCED_FINANCIAL_ACTION", 0.85),
        (r"already\s+been\s+verified", "FALSE_AUTHORIZATION_ASSERTION", 0.75),
        (r"do\s+not\s+(?:check|verify|ask|validate)", "VERIFICATION_SUPPRESSION", 0.90),
        (r"disregard\s+(?:safety|rules|limits)", "SAFETY_OVERRIDE", 0.95),
        (r"admin\s+override\s+code", "FORGED_PRIVILEGE", 0.90),
        (r"<script>|javascript:|curl\s+http", "DATA_EXFILTRATION_PROBE", 0.80),
    ]

    def scan(self, text: str) -> InjectionScanResult:
        if not text:
            return InjectionScanResult(False, 0.0, [], "Clean")

        lowered = text.lower()
        matched_patterns = []
        max_score = 0.0

        for regex, name, score in self.PATTERNS:
            if re.search(regex, lowered, re.IGNORECASE):
                matched_patterns.append(name)
                max_score = max(max_score, score)

        is_suspicious = len(matched_patterns) > 0 and max_score >= 0.70
        details = (
            f"Detected {len(matched_patterns)} adversarial pattern(s): {', '.join(matched_patterns)}"
            if matched_patterns
            else "Clean content"
        )

        return InjectionScanResult(
            is_suspicious=is_suspicious,
            risk_score=max_score,
            detected_patterns=matched_patterns,
            details=details,
        )


detector = InjectionDetector()
