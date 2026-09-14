# v1.1 | 14-Sep-2026 | is_english_text: check a generated answer before it becomes the slip.
# v1.0 | 13-Sep-2026 | WP5.1 reply-language policy from transcript, STT evidence and preference.
"""Decide the reply language of one turn: English or Malay.

design.md 6.4: STT provides language evidence, but the reply language comes
from the transcript, that evidence and the configured preference together.
Rules run in a fixed order and the first that decides wins (runbook 10.1
WP5.1, "Language policy"):

1. Transcript. Tokens found in a closed Malay list and a closed English list
   are counted; scheme names, numbers and discourse particles count for
   neither. With enough counted tokens, a clear Malay or English share
   decides.
2. Short utterance. At or below `SHORT_UTTERANCE_TOKENS` words the preference
   decides. Whisper's label is weakest on short clips, and Malay loanwords
   cluster there, so "CDC voucher macam mana?" must not turn English on a
   Malay-preference kiosk because Whisper said `en`.
3. STT evidence as a tie-breaker. Whisper `ms` or `id` gives Malay and `en`
   gives English, but only when the transcript holds at least one counted
   token of that language. STT never decides alone.
4. Preference, for everything else, including Chinese.

The word lists are deliberately small and closed. Nothing here calls a model.
"""

import re
from dataclasses import dataclass
from enum import Enum

from kaki_backend.contracts.ports import LanguageEvidence

ENGLISH = "en"
MALAY = "ms"
SUPPORTED_LANGUAGES = (ENGLISH, MALAY)

# At or below this many words, the preference outranks Whisper's label.
SHORT_UTTERANCE_TOKENS = 6
# Rule 1 needs at least this many counted tokens before a share can decide.
MIN_COUNTED_TOKENS = 3
MALAY_SHARE_FOR_MALAY = 0.60
MALAY_SHARE_FOR_ENGLISH = 0.40

# Whisper labels that count as Malay evidence. Whisper often hears Malay as
# Indonesian, and a Singapore kiosk never needs an Indonesian reply.
STT_MALAY_LABELS = frozenset({"ms", "id"})
STT_ENGLISH_LABELS = frozenset({"en"})

# Function words plus common service words heard at the kiosk.
MALAY_WORDS = frozenset("""
    saya aku anda awak kamu dia kita kami mereka nak hendak mahu mau boleh tak
    tidak bukan ada apa macam mana macamana bagaimana kenapa mengapa bila bilakah
    siapa berapa di ke dari daripada untuk dengan dan atau yang ini itu tu ni
    sini sana situ kat pada dalam juga lagi sudah dah belum akan sedang masih
    perlu kena harus patut cara tolong sila terima kasih baik ya tahu guna
    gunakan pakai mohon memohon tuntut bayar dapat dapatkan cetak cetakkan ulang
    ulangi sebut cakap sekali setiap tahun bulan hari esok semalam cuaca hujan
    baucar kad kedai klinik rumah isi duit wang bantuan langkah kata laluan bagi
    beri kah pun sahaja saja sangat lebih kurang mesti jika kalau sebab kerana
    jadi supaya nanti sekarang masa orang pergi datang beli buat lupa tukar
    resit bila-bila semua
""".split())

ENGLISH_WORDS = frozenset("""
    i me my mine you your he she it its we our they them their this that these
    those the a an is are was were be been am do does did done have has had can
    could will would should shall may might must what where when why who which
    how to of in on at for from with by about and or but not no yes if so there
    here please thank thanks get got use used using pay apply claim need want
    know tell say said again one more much many every year month day tomorrow
    today weather card shop clinic house money help voucher vouchers forgot
    reset password print repeat slip receipt open time morning good don't
    didn't can't catch hear hospital bill flat community centre center
    anything something any some
""".split())

# Counted for neither language: scheme names and Singapore discourse particles.
NEUTRAL_WORDS = frozenset("""
    cdc chas singpass careshield medisave medishield hdb cpf sms otp
    lah leh lor ah meh hor sia liao
""".split())

_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")


class DecisionRule(str, Enum):
    """Which policy rule decided the language; recorded for tests and diagnosis."""

    TRANSCRIPT = "transcript"
    SHORT_UTTERANCE = "short_utterance"
    STT_EVIDENCE = "stt_evidence"
    PREFERENCE = "preference"


@dataclass(frozen=True)
class LanguageDecision:
    """The chosen reply language, the rule that chose it and the token counts."""

    language: str
    rule: DecisionRule
    malay_tokens: int
    english_tokens: int
    word_tokens: int


def _words(transcript: str) -> list[str]:
    """Return the transcript's lower-case word tokens with typographic apostrophes folded."""
    return [word.replace("’", "'") for word in _WORD.findall(transcript.lower())]


def decide_reply_language(
    transcript: str, evidence: LanguageEvidence | None, preference: str = ENGLISH,
) -> LanguageDecision:
    """Return the reply language for one transcript.

    `preference` must be `en` or `ms`; any other value raises ValueError,
    because configuration validates it at startup and a silent default would
    hide a wiring mistake. `evidence` may be None (canned STT invents none).
    """
    if preference not in SUPPORTED_LANGUAGES:
        raise ValueError(f"preference must be one of {SUPPORTED_LANGUAGES}, got {preference!r}.")
    words = _words(transcript)
    malay = sum(1 for word in words if word in MALAY_WORDS and word not in NEUTRAL_WORDS)
    english = sum(1 for word in words if word in ENGLISH_WORDS and word not in NEUTRAL_WORDS)

    def decision(language: str, rule: DecisionRule) -> LanguageDecision:
        return LanguageDecision(language, rule, malay, english, len(words))

    counted = malay + english
    if counted >= MIN_COUNTED_TOKENS:
        share = malay / counted
        if share >= MALAY_SHARE_FOR_MALAY:
            return decision(MALAY, DecisionRule.TRANSCRIPT)
        if share <= MALAY_SHARE_FOR_ENGLISH:
            return decision(ENGLISH, DecisionRule.TRANSCRIPT)

    if len(words) <= SHORT_UTTERANCE_TOKENS:
        return decision(preference, DecisionRule.SHORT_UTTERANCE)

    label = evidence.language.strip().lower().split("-")[0] if evidence is not None else ""
    if label in STT_MALAY_LABELS and malay > 0:
        return decision(MALAY, DecisionRule.STT_EVIDENCE)
    if label in STT_ENGLISH_LABELS and english > 0:
        return decision(ENGLISH, DecisionRule.STT_EVIDENCE)
    return decision(preference, DecisionRule.PREFERENCE)


def is_english_text(text: str) -> bool:  #v1.1
    """Return False only when the transcript rule would call `text` Malay.

    Used on generated answers, not on speech: the slip must be English, and
    the grounded model can answer a Malay question in Malay despite its
    prompt. Text too short to count is treated as English, because nothing
    here can show otherwise.
    """
    return decide_reply_language(text, None, ENGLISH).language == ENGLISH
