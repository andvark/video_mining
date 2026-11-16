from __future__ import annotations

import pytest

from podstudy.annotate import annotate, has_han
from podstudy.known import load_known, unknown_words
from podstudy.models import Cue, Sentence
from podstudy.segment import split_sentences, to_simplified
from podstudy.subs import format_srt, format_vtt, parse_subs, read_subs


def test_srt_vtt_roundtrip():
    cues = [Cue(0.5, 2.25, "你好"), Cue(3.0, 4.5, "再见\n第二行")]
    assert [c.start for c in parse_subs(format_srt(cues))] == [0.5, 3.0]
    back = parse_subs(format_vtt(cues))
    assert back[1].text == "再见 第二行" and back[0].end == 2.25


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        parse_subs("1\nnot a timing\nhello\n")
    with pytest.raises(ValueError):
        parse_subs("1\n00:00:05,000 --> 00:00:01,000\nbackwards\n")


def test_parse_fixture(fix):
    cues = read_subs(fix / "sample.zh.srt")
    assert len(cues) == 5 and cues[0].text.startswith("大家好")


def test_opencc_to_simplified():
    assert to_simplified("學習中文") == "学习中文"


def test_split_sentences_traditional_and_timing():
    cues = [Cue(0.0, 4.0, "我喜歡學習。今天"), Cue(4.0, 6.0, "很好！")]
    out = split_sentences(cues)
    assert [s.text for s in out] == ["我喜欢学习。", "今天很好！"]
    assert out[0].start == 0.0 and out[0].end < out[1].end
    assert out[1].start < 4.0 < out[1].end  # sentence spans two cues


def test_split_empty():
    assert split_sentences([]) == []


def test_annotate_pinyin_and_words():
    py, words = annotate("我喜欢学习中文。")
    assert py.startswith("wǒ xǐ huān") or "xǐhuān" in py or "xǐ huān" in py
    assert "".join(w.text for w in words) == "我喜欢学习中文。"
    assert has_han(words[0].text)
    assert [w for w in words if w.text == "。"][0].pinyin == ""


def test_known_vocab_underlining(tmp_path):
    kn = tmp_path / "known.txt"
    kn.write_text("我\n学习\n# comment\n\n")
    known = load_known(kn)
    _, words = annotate("我学习播客")
    s = Sentence(0, "v", 0, 1, "我学习播客", "", None, words)
    assert unknown_words(s, known) == ["播客"]
    assert load_known(tmp_path / "missing.txt") == set()


def test_split_on_pause_and_hard_cap():
    cues = [Cue(0.0, 1.0, "你好吗"), Cue(3.0, 4.0, "我很好")]  # 2 s pause, no punctuation
    assert [s.text for s in split_sentences(cues)] == ["你好吗", "我很好"]
    long = [Cue(0.0, 10.0, "好" * 300)]
    assert all(len(s.text) <= 120 for s in split_sentences(long))
