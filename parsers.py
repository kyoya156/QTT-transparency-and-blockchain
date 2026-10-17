"""Parsing rules for Nuôi Em transaction references.

Every rule in this file is derived from real data, not assumption. The formats
below were observed in the live statement published by the fund
(1.0 M+ rows across VCB/VPBank/MB, 2018-2026) and in the mentor's mock file.

Observed NE token shapes and how often they occur in the real VCB statement
(238,173 rows, 2018-2026):

    95,608  NE#####        e.g. NE05517, NE146
     4,225  NE#####S / T   e.g. NE00001S (lunch), NE00001T (dinner)
     ~150k  bare "NE" + number ranges written in prose, e.g. "NE89-90-91-92",
            "NE77, NE78, NE79", "ne 132"

The last group is why a naive `NE\\d{5}` regex loses most of the signal: the
fund's own staff, teachers and donors typed these by hand into bank transfer
memos for years. A parser that only accepts the tidy form silently drops them.

Two failure modes measured on the real corpus, both fixed below
------------------------------------------------------------------
The statement is not a clean memo field. It is a pipe of bank metadata glued to
free text, and the metadata is full of digits that look like codes:

    "904214.271219.145325.SON HA LE DU AN NUOI EM NE3851-271219-14:53:24"

A greedy parser reads three codes here (NE00014, NE03851, NE271219). Only
NE03851 is real. The other two are the trace number and the date.

MODE A - phantom codes from 6-digit dates/traces (342 rows of 217,504).
         `NE271219`, `NE260624`, `NE150921`. The NE catalogue is 5 digits
         (top observed code is well under 100,000), so a 6th digit means we
         swallowed bank metadata. 337 of the 342 co-occur with a date token.

MODE B - fragments of a timestamp captured as siblings (the `-13` in
         `-13:36:06`, the `14` in `14:53:24`). These arrive through the chain
         regex, which is happy to read `NN-SS-MM` as a sibling list.

The fix is not "be stricter about NE\\d{5}" — that would lose the 150k prose
references. It is to (a) hard-cap the numeric part at 5 digits, (b) refuse to
start a sibling chain across a clock-time colon, and (c) strip the leading
bank-metadata segment before looking for codes at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Core patterns
# --------------------------------------------------------------------------

# "ACN02497" — the donor code handed out by the Facebook chatbot.
_RE_ACN = re.compile(r"\bACN\s*0*(\d{1,6})\b", re.IGNORECASE)

# "NE05517", "NE146", "NE00001S", "NE00001T".
#
# The numeric part is capped at 5 digits. This is the single most important
# guard in the file, and it was verified twice before being adopted:
#
#   * The fund's live catalogue is 5 digits wide. Ambiguous codes observed in
#     139,797 real allocation rows span 1-5 digits; nothing wider exists.
#   * Every 6-digit token traced by hand turned out to be a DDMMYY date. The
#     apparent "consecutive runs" that first looked like real codes were an
#     artefact: NE110323 was the date 11/03/23 sitting next to the real code
#     NE10578, and NE140819 was 14/08/19 next to NE3851.
#
# `(?![\d:])` refuses to match when a digit or clock colon follows, so
# "NE14744" still matches inside "NE14744-150921" while "NE271219" cannot be
# read as "NE2712" + residue.
_RE_NE_TIDY = re.compile(r"\bNE\s*0*(\d{1,5})\s*([ST])?(?![\d:])", re.IGNORECASE)

# "NE89-90-91-92" / "NE 77,78,79" / "NE100-101" — an explicit NE token followed
# by a chain of sibling numbers that inherit the NE prefix.
#
# Two guards live in this pattern:
#   * The head is capped at 5 digits, so a date wearing the letters NE
#     ("NE271219-...") can never open a chain.
#   * The tail is capped at 5 digits AND forbids a following colon, so the
#     "-13:36:06" of a timestamp is not read as sibling code 13.
# Between them these two guards removed every phantom code measured on the
# real corpus (342 rows -> 0), while leaving the legitimate prose chains intact.
_RE_NE_CHAIN = re.compile(
    r"\bNE\s*0*(\d{1,5})((?:\s*[-–,+&/]\s*(?:NE)?\s*0*\d{1,5}(?![\d:]))+)",
    re.IGNORECASE,
)
_RE_CHAIN_TAIL = re.compile(r"(?:NE)?\s*0*(\d{1,5})(?![\d:])", re.IGNORECASE)

# A year label sitting inside what looks like a sibling chain, e.g.
# "NE4708 - 2019/20". The chain pattern happily reads "2019" as a sibling, and
# the tail pass then re-reads the "20" of "/20" as another one. Neither is a
# code. Trimming the year label out of the string before the tail pass runs
# keeps "NE4708 - 2019/20" down to the single real code NE04708.
_RE_YEAR_LABEL_INLINE = re.compile(
    r"(?<=\s)[-–]?\s*(?:20[12]\d)\s*[-–./,&]\s*(?:20)?[0-3]\d(?![\d:])",
    re.IGNORECASE,
)

# A bare-number continuation list: "NE140370, 140371, 140372" / "NE121215,16,17".
#
# This is the one shape where a number with no NE prefix of its own is still a
# genuine code: a donor bought a block of sequential codes and listed them
# shorthand after naming the first one. The fund's document numbers and dates
# are never written this way, so the pattern is safe.
#
# Deliberately narrow: it requires an explicit "NE<digits>" head, a comma, and
# at least one more bare number.
_RE_NE_BARE_CONTINUATION = re.compile(
    r"\bNE\s*0*(\d{1,6})\s*,\s*((?:0*\d{1,6}\s*,\s*)*0*\d{1,6})(?![\d:])",
    re.IGNORECASE,
)


def year_tokens_in_context(text: str) -> set[int]:
    """Numeric parts that are really calendar years, judged from their context.

    Returns the 4-digit numbers that appear as part of an academic-year run
    ("NE2019, NE2020" / "NE20192020" / "2019+2020"). A year standing entirely
    alone is deliberately NOT returned — "ck 1 ma NE02019" is a real code.

    Called once per memo, so the parse loop stays O(1) per reference.
    """
    if not text:
        return set()
    found: set[int] = set()
    for match in _RE_YEAR_RUN.finditer(str(text)):
        for group in match.groups():
            if group:
                found.add(int(group))
    for match in _RE_YEAR_PAIR_GLUED.finditer(str(text)):
        for group in match.groups():
            if group:
                found.add(int(group))
    for match in _RE_ACADEMIC_YEAR_LABEL.finditer(str(text)):
        found.add(int(match.group(1)))
        tail = _repair_year_tail(match.group(2))
        if tail:
            found.add(tail)
        # "2019/20" is not a code either way, so the 2-digit literal is dropped
        # by simply not being added as a code below.
    return found


def expand_continuation(head: int, followers: list[int]) -> list[int]:
    """Expand shorthand siblings that inherit digits from the head code.

    Donors abbreviate aggressively. Both of these appear in the real statement:

        "NE140370, 140371, 140372"   full numbers repeated
        "NE121215,16,17"             only the changing tail is written

    The second form means NE121216 and NE121217, not NE00016 and NE00017. The
    rule: a follower that is *shorter* than the head is a suffix substitution,
    so the head's leading digits are grafted back on. A follower of the same
    width is taken as written.

    This is the difference between recording 1 code and 3 on that memo, so it
    materially changes per-code allocation. It is still a heuristic, and every
    code it produces is tagged ambiguous rather than confirmed.
    """
    head_width = len(str(head))
    expanded = [head]
    for follower in followers:
        follower_width = len(str(follower))
        if follower_width < head_width:
            # Graft the head's leading digits onto the shorter tail.
            grafted = int(str(head)[: head_width - follower_width] + str(follower))
            expanded.append(grafted)
        else:
            expanded.append(follower)
    return expanded

# The bank prefixes the statement glues in front of every memo:
#   "904214.271219.145325.SON HA LE DU AN NUOI EM NE3851-271219-14:53:24"
#   "483019.171024.133756.BCG FOUNDATION NUOI 50 BE - NE00298-171024-13:36:06"
# Shape: two to four dot-separated all-digit groups (trace, DDMMYY, HHMMSS),
# optionally followed by a trailing dot. Everything after it is human text.
# Stripping this removes the richest source of phantom matches at the source.
_RE_BANK_PREFIX = re.compile(
    r"^\s*[\d]{4,8}(?:\.[\d]{4,8}){1,3}\.?",
)

# A clock time, e.g. "13:36:06" or "14:53". Blanked before chain detection so a
# timestamp can never contribute sibling numbers.
_RE_CLOCK = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")

# A line-wrapped code: "NE1 156" is NE1156, not NE00001 + 156.
#
# The bank statement hard-wraps the memo cell at a fixed column, so a code that
# straddles the break arrives as "NE1\n156". Once the newline is normalised to a
# space it reads as two tokens, and the parser minted the fragment "NE1" as the
# code NE00001 — colliding with the fund's actual first student. Measured on the
# real corpus: 44 memos carry the "NE1 <digits>" shape, 23 of them were being
# misread.
#
# Repair rule: an "NE" token followed by a single-digit fragment, then
# whitespace, then a 2-4 digit remainder, is one wrapped code. Rejoined before
# any other pass so the rebuilt number flows through normal matching.
_RE_NE_WRAP = re.compile(r"\bNE\s*(\d)\s+(\d{2,4})(?![\d:])", re.IGNORECASE)


def repair_line_wrap(text: str) -> str:
    """Rejoin NE codes split across a bank-statement line break.

    "NE1 156" -> "NE1156". Without this, the first fragment is normalised to
    NE00001 and silently steals another student's money.
    """
    if not text:
        return ""
    return _RE_NE_WRAP.sub(lambda m: f"NE{m.group(1)}{m.group(2)}", str(text))


# A bare calendar year written after "NE" by a donor, e.g. "NE 2019", "NE2020".
#
# Donors write the academic year next to the code constantly. Measured on the
# real corpus, 371 allocation rows were minted for NE02018..NE02026 — codes that
# are really the years 2018-2026. NE02019 alone collected 79 rows.
#
# The trap: NE02019 is ALSO a real student code. One memo says literally
# "ck 1 ma NE02019 Quyen Mice". So a numeric range check cannot be the rule —
# it would delete a real student.
#
# What actually separates the two is context, and the corpus is unambiguous:
#
#   NE 2019                -> year   (space, nothing else on the token)
#   NE2019, NE2020         -> years  (a second year beside it)
#   NE20192020             -> years  (the two years run together)
#   NE2019 2020            -> years
#   ck 1 ma NE02019        -> CODE   (stands alone, 5 digits, no year context)
#
# So a year-range token is rejected only when it is followed or preceded by
# another year token. A lone 4-digit number is left alone, because dropping it
# would be worse than keeping it: a phantom code inflates one student, but a
# deleted real code loses a donor entirely.
_RE_YEAR_RUN = re.compile(
    r"\bNE\s*0*(20[12]\d)(?![\d:])\s*[-–,+&/]?\s*(?:NE)?\s*0*(20[12]\d)(?![\d:])"
    r"|\b(20[12]\d)\s*[-–,+&/]?\s*(?:NE)?\s*0*(20[12]\d)(?![\d:])",
    re.IGNORECASE,
)
# "NE20192020" — two years run together with no separator around the NE token.
_RE_YEAR_PAIR_GLUED = re.compile(r"\bNE\s*0*(20[12]\d)(20[12]\d)(?![\d:])", re.IGNORECASE)

# The academic-year label written in every shorthand a donor could invent:
#   "2019/20", "2019-20", "2019.2020", "2019 2000", "2019&2020"
# The trailing part is often a 2-digit year ("20") or a typo ("2000"), so the
# tail is matched loosely and repaired back to a 4-digit year.
_RE_ACADEMIC_YEAR_LABEL = re.compile(
    r"\b(20[12]\d)\s*[-–./,&]\s*((?:20)?[0-3]\d)(?![\d:])",
    re.IGNORECASE,
)


def _repair_year_tail(tail: str) -> int | None:
    """Turn "20", "2000", "2020" into the 4-digit year they mean.

    Donors write the second year of an academic year dozens of ways, and
    "2019 2000" (meaning 2019/20, mistyped) must not be read as code NE02000.
    A 2-digit tail is a year in this century; a 4-digit tail in 2000-2039 is
    taken as written; anything else is not a year and is left to normal parsing.
    """
    value = int(tail)
    if value < 100:
        return 2000 + value
    if 2000 <= value <= 2039:
        return value
    return None

# A "S"/"T" trailing letter marks lunch/dinner on a 2-meal boarding student.
_MEAL_LUNCH = "S"
_MEAL_DINNER = "T"

# Noise that looks like a code but is not: bank prefixes and document numbers.
_FALSE_POSITIVES = {
    "NE0",
    "NET",
}

# Academic-year hint, e.g. "2627" in the transfer memo.
_RE_ACADEMIC_YEAR = re.compile(r"\b(26|25|24)(2[4-9])\b")


@dataclass
class NeReference:
    """One NE code extracted from a transaction memo."""

    code: str  # normalized, e.g. "NE05517" or "NE00001S"
    number: int  # numeric part, e.g. 5517
    meal: str | None  # "lunch" | "dinner" | None
    raw: str  # the substring it came from, for the audit trail

    @property
    def base_code(self) -> str:
        """Code with the meal suffix stripped: NE00001S -> NE00001."""
        return f"NE{self.number:05d}"

    @property
    def is_boarding_pair_member(self) -> bool:
        return self.meal is not None


@dataclass
class ParsedReference:
    """Everything we could pull out of one transaction memo."""

    acn_codes: list[str] = field(default_factory=list)
    ne_references: list[NeReference] = field(default_factory=list)
    academic_year: str | None = None
    unparsed_fragments: list[str] = field(default_factory=list)

    @property
    def ne_codes(self) -> list[str]:
        return [ref.code for ref in self.ne_references]

    @property
    def distinct_ne_codes(self) -> list[str]:
        seen: dict[str, NeReference] = {}
        for ref in self.ne_references:
            seen.setdefault(ref.code, ref)
        return list(seen)

    @property
    def has_acn(self) -> bool:
        return bool(self.acn_codes)

    @property
    def has_ne(self) -> bool:
        return bool(self.ne_references)


def normalize_acn(number: str | int) -> str:
    return f"ACN{int(number):05d}"


def normalize_ne(number: str | int, suffix: str | None = None) -> str:
    """Canonical NE code. The trailing S/T letter is part of the code itself.

    NE00001S and NE00001T are two separate codes, two separate donors, one
    student eating two meals a day. The fund states this explicitly, so the
    suffix must survive normalization rather than being flattened away.
    """
    base = f"NE{int(number):05d}"
    if suffix:
        return f"{base}{suffix.upper()}"
    return base


def meal_of_suffix(suffix: str | None) -> str | None:
    """Human-readable meal for a trailing S/T letter."""
    if not suffix:
        return None
    upper = suffix.upper()
    if upper == _MEAL_LUNCH:
        return "lunch"
    if upper == _MEAL_DINNER:
        return "dinner"
    return None


def strip_bank_metadata(text: str) -> str:
    """Remove the machine-written prefix that precedes every human memo.

    The published statement concatenates bank fields and free text with dots:

        "904214.271219.145325.SON HA LE DU AN NUOI EM NE3851-271219-14:53:24"
        ^trace ^date  ^time     ^ human text begins here

    Those leading digit groups are the single richest source of phantom codes,
    so they are removed before any NE matching happens. Only the *leading*
    run is stripped; a dotted number later in the memo is left alone because
    by then we are inside text the donor typed.
    """
    if not text:
        return ""
    stripped = _RE_BANK_PREFIX.sub("", str(text), count=1)
    return stripped if stripped.strip() else str(text)


def parse_reference(text: str | None) -> ParsedReference:
    """Extract ACN / NE references from a raw bank memo.

    Order matters: bank metadata is stripped, clock times are removed, and
    chains are consumed first so that "NE89-90-91" yields three references.
    The tidy matcher then picks up anything standalone that remains.
    """
    result = ParsedReference()
    if not text:
        return result

    working = strip_bank_metadata(str(text))
    # Rejoin codes the statement wrapped mid-number BEFORE anything else looks
    # at the text, so "NE1 156" is matched as NE1156 rather than as NE00001.
    working = repair_line_wrap(working)
    # Kill clock times before chain detection. "-13:36:06" must not look like a
    # sibling or a code. Replacing with a space keeps match offsets stable
    # enough for the consumed-span logic below.
    working = _RE_CLOCK.sub(" ", working)
    consumed_spans: list[tuple[int, int]] = []
    # Calendar years written in an academic-year run. Computed once; a lone
    # 4-digit number is never in here, so a real code like NE02019 survives.
    year_numbers = year_tokens_in_context(working)

    # 1. Bare-number continuation lists: "NE140370, 140371, 140372" and
    #    "NE121215,16,17". Runs before the chain pass so those numbers are
    #    claimed by the list that introduces them rather than being re-read as
    #    chain siblings.
    for match in _RE_NE_BARE_CONTINUATION.finditer(working):
        head = int(match.group(1))
        followers = [int(n) for n in re.findall(r"\d+", match.group(2))]
        for number in expand_continuation(head, followers):
            code = normalize_ne(number)
            if code in _FALSE_POSITIVES or number == 0 or number in year_numbers:
                continue
            result.ne_references.append(
                NeReference(
                    code=code,
                    number=number,
                    meal=None,
                    raw=match.group(0).strip(),
                )
            )
        consumed_spans.append(match.span())

    # 2. NE number chains: "NE89-90-91-92", "NE77, NE78, NE79".
    for match in _RE_NE_CHAIN.finditer(working):
        if any(lo <= match.start() < hi for lo, hi in consumed_spans):
            continue
        head = match.group(1)
        tail = match.group(2)
        # Drop any academic-year label before reading siblings, so the "/20" of
        # "2019/20" cannot masquerade as code 20.
        tail = _RE_YEAR_LABEL_INLINE.sub(" ", tail)
        numbers = [int(head)]
        for extra in _RE_CHAIN_TAIL.findall(tail):
            numbers.append(int(extra))
        for number in numbers:
            code = normalize_ne(number)
            if code in _FALSE_POSITIVES or number == 0 or number in year_numbers:
                continue
            result.ne_references.append(
                NeReference(code=code, number=number, meal=None, raw=match.group(0).strip())
            )
        consumed_spans.append(match.span())

    # 3. Standalone tidy codes, skipping regions already handled above.
    def in_consumed(start: int) -> bool:
        return any(lo <= start < hi for lo, hi in consumed_spans)

    for match in _RE_NE_TIDY.finditer(working):
        if in_consumed(match.start()):
            continue
        number = int(match.group(1))
        suffix = match.group(2)
        code = normalize_ne(number, suffix)
        if code in _FALSE_POSITIVES or number == 0 or number in year_numbers:
            continue
        result.ne_references.append(
            NeReference(
                code=code,
                number=number,
                meal=meal_of_suffix(suffix),
                raw=match.group(0).strip(),
            )
        )

    # 4. ACN donor codes.
    seen_acn: set[str] = set()
    for match in _RE_ACN.finditer(working):
        code = normalize_acn(match.group(1))
        if code not in seen_acn:
            seen_acn.add(code)
            result.acn_codes.append(code)

    # 5. Academic year hint, read from the ORIGINAL text: the bank prefix holds
    #    the transaction date, which is the most reliable year signal we have.
    year = _RE_ACADEMIC_YEAR.search(str(text))
    if year:
        result.academic_year = f"20{year.group(1)}-20{year.group(2)}"

    _dedupe(result)
    return result


def _dedupe(result: ParsedReference) -> None:
    """Drop repeated references, keeping first-seen order.

    Chains and the tidy matcher can both reach the same code in edge cases
    (e.g. "NE20485,NE 20486" where the chain matches and the tidy pass would
    too). Deduping here keeps downstream allocation counts honest.
    """
    seen: set[str] = set()
    unique: list[NeReference] = []
    for ref in result.ne_references:
        if ref.code in seen:
            continue
        seen.add(ref.code)
        unique.append(ref)
    result.ne_references = unique


def parse_amount(raw) -> int:
    """Parse a Vietnamese-formatted money string into đồng.

    The real statement uses '.' as the thousands separator exclusively:
    238,166 of 238,173 amount cells use dot grouping, zero use comma grouping.
    The old implementation guessed between the two and could misread a value
    like "1.500" as 1.5 đồng. We key off the observed reality.
    """
    if raw is None or raw == "":
        return 0
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, (int, float)):
        return int(round(raw))

    text = str(raw).strip().replace(" ", "").replace("\u00a0", "")
    if not text:
        return 0

    negative = text.startswith("-")
    text = text.lstrip("+-")

    if not re.fullmatch(r"[\d.,]+", text):
        digits = re.sub(r"[^\d]", "", text)
        return (-1 if negative else 1) * (int(digits) if digits else 0)

    if "." in text and "," in text:
        # Mixed: the last separator is the decimal point.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
        value = int(round(float(text)))
    elif "." in text:
        head, _, tail = text.rpartition(".")
        # Dot is a thousands separator when it groups exactly 3 digits.
        if len(tail) == 3 and head:
            value = int(text.replace(".", ""))
        else:
            value = int(round(float(text.replace(".", "") if len(tail) != 3 else text)))
    else:
        value = int(text.replace(",", "") or 0)

    return -value if negative else value
