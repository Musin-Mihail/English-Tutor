import re
from difflib import SequenceMatcher
from typing import Any, Dict, List

from app.core.config import settings
from app.services.acoustic_asr import AcousticTranscriber
from app.services.asr import LocalTranscriber, empty_whisper_result

_WORD_RE = re.compile(r"[a-z']+")
_STOPWORDS = {
    "a",
    "an",
    "the",
    "to",
    "of",
    "in",
    "on",
    "at",
    "for",
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "am",
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "my",
    "your",
    "his",
    "her",
    "our",
    "their",
}

_whisper = LocalTranscriber()
_acoustic = AcousticTranscriber()


def _tokens(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower())


def pick_literal_transcript(whisper_text: str, acoustic_text: str) -> str:
    acoustic = (acoustic_text or "").strip()
    whisper = (whisper_text or "").strip()
    return acoustic or whisper


def _normalize_compare(text: str) -> str:
    return " ".join(_tokens(text))


def _close_enough(word: str, spoken: List[str]) -> bool:
    for token in spoken:
        if token == word:
            return True
        if SequenceMatcher(None, token, word).ratio() >= 0.82:
            return True
    return False


def missing_content_words(correct: str, spoken: str) -> List[str]:
    spoken_tokens = _tokens(spoken)
    missing: List[str] = []
    seen: set[str] = set()
    for word in _tokens(correct):
        if word in _STOPWORDS or word in seen:
            continue
        seen.add(word)
        if not _close_enough(word, spoken_tokens):
            missing.append(word)
    return missing


def analyze_recordings(audio_paths: List[str]) -> List[Dict[str, Any]]:
    whisper_results = _whisper.transcribe_files(audio_paths)
    if settings.ACOUSTIC_ASR:
        try:
            acoustic_texts = _acoustic.transcribe_files(audio_paths)
        except Exception as e:
            print(f"!!! Acoustic ASR unavailable: {e}")
            acoustic_texts = [""] * len(audio_paths)
    else:
        acoustic_texts = [""] * len(audio_paths)

    packed: List[Dict[str, Any]] = []
    for whisper, acoustic in zip(whisper_results, acoustic_texts):
        item = dict(whisper or empty_whisper_result())
        item["whisper_text"] = item.get("text") or ""
        item["acoustic_text"] = acoustic or ""
        item["literal_text"] = pick_literal_transcript(
            item["whisper_text"], item["acoustic_text"]
        )
        packed.append(item)
    return packed


def format_analysis_block(analyses: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for i, item in enumerate(analyses, start=1):
        low = item.get("low_confidence_words") or []
        low_text = ", ".join(low) if low else "нет"
        lines.append(f"""Предложение {i}:
- whisper_transcript: "{item.get('whisper_text', '')}"
- acoustic_transcript: "{item.get('acoustic_text', '')}"
- literal_transcript: "{item.get('literal_text', '')}"
- low_confidence_words: {low_text}""")
    return "\n".join(lines)


def _error_key(err: Dict[str, Any]) -> str:
    return f"{err.get('type', '')}|{err.get('explanation', '')}".lower()


def _merge_errors(
    existing: List[Dict[str, Any]], extra: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    merged = list(existing or [])
    seen = {_error_key(err) for err in merged}
    for err in extra:
        key = _error_key(err)
        if key in seen:
            continue
        seen.add(key)
        merged.append(err)
    return merged


def augment_pronunciation_errors(
    result: Dict[str, Any], analyses: List[Dict[str, Any]]
) -> Dict[str, Any]:
    sentences = result.get("sentences_feedback") or []
    for i, sentence in enumerate(sentences):
        analysis = analyses[i] if i < len(analyses) else empty_whisper_result()
        literal = pick_literal_transcript(
            analysis.get("whisper_text", ""),
            analysis.get("acoustic_text", ""),
        )
        if literal:
            sentence["student_transcription"] = literal

        extra: List[Dict[str, Any]] = []
        if not literal:
            sentence["errors"] = _merge_errors(sentence.get("errors") or [], extra)
            continue

        low = analysis.get("low_confidence_words") or []
        if low:
            extra.append(
                {
                    "type": "Произношение",
                    "explanation": (
                        "Низкая уверенность распознавания у слов: "
                        f"{', '.join(low)}. Возможно, они произнесены нечётко."
                    ),
                }
            )

        whisper_n = _normalize_compare(analysis.get("whisper_text", ""))
        acoustic_n = _normalize_compare(analysis.get("acoustic_text", ""))
        if whisper_n and acoustic_n and whisper_n != acoustic_n:
            extra.append(
                {
                    "type": "Произношение",
                    "explanation": (
                        "Акустическая расшифровка "
                        f"«{analysis.get('acoustic_text', '')}» расходится с Whisper "
                        f"«{analysis.get('whisper_text', '')}». "
                        "Вероятны искажения звуков или окончаний."
                    ),
                }
            )

        missing = missing_content_words(sentence.get("correct_variant") or "", literal)
        if missing:
            extra.append(
                {
                    "type": "Произношение",
                    "explanation": (
                        "В речи не распознаны слова из правильного варианта: "
                        f"{', '.join(missing)}."
                    ),
                }
            )

        sentence["errors"] = _merge_errors(sentence.get("errors") or [], extra)

    result["sentences_feedback"] = sentences
    return result
