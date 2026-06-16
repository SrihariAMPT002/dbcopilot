"""Deterministic PII rule matching for governance."""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class PIIRuleMatch:
    pattern_key: str
    label: str
    match_type: str
    risk_level: str
    confidence: float
    matched_value: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PIIRuleService:
    """Regex, keyword, and datatype heuristics for governance."""

    def __init__(self) -> None:
        self._patterns: list[tuple[str, str, str, re.Pattern[str], float]] = [
            ("email", "email", "regex", re.compile(r"(?i)(?:^|[^a-z0-9])[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), 0.98),
            ("phone", "phone", "regex", re.compile(r"(?i)(?:\+?\d[\d\s().-]{7,}\d)"), 0.92),
            ("mobile", "mobile", "keyword", re.compile(r"(?i)\b(?:mobile|cell|cellphone|handset|msisdn)\b"), 0.94),
            ("dob", "date_of_birth", "keyword", re.compile(r"(?i)\b(?:dob|date_of_birth|birthdate|birthday|birth_date)\b"), 0.94),
            ("passport", "passport", "keyword", re.compile(r"(?i)\bpassport\b|\bpassport_no\b|\bpassport_number\b"), 0.96),
            ("aadhaar", "aadhaar", "keyword", re.compile(r"(?i)\baadhaar\b|\baadhar\b"), 0.99),
            ("ssn", "ssn", "keyword", re.compile(r"(?i)\bssn\b|\bsocial[_\s-]?security\b|\bsocial_security_number\b"), 0.99),
            ("license", "license", "keyword", re.compile(r"(?i)\blicen[cs]e\b|\blicense_number\b|\bdriving[_\s-]?license\b|\bdl_number\b"), 0.95),
            ("upi", "upi", "keyword", re.compile(r"(?i)\bupi\b|\bupi_id\b|\bvpa\b"), 0.96),
            ("iban", "iban", "keyword", re.compile(r"(?i)\biban\b|\bswift\b|\bbic\b"), 0.97),
            ("bank_account", "bank_account", "keyword", re.compile(r"(?i)\b(?:bank[_\s-]?account|acct(?:ount)?|account[_\s-]?no)\b"), 0.9),
            ("credit_card", "credit_card", "keyword", re.compile(r"(?i)\b(?:credit[_\s-]?card|debit[_\s-]?card|pan|cvv|cvc)\b"), 0.97),
            ("tax_id", "tax_id", "keyword", re.compile(r"(?i)\b(?:tax[_\s-]?id|tin|vat|gstin|ein)\b"), 0.95),
            ("address", "address", "keyword", re.compile(r"(?i)\b(?:address|street|postcode|zip|postal|city|state|country)\b"), 0.72),
            ("name", "name", "keyword", re.compile(r"(?i)\b(?:first[_\s-]?name|last[_\s-]?name|full[_\s-]?name|given[_\s-]?name|family[_\s-]?name)\b"), 0.78),
            ("medical", "medical", "keyword", re.compile(r"(?i)\b(?:diagnosis|medical|patient|provider|symptom|treatment|prescription|claim)\b"), 0.9),
            ("auth", "auth", "keyword", re.compile(r"(?i)\b(?:password|passcode|otp|mfa|2fa|auth|token|secret|apikey|api_key)\b"), 0.98),
        ]
        self._column_name_hints: list[tuple[str, str, float]] = [
            ("email", "email", 0.98),
            ("mail", "email", 0.92),
            ("e_mail", "email", 0.92),
            ("phone", "phone", 0.96),
            ("mobile", "mobile", 0.96),
            ("contact", "contact", 0.72),
            ("dob", "date_of_birth", 0.95),
            ("birth", "date_of_birth", 0.92),
            ("passport", "passport", 0.96),
            ("aadhaar", "aadhaar", 0.99),
            ("aadhar", "aadhaar", 0.99),
            ("ssn", "ssn", 0.99),
            ("license", "license", 0.92),
            ("upi", "upi", 0.96),
            ("iban", "iban", 0.97),
            ("account", "bank_account", 0.84),
            ("card", "credit_card", 0.9),
            ("pan", "tax_id", 0.92),
            ("tax", "tax_id", 0.9),
            ("diagnosis", "medical", 0.92),
            ("claim", "medical", 0.84),
            ("policy", "policy", 0.72),
            ("patient", "medical", 0.82),
            ("provider", "medical", 0.8),
            ("first_name", "name", 0.88),
            ("last_name", "name", 0.88),
            ("full_name", "name", 0.9),
        ]

    def match_column(self, *, column_name: str, data_type: str, table_context: str = "", neighbor_context: str = "") -> list[PIIRuleMatch]:
        haystack = " ".join([column_name or "", data_type or "", table_context or "", neighbor_context or ""]).strip()
        matches: list[PIIRuleMatch] = []
        lowered = haystack.lower()
        normalized_column = (column_name or "").lower()

        for hint, label, confidence in self._column_name_hints:
            if hint in normalized_column:
                matches.append(
                    PIIRuleMatch(
                        pattern_key=f"column_hint:{hint}",
                        label=label,
                        match_type="column_name",
                        risk_level=self._risk_from_label(label, confidence),
                        confidence=confidence,
                        matched_value=hint,
                    )
                )

        for pattern_key, label, match_type, pattern, confidence in self._patterns:
            if pattern.search(haystack):
                matches.append(
                    PIIRuleMatch(
                        pattern_key=pattern_key,
                        label=label,
                        match_type=match_type,
                        risk_level="high" if confidence >= 0.9 else "medium",
                        confidence=confidence,
                        matched_value=pattern.search(haystack).group(0) if pattern.search(haystack) else None,
                    )
                )
            elif pattern_key in lowered:
                matches.append(
                    PIIRuleMatch(
                        pattern_key=pattern_key,
                        label=label,
                        match_type="keyword",
                        risk_level="high" if confidence >= 0.9 else "medium",
                        confidence=confidence,
                        matched_value=pattern_key,
                    )
                )

        dtype = (data_type or "").lower()
        if self._looks_like_email_dtype(dtype, normalized_column):
            matches.append(PIIRuleMatch("email_datatype", "email", "datatype", "high", 0.88, data_type))
        if self._looks_like_phone_dtype(dtype, normalized_column):
            matches.append(PIIRuleMatch("phone_datatype", "phone", "datatype", "high", 0.82, data_type))
        if self._looks_like_name_dtype(dtype, normalized_column):
            matches.append(PIIRuleMatch("name_datatype", "name", "datatype", "medium", 0.7, data_type))
        if self._looks_like_medical_context(dtype, lowered):
            matches.append(PIIRuleMatch("medical_context", "medical", "context", "high", 0.9, data_type))
        return self._dedupe(self._boost_with_context(matches, lowered, normalized_column))

    @staticmethod
    def _risk_from_label(label: str, confidence: float) -> str:
        if label in {"aadhaar", "ssn", "passport", "credit_card", "auth", "tax_id", "bank_account", "upi", "iban"}:
            return "critical" if confidence >= 0.95 else "high"
        if label in {"email", "phone", "mobile", "license", "medical"}:
            return "high" if confidence >= 0.85 else "medium"
        return "medium"

    @staticmethod
    def _looks_like_email_dtype(dtype: str, column: str) -> bool:
        return any(token in dtype for token in ["email", "varchar", "text", "char"]) and "email" in column

    @staticmethod
    def _looks_like_phone_dtype(dtype: str, column: str) -> bool:
        return any(token in dtype for token in ["phone", "mobile", "tel", "char", "text", "varchar", "number"]) and any(
            token in column for token in ["phone", "mobile", "cell", "contact"]
        )

    @staticmethod
    def _looks_like_name_dtype(dtype: str, column: str) -> bool:
        return any(token in column for token in ["name", "firstname", "lastname", "fullname"]) and any(
            token in dtype for token in ["char", "text", "varchar"]
        )

    @staticmethod
    def _looks_like_medical_context(dtype: str, haystack: str) -> bool:
        if any(token in haystack for token in ["diagnosis", "patient", "provider", "claim", "symptom", "treatment", "prescription"]):
            return True
        return any(token in dtype for token in ["json", "text", "varchar"])

    def _boost_with_context(
        self,
        matches: list[PIIRuleMatch],
        lowered_haystack: str,
        normalized_column: str,
    ) -> list[PIIRuleMatch]:
        boosted: list[PIIRuleMatch] = []
        for match in matches:
            confidence = match.confidence
            if match.label in {"email", "phone", "mobile", "medical"} and any(token in lowered_haystack for token in ["contact", "patient", "provider", "customer", "user"]):
                confidence = min(0.99, confidence + 0.03)
            if match.label in {"ssn", "aadhaar", "passport", "bank_account", "credit_card", "auth", "tax_id", "upi", "iban"}:
                confidence = min(0.995, confidence + 0.01)
            if any(token in normalized_column for token in ["_no", "_num", "_number", "_id"]) and match.label in {"license", "passport", "tax_id", "bank_account", "credit_card"}:
                confidence = min(0.99, confidence + 0.02)
            boosted.append(
                PIIRuleMatch(
                    pattern_key=match.pattern_key,
                    label=match.label,
                    match_type=match.match_type,
                    risk_level=self._risk_from_label(match.label, confidence),
                    confidence=confidence,
                    matched_value=match.matched_value,
                )
            )
        return boosted

    def _dedupe(self, matches: list[PIIRuleMatch]) -> list[PIIRuleMatch]:
        seen: set[tuple[str, str]] = set()
        deduped: list[PIIRuleMatch] = []
        for match in matches:
            key = (match.pattern_key, match.match_type)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(match)
        return deduped
