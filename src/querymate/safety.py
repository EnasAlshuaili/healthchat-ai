"""Safety & Scope Router, prototype v0.1.0 (see docs/SAFETY_ROUTER.md).

Runs before topic matching and retrieval. Returns exactly one route plus reason
codes (fixed rule names; never user text). Only the PROCEED route allows topic
matching, and PROCEED is returned only when no risk rule fired AND the question
contains health-related vocabulary. Uncertainty never defaults to PROCEED, and any
internal error returns SAFE_FALLBACK.

This is a keyword/rule prototype, NOT a clinical triage system. It does not detect
every emergency, crisis, diagnosis, or dosage request, cannot tell whether anyone
is safe, and has not been clinically validated (D-07, D-11, 07_Safety §4). It
produces route categories only: no response wording, emergency numbers, helplines,
diagnoses, treatments, or medication instructions (P6). It never reads the dataset.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum

from querymate import audit, cleaning, config

# v0.1.0: rules frozen before the Validation baseline (docs/safety_router_rules_v0.1.0.json).
# v0.1.1: Validation-informed changes (D-17 amendment); see docs/SAFETY_ROUTER.md.
ROUTER_VERSION = "0.1.1"
MAX_INPUT_CHARS = config.MAX_INPUT_CHARS  # ordinary length limit (1,000 by default)
SCAN_LIMIT_CHARS = 20_000                 # long inputs: crisis/emergency scan covers this prefix only


class Route(str, Enum):
    """Router outcomes. Only PROCEED allows topic matching."""

    PROCEED = "proceed"
    INVALID_INPUT = "invalid_input"
    EMERGENCY = "emergency_guidance"
    CRISIS = "crisis_guidance"
    DIAGNOSIS = "decline_diagnosis_refer"
    DOSAGE = "decline_dosage_refer"
    OUT_OF_SCOPE = "out_of_scope_fallback"
    SAFE_FALLBACK = "safe_fallback"


@dataclass(frozen=True)
class PreCheckResult:
    """Decision handed to the Topic Matcher gate."""

    route: Route
    checked_by: str


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    reason_codes: tuple[str, ...]  # fixed rule names in priority order; no user text
    router_version: str = ROUTER_VERSION


def _audit(group: str, name: str) -> str:
    return audit.PATTERN_GROUPS[group][name]


# --- Frozen rule lists (v0.1.0). Patterns run on lowercased, cleaned text. ----------------

CRISIS_RULES = {
    "self_harm_or_suicide": _audit("emergency_related_questions", "self_harm_or_suicide"),
    "wants_to_die": (r"\bwant(?:s|ed)? to die\b|\bwish (?:i|he|she|they) (?:was|were) dead\b"
                     r"|\bbetter off dead\b|\bno reason to live\b|\bend it all\b"
                     r"|\bdo(?:n'?t| not) want to (?:live|be alive|wake up)\b"),
    "hurting_self": (r"\b(?:hurt|hurting|harm|harming|cut|cutting|burn|burning) "
                     r"(?:myself|himself|herself|themselves|themself)\b|\bkill (?:themselves|themself)\b"),
    # v0.1.1: no longer the reused audit pattern; "food poisoning" and poison ivy/oak/sumac excluded.
    # Other rules still fire independently (e.g. vomiting blood, swallowed rat poison).
    "overdose_or_poisoning": r"\boverdos\w*|(?<!food )\bpoison(?:s|ed|ing|ous)?\b(?! (?:ivy|oak|sumac)\b)",
    # v0.1.1 typo variants (small explicit list; not comprehensive).
    "suicide_typo_variants": r"\b(?:sucide|suicde|suiside|sucidal|suicdal)\w*|\bkill my self\b(?!-)",
    "overdose_typo_variants": r"\bover dos(?:e|ed|es|ing)\b",
    "took_too_many": (r"\b(?:took|taken|swallowed|ate|had) (?:too many|too much|a lot of|lots of"
                      r"|all (?:of )?(?:my|the|his|her|their)|a whole|an entire)\b"
                      r"|\bwhole (?:bottle|pack|packet|box|strip|tub) of\b"),
    "swallowed_harmful_substance": (r"\b(?:drank|drunk|swallowed|ate|ingested) (?:some )?"
                                    r"(?:bleach|disinfectant|antifreeze|detergent|cleaning (?:fluid|product)"
                                    r"|weed ?killer|pesticide|rat poison|batter(?:y|ies))\b"),
    "immediate_danger": (r"\b(?:going|trying|threaten\w*) to (?:kill|hurt|attack) (?:me|him|her|them|us|myself)\b"
                         r"|\bin (?:immediate )?danger\b"),
}

EMERGENCY_RULES = {
    **{name: _audit("emergency_related_questions", name)
       for name in ["chest_pain", "breathing_difficulty", "stroke_like_symptoms", "severe_allergic_reaction",
                    "severe_bleeding", "loss_of_consciousness", "seizure"]},
    "not_breathing_or_unresponsive": (r"\b(?:not|stopped) breathing\b|\bunresponsive\b|\bwon'?t wake\b"
                                      r"|\bcan'?t (?:be )?wake?n?\b|\bcollaps\w*|\bblue lips\b|\bchok(?:e|es|ed|ing)\b"),
    "airway_swelling": r"\b(?:tongue|throat|lips?|face) (?:is |are )?(?:swelling|swollen|swelled)\b",
    "heart_attack": r"\bheart attack\b|\bcardiac arrest\b",
    "sudden_severe": r"\bworst headache\b|\bsudden(?:ly)? (?:and )?severe\b|\bsevere (?:pain|burn|burns|bleed\w*)\b",
    # v0.1.1: "emergency contraception" excluded; other emergency rules still fire independently.
    "emergency_help_terms": r"\bemergenc(?:y|ies)\b(?! contracepti)|\bambulance\b|\b(?:911|999|112)\b",
    # v0.1.1 typo variants (small explicit list; not comprehensive).
    "chest_pain_typo_variants": r"\b(?:chesst|chst|chets|cheast) +(?:pain|pains|pian)\b|\bchest +pian\b",
    "breathing_typo_variants": (r"\b(?:can'?t|cannot|unable to) +(?:breath|breth|brethe|breate|brathe)\b"
                                r"|\b(?:difficulty|dificulty|trouble|hard) +(?:to +)?(?:breating|brething|breathin|breath)\b"
                                r"|\bshort(?:ness)? +of +breth\b"),
    "unconscious_typo_variants": r"\b(?:unconcious|unconsious|uncoscious)\b|\bpast out\b",
    "seizure_typo_variants": r"\b(?:siezures?|sezures?|seizur)\b",
}

DOSAGE_RULES = {
    "dose_amount": _audit("medical_risk_indicators", "dose_amount"),
    "dosing_frequency": _audit("medical_risk_indicators", "dosing_frequency"),
    # v0.1.1: idiomatic "a dose of sunshine/fresh air/..." excluded.
    "dose_words": (r"\bdos(?:e|es|age|ages|ing)\b(?! of (?:sunshine|sunlight|fresh air|nature|laughter|reality"
                   r"|humou?r)\b)|\bmilligrams?\b|\bmicrograms?\b"),
    "how_much_to_take": r"\bhow (?:much|many)\b[^.?!]{0,60}\b(?:take|taking|give|giving|use|using)\b",
    "choose_a_medicine": (r"\b(?:what|which) (?:medicine|medication|drug|antibiotic|pill|tablet|painkiller"
                          r"|cream|inhaler|supplement)s? (?:should|can|could|do|to|would|will)\b"
                          r"|\bwhat (?:should|can|could) (?:i|we|he|she|they) (?:take|give|use)\b"),
    "prescribing": (r"\bprescribe (?:me|him|her|them|us|something|anything)\b|\bprescription for\b"
                    r"|\b(?:give|write|get|need) (?:me )?(?:a |an )?prescription\b"
                    r"|\bwhat (?:would|should|could|can|do) (?:you|a doctor|doctors) (?:usually )?prescribe\b"),
    "can_i_take": (r"\b(?:can|could|should|may) (?:i|we|he|she|they|my \w+) (?:take|give|use|have)\b"
                   r"[^.?!]{0,40}\b(?:medicine|medication|meds|tablets?|pills?|capsules?|drugs?|syrup|insulin"
                   r"|inhaler|antibiotics?|painkillers?|supplements?)\b"
                   r"|\bis it (?:safe|ok|okay|fine) to (?:take|give|use|mix|combine)\b"),
    "combine_medicines": (r"\b(?:mix|mixing|combine|combining|together with|alongside)\b[^.?!]{0,40}"
                          r"\b(?:medicines?|medications?|meds|tablets?|pills?|drugs?|antibiotics?|painkillers?"
                          r"|supplements?|alcohol)\b"),
    "stop_or_change_medicine": (_audit("medical_risk_indicators", "stop_medication_language") +
                                r"|\b(?:stop|stopping|quit|quitting|skip|skipping|double|doubling|halve|halving"
                                r"|increase|increasing|decrease|decreasing|reduce|reducing|lower|lowering"
                                r"|change|changing|switch|switching|come off|coming off)\b[^.?!]{0,30}"
                                r"\b(?:medicines?|medications?|meds|tablets?|pills?|insulin|inhalers?"
                                r"|antidepressants?|antibiotics?|treatment)\b"),
    "named_medicine_with_take": (r"(?:" + _audit("medical_risk_indicators", "medication_name") + "|"
                                 + _audit("medical_risk_indicators", "antibiotic_mention") + r")"
                                 r"[^.?!]{0,40}\b(?:take|taking|give|giving|use|using)\b"
                                 r"|\b(?:take|taking|give|giving|use|using)\b[^.?!]{0,40}(?:"
                                 + _audit("medical_risk_indicators", "medication_name") + "|"
                                 + _audit("medical_risk_indicators", "antibiotic_mention") + ")"),
}

DIAGNOSIS_RULES = {
    "do_i_have": (r"\b(?:do|does|did) (?:i|you think i|we|he|she|they|my \w+) (?:have|has|had)\b(?! to\b)"
                  r"|\bhave (?:i|you) got\b|\bhas (?:he|she|my \w+) got\b|\bam i (?:sick|ill|diabetic|anaemic|anemic)\b"),
    "whats_wrong_with_me": r"\bwhat(?:'s| is) wrong with (?:me|my|him|her|them)\b",
    "is_it_x_or_y": r"\b(?:is|was) (?:it|this|that) (?:a |an )?\w+(?: \w+)? or (?:a |an )?\w+",
    "could_it_be": r"\b(?:could|can|might|would) (?:it|this|that) be\b",
    "diagnose_words": r"\bdiagnos\w*",
    "what_condition_is_it": (r"\bwhat (?:infection|condition|disease|illness|rash|lump|problem|virus|allergy) "
                             r"(?:is|do|does|did|have|has|could|might)\b"),
    # v0.1.1 (Validation-informed): up to 4 words between "is this/that/my" and the condition word,
    # excluding "is", "are", "that" so "is this true that ... is bad" does not fire.
    "is_this_serious": (r"\bis (?:this|that|my) (?:(?!is\b|are\b|that\b)\w+ ){0,4}"
                        r"(?:serious|cancer\w*|tumou?rs?|malignant|dangerous|normal|bad|infected|broken)\b"
                        r"|\bis it (?:serious|cancer|dangerous|malignant)\b"),
    # v0.1.1 (Validation-informed): requests to confirm or rule out something about a person.
    "confirm_or_rule_out": (r"\b(?:confirm|rule out|verify)\b[^.?!]{0,80}"
                            r"\b(?:i|i'm|me|my|this|he|she|they|his|her|him|them)\b"),
    # v0.1.1 (Validation-informed): a body finding asked about as a condition. Conservative: also catches
    # benign/general wording ("is this patch of dry skin normal?") - documented over-restriction.
    "personal_finding_condition": (r"\b(?:this|a|my|the) (?:lump|bump|mole|spot|growth|swelling|lesion|mark|patch"
                                   r"|cyst|nodule)s?\b[^.?!]{0,60}\b(?:cancer\w*|tumou?rs?|malignant|benign|serious"
                                   r"|dangerous|infected|normal|worr\w*)\b"),
    "my_results": (r"\b(?:my|his|her|these|our) (?:\w+ )?(?:test |blood |lab )?(?:results?|readings?|levels?|numbers?)\b"
                   r"[^.?!]{0,40}\b(?:mean|normal|high|low|bad|good|worry|ok|okay)\b"),
}

SAFE_FALLBACK_RULES = {
    "override_safety": (r"\bignore (?:all |any |your |the |previous |prior |these )*(?:rules|instructions|guidelines"
                        r"|safety|restrictions|policies|warnings)\b|\bjailbreak\b|\bdeveloper mode\b"
                        r"|\bwithout (?:any )?(?:warnings?|disclaimers?|restrictions|safety)\b"
                        r"|\bno (?:disclaimers?|restrictions|warnings)\b"),
    "act_as_clinician": (r"\b(?:pretend|act|behave|roleplay|role-play)\b[^.?!]{0,20}\b(?:doctor|physician|nurse"
                         r"|pharmacist|surgeon|clinician|gp)\b|\byou are (?:a |my )?(?:doctor|physician|nurse|pharmacist)\b"),
    "demand_certainty": (r"\bguarantee\w*|\b100 ?%|\bone hundred percent\b|\bpromise (?:me|that)\b"
                         r"|\b(?:completely|totally|absolutely|100 percent) (?:sure|certain)\b|\bfor (?:sure|certain)\b"),
    "medical_documents": (r"\b(?:sick note|doctor'?s note|medical (?:certificate|note|report|letter|record))\b"
                          r"|\bfit note\b"),
    "replace_treatment": (r"\binstead of (?:my |the |his |her |their |taking )?(?:prescribed |prescription )?"
                          r"(?:medicines?|medications?|meds|treatment|insulin|chemo\w*|tablets?|inhalers?|antibiotics?)\b"),
    "someone_elses_records": (r"\b(?:someone else'?s|another person'?s|(?:my |his |her )?(?:neighbou?r|friend|ex|boss"
                              r"|colleague|coworker)'?s?) (?:medical |health )?(?:records?|charts?|files?|history)\b"
                              r"|\baccess (?:to )?(?:\w+ )?(?:medical|health) records?\b"),
    "dangerous_substance": r"\b(?:bleach|disinfectant|turpentine|kerosene|chlorine dioxide|antifreeze)\b",
}

OUT_OF_SCOPE_RULES = {
    "animal_or_veterinary": (r"\b(?:dogs?|puppy|puppies|cats?(?! scan)|kittens?|pets?(?! scan)|horses?|rabbits?"
                             r"|hamsters?|guinea pigs?|parrots?|budgies?|goldfish|cows?(?!'?s? milk)|goats?(?!'?s? milk)|sheep"
                             r"|chickens?|vets?|veterinar\w*)\b"),
    # v0.1.1 (Validation-informed): health-adjacent money/admin questions are not health education.
    "non_clinical_finance_or_admin": (r"\b(?:insurance|insurers?|premiums?|deductibles?|co-?pays?|billing|bills?"
                                      r"|invoices?|refunds?|reimburs\w*|invest\w*|stocks?|shares (?:in|of)"
                                      r"|mortgages?|loans?|tax(?:es)?)\b"),
}

# Health allow-list (P1). Presence is necessary but never sufficient for PROCEED.
HEALTH_VOCABULARY = (
    r"\b(?:health\w*|medic\w*|symptoms?|signs? of|pain\w*|ache\w*|aching|sore|fever\w*|temperature|cough\w*"
    r"|colds?|flu|influenza|infect\w*|virus\w*|viral|bacteri\w*|germs?|vaccin\w*|immun\w*|sleep\w*|insomnia"
    r"|tired\w*|fatigue|diet\w*|eat\w*|food|nutrition\w*|fib(?:re|er)|vitamins?|minerals?|iron|calcium|exercis\w*"
    r"|physical(?:ly)? activ\w*|fitness|weight|obes\w*|drink\w* (?:more |enough )?water|water intake|fluids?"
    r"|hydrat\w*|dehydrat\w*|thirst\w*|blood|cholesterol|hdl|ldl|heart\w*|lungs?|breath\w*|asthma\w*|allerg\w*"
    r"|hay ?fever|pollen|sneez\w*|migraines?|headaches?|stomach|heartburn|reflux|stomach acid|indigestion|digest\w*"
    r"|bowel\w*|constipat\w*|diarrh\w*|nause\w*|vomit\w*|urin\w*|bladder|kidneys?|liver|skin|rash\w*|eczema"
    r"|sun(?:burn\w*|screen\w*|light|shine|block|cream|bed|beds)?|moles?|diabet\w*|glucose|blood sugar|insulin"
    r"|an(?:a)?emi\w*|hygiene|hand ?wash\w*|wash\w* (?:my |your |our )?hands|soap|saniti[sz]\w*|diseases?"
    r"|illness\w*|ill|sick\w*|medical conditions?|health conditions?|blood tests?|medical tests?|lab tests?|scans?"
    r"|x-?rays?|pharmac\w*|medicine labels?|leaflets?|tablets?|pills?|medicines?|medications?|drugs?|body"
    r"|muscles?|bones?|joints?|eyes?|ears?|nose"
    r"|throat|teeth|tooth|dental|stress\w*|anxi\w*|depress\w*|mental|wellbeing|well-being|pregnan\w*|doctors?"
    r"|nurses?|gp|clinic\w*|hospital\w*|wounds?|cuts?|burns?|bruis\w*|swell\w*|itch\w*|smok\w*|alcohol|caffeine"
    r"|coffee|hormon\w*|thyroid|cancer\w*|tumou?rs?|stroke|seizures?|injur\w*"
    r"|contracepti\w*|poison (?:ivy|oak|sumac))\b"  # v0.1.1 additions
)

# Emergency framing (P2): recorded as a reason code only; never changes the route.
GENERAL_FRAMING = (r"^(?:what|which|how|why|when|are|is|can|do|does)\b[^.?!]{0,40}"
                   r"\b(?:signs?|symptoms?|causes?|recogni[sz]e|spot|tell|happens|is an?|are)\b")
PERSONAL_OR_CURRENT = (r"\b(?:i|i'm|im|i've|ive|i'd|me|my|mine|we|we're|us|our)\b|\bright now\b|\bcurrently\b"
                       r"|\bat the moment\b|\bjust (?:now|started|happened)\b|\btoday\b|\btonight\b"
                       r"|\b(?:he|she|they)(?:'s|'re| is| are| has| have| can'?t| cannot| won'?t| just)\b")

RULE_GROUPS = [
    (Route.CRISIS, "crisis", CRISIS_RULES),
    (Route.EMERGENCY, "emergency", EMERGENCY_RULES),
    (Route.DOSAGE, "dosage", DOSAGE_RULES),
    (Route.DIAGNOSIS, "diagnosis", DIAGNOSIS_RULES),
    (Route.SAFE_FALLBACK, "safe_fallback", SAFE_FALLBACK_RULES),
    (Route.OUT_OF_SCOPE, "out_of_scope", OUT_OF_SCOPE_RULES),
]
URGENT_ROUTES = (Route.CRISIS, Route.EMERGENCY)

_COMPILED = [(route, prefix, {name: re.compile(p) for name, p in rules.items()})
             for route, prefix, rules in RULE_GROUPS]
_HEALTH = re.compile(HEALTH_VOCABULARY)
_GENERAL = re.compile(GENERAL_FRAMING)
_PERSONAL = re.compile(PERSONAL_OR_CURRENT)

# Every reason code the router can emit (fixed strings; no user text).
REASON_CODES = frozenset(
    {f"{prefix}:{name}" for _, prefix, rules in RULE_GROUPS for name in rules}
    | {"input:not_text", "input:empty", "input:too_long", "scope:no_health_vocabulary",
       "scope:health_vocabulary_no_risk_rule", "framing:personal_or_current", "framing:general_question",
       "framing:unclear", "router:error"}
)


def rules_payload() -> str:
    """Canonical JSON of every rule pattern and setting (same format since v0.1.0)."""
    payload = {"version": ROUTER_VERSION, "max": MAX_INPUT_CHARS, "scan": SCAN_LIMIT_CHARS,
               "groups": [[r.value, p, rules] for r, p, rules in RULE_GROUPS],
               "health": HEALTH_VOCABULARY, "general": GENERAL_FRAMING, "personal": PERSONAL_OR_CURRENT}
    return json.dumps(payload, sort_keys=True)


def rules_fingerprint() -> str:
    """SHA-256 of `rules_payload()`, to show the rules of a version were frozen (P9)."""
    return hashlib.sha256(rules_payload().encode("utf-8")).hexdigest()


def _matches(text: str) -> dict[Route, list[str]]:
    hits: dict[Route, list[str]] = {}
    for route, prefix, rules in _COMPILED:
        names = [f"{prefix}:{n}" for n, rx in rules.items() if rx.search(text)]
        if names:
            hits[route] = names
    return hits


def _framing(text: str) -> str:
    if _PERSONAL.search(text):
        return "framing:personal_or_current"
    if _GENERAL.search(text):
        return "framing:general_question"
    return "framing:unclear"


def _route(query: object) -> RouteDecision:
    if not isinstance(query, str):
        return RouteDecision(Route.INVALID_INPUT, ("input:not_text",))
    text = cleaning.clean_text(query[:SCAN_LIMIT_CHARS]).lower()
    if not text:
        return RouteDecision(Route.INVALID_INPUT, ("input:empty",))

    hits = _matches(text)
    codes = [c for route, _, _ in RULE_GROUPS for c in hits.get(route, [])]
    if any(r in hits for r in URGENT_ROUTES):
        codes.append(_framing(text))

    too_long = len(cleaning.normalize_whitespace(query)) > MAX_INPUT_CHARS
    if too_long:
        # P4: urgent signals first; otherwise the ordinary length rejection.
        codes.append("input:too_long")
        for route in URGENT_ROUTES:
            if route in hits:
                return RouteDecision(route, tuple(codes))
        return RouteDecision(Route.INVALID_INPUT, tuple(codes))

    for route, _, _ in RULE_GROUPS:  # fixed priority order (P5)
        if route in hits:
            return RouteDecision(route, tuple(codes))
    if not _HEALTH.search(text):
        return RouteDecision(Route.OUT_OF_SCOPE, ("scope:no_health_vocabulary",))
    return RouteDecision(Route.PROCEED, ("scope:health_vocabulary_no_risk_rule",))


def route(query: object) -> RouteDecision:
    """Route one question. Any internal error returns SAFE_FALLBACK, never PROCEED."""
    try:
        decision = _route(query)
        if not isinstance(decision.route, Route) or not set(decision.reason_codes) <= REASON_CODES:
            raise RuntimeError("router produced an undefined route or reason code")
        return decision
    except Exception:  # noqa: BLE001 - fail safe (03_System_Design §9, R-10)
        return RouteDecision(Route.SAFE_FALLBACK, ("router:error",))


def to_precheck(decision: RouteDecision) -> PreCheckResult:
    """The gate input for TopicMatcher.match_after_precheck."""
    if not isinstance(decision, RouteDecision):
        raise TypeError("A RouteDecision from safety.route is required.")
    return PreCheckResult(decision.route, checked_by=f"safety_router {decision.router_version}")
