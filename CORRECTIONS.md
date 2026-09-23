# Corrections to `tse-v1.0`

A tag is a promise about bytes. Nothing in `tse-v1.0` is edited after the fact, including this
file's subject — the errata live here, on `main`, and the tag stays exactly as it was published
and as the manuscript's SHA-256 records it.

## C1 — three `transform` rows in `MANIFEST.json` name the wrong transformation

**Affected files, in `tse-v1.0`:**

- `measurements/langconf/log_gemini.txt`
- `measurements/langconf/log_qwen.txt`
- `measurements/langconf/log_realvoice.txt`

**What the manifest says:** `"transform": "S2 transcripts replaced by SHA-256 of normalised text"`

**What was actually done:** eight absolute build paths of the author's machine were replaced by
`<repo>/`. No transcript was hashed in these files, and no transcript appears in them at all. The
S2 hashing mechanism exists in the builder but is switched off for this release — tier S2 is
published with raw transcripts, as `EXCLUDED.md` §1 describes.

**Effect on verification: none.** Every `sha256` in the manifest is the hash of the file as
published, so re-downloading and re-hashing reproduces the manifest exactly. The mislabel is a
description error, not a content error.

**Cause:** the builder chained the two transformations as `bien_doi_s2(src) or
chui_duong_dan(src)` and then wrote a hard-coded description for whichever one fired. Fixed in
the source repository: each transformation now carries its own label.

**Status:** `tse-v1.0` is left untouched. A future data release will carry the corrected labels
and a new tag; the rule is that changing data means a new tag, never a moved one.

## C2 — a redaction promised in an earlier submission was never applied

An earlier version of the title page, prepared for a different venue, stated that one third-party
company name occurring in the recorded transcripts is replaced by the token `[COMPANY]` in the
public copy. **That replacement was never applied.** The released transcripts contain the company
name as spoken, 23 times across `measurements/benchmark/M1_20260916_v1.jsonl`.

The data is left as it is, deliberately. The name is a public company name occurring in ordinary
question-and-answer speech, not personal data and under no confidentiality obligation, and the
measurement is what it is only because the text is what was actually said. The sentence promising
the redaction has been corrected in the submitted title page rather than the data being changed to
match a sentence.

Recorded here because a deposit that quietly differs from what its own documentation once claimed
is the failure this project exists to describe.
