# -*- coding: utf-8 -*-
"""Stateless, thread-safe learning and post-OCR correction engine for the Ohr HaKsav web app."""

from __future__ import annotations

import difflib
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from core.learning_engine import (
    BUILTIN_CURSIVE_FIXES,
    CURSIVE_CHAR_SWAPS,
    DEFAULT_CORRECTIONS,
    DEFAULT_VOCABULARY,
    SAFE_COMMON_HEBREW,
    TORAH_CURSIVE_TARGETS,
)

MAX_USER_RULES = 5000


def normalize_user_rules(raw_rules: Any, max_rules: int = MAX_USER_RULES) -> List[Dict[str, Any]]:
    """Validate and normalize user replacement rules from JSON string or list.

    Matches the desktop LearningEngine JSON export format:
    [{"raw_text": "...", "corrected_text": "...", "count": 1, "is_active": true}, ...]
    """
    parsed: Any = raw_rules
    if isinstance(raw_rules, str):
        stripped = raw_rules.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return []

    if not isinstance(parsed, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in parsed:
        if len(normalized) >= max_rules:
            break
        if not isinstance(item, dict):
            continue
        raw = str(item.get("raw_text", "")).strip()
        corr = str(item.get("corrected_text", "")).strip()
        is_active = bool(item.get("is_active", True))
        if not raw or not corr or raw == corr or len(raw) > 120 or len(corr) > 120:
            continue
        try:
            count = max(1, int(item.get("count", 1)))
        except (TypeError, ValueError):
            count = 1
        normalized.append(
            {
                "raw_text": raw,
                "corrected_text": corr,
                "count": count,
                "is_active": is_active,
            }
        )
    return normalized


class StatelessLearningEngine:
    """Thread-safe per-request correction engine implementing LearningEngine semantics without SQLite."""

    def __init__(self, user_rules: Optional[List[Dict[str, Any]]] = None) -> None:
        self.user_rules = normalize_user_rules(user_rules or [])

        # Built-in cursive fixes first, then default yeshiva abbreviations, then active user overrides.
        rule_map: Dict[str, str] = dict(BUILTIN_CURSIVE_FIXES)
        for raw, corr in DEFAULT_CORRECTIONS:
            if raw and corr and raw != corr:
                rule_map[raw] = corr

        known_targets = set(TORAH_CURSIVE_TARGETS)
        for word in DEFAULT_VOCABULARY:
            if word and len(word) >= 4:
                known_targets.add(word)

        for rule in self.user_rules:
            if not rule.get("is_active", True):
                continue
            raw = rule["raw_text"]
            corr = rule["corrected_text"]
            rule_map[raw] = corr
            for hw in re.findall(r"[\u0590-\u05FF]{4,}", corr):
                known_targets.add(hw)

        self.rule_map = rule_map
        self.known_targets = known_targets

        if rule_map:
            sorted_keys = sorted(rule_map.keys(), key=len, reverse=True)
            alt_pattern = "|".join(re.escape(k) for k in sorted_keys)
            self._boundary_pattern = re.compile(
                r'(?<![\u0590-\u05FF0-9\'"])(?:' + alt_pattern + r')(?![\u0590-\u05FF0-9\'"])'
            )
        else:
            self._boundary_pattern = None

    def _resolve_cursive_swap(self, word: str) -> Optional[str]:
        """Resolve single-character cursive confusions against known Torah targets."""
        if len(word) < 4 or word in SAFE_COMMON_HEBREW or word in self.known_targets:
            return None

        if word.endswith("ן") and len(word) >= 5:
            stem = word[:-1]
            if stem in self.known_targets or stem in SAFE_COMMON_HEBREW:
                return stem
            if stem in BUILTIN_CURSIVE_FIXES:
                return BUILTIN_CURSIVE_FIXES[stem]

        matches = set()
        for idx, ch in enumerate(word):
            swaps = CURSIVE_CHAR_SWAPS.get(ch)
            if not swaps:
                continue
            for alt in swaps:
                cand = word[:idx] + alt + word[idx + 1 :]
                if cand in self.known_targets:
                    matches.add(cand)
        if len(matches) == 1:
            return next(iter(matches))
        return None

    def apply_corrections(self, text: str) -> Tuple[str, List[Tuple[str, str]]]:
        """Apply single-pass rule replacements and cursive swap resolution."""
        if not text:
            return "", []

        applied: List[Tuple[str, str]] = []
        result = text

        if self._boundary_pattern is not None:
            def _repl_cb(m: re.Match[str]) -> str:
                matched = m.group(0)
                target = self.rule_map[matched]
                applied.append((matched, target))
                return target

            result = self._boundary_pattern.sub(_repl_cb, result)

        def _cursive_cb(m: re.Match[str]) -> str:
            tok = m.group(0)
            fixed = self._resolve_cursive_swap(tok)
            if fixed and fixed != tok:
                applied.append((tok, fixed))
                return fixed
            return tok

        result = re.sub(
            r'(?<![\u0590-\u05FF\'"])[\u0590-\u05FF]{4,}(?![\u0590-\u05FF\'"])',
            _cursive_cb,
            result,
        )

        return result, applied


def extract_corrections(raw_text: str, corrected_text: str) -> List[Dict[str, str]]:
    """Extract candidate (raw_text, corrected_text) replacement pairs from proofreading edits."""
    raw_tokens = [w for w in re.split(r'(\s+|[.,:;!?"\'\(\)\[\]])', raw_text or "") if w and not w.isspace()]
    corr_tokens = [w for w in re.split(r'(\s+|[.,:;!?"\'\(\)\[\]])', corrected_text or "") if w and not w.isspace()]

    matcher = difflib.SequenceMatcher(None, raw_tokens, corr_tokens)
    candidates: List[Dict[str, str]] = []
    seen = set()

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            raw_sub = " ".join(raw_tokens[i1:i2]).strip()
            corr_sub = " ".join(corr_tokens[j1:j2]).strip()
            if 0 < len(raw_tokens[i1:i2]) <= 3 and 0 < len(corr_tokens[j1:j2]) <= 3:
                if raw_sub and corr_sub and raw_sub != corr_sub:
                    pair = (raw_sub, corr_sub)
                    if pair not in seen:
                        seen.add(pair)
                        candidates.append({"raw_text": raw_sub, "corrected_text": corr_sub})

    return candidates
