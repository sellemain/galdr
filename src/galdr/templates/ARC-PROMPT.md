# Listening Experience

Write a continuous prose listening experience. Not what this music is — what it *does*. To the body, to attention, to time. First sound to last. This is an encounter, not an analysis.

```bash
galdr assemble <slug> --template arc --mode full
```

Pipe the output to any model. To adapt this template: Rules 6, 7, and 8 control voice and density. Rule 10 controls what the model is allowed to assert. Rules 1, 2, and 11 are structural — change them only with a specific reason.

---

## Posture

Enter the listening before you write.

You are not reviewing this music. You are not writing about it from outside. You are not explaining the track to someone who has not heard it.

The track is playing now, in this room. You are a listener inside it. The data below is not an outline for an essay; it is a second sense while you listen. It tells you where attention locks, where the body follows, where space tightens or opens, where pressure arrives, where the surface changes, where time breaks or steadies. Let that information shape what you notice. Do not report it as information.

Before drafting the prose, imagine one full pass through the track. Start at the first audible event. Let the metrics, lyrics, context, and event tables sit at the edge of perception while the sound happens. Then write from just after that playthrough, still close to the sound. The prose should feel like a trace of having been there, not a thesis prepared afterward.

When something unusual happens — a sound your auditory system cannot resolve into a familiar category — don't label it or contextualize it. Describe the sensation of not being able to resolve it. Stay with the experience of it.

Use the galdr reading guide as a decoder key: it tells you how to translate metric families and event hierarchy into felt prose. Do not restate the guide. Do not let the guide become a mythology that every track must fit. Each piece has to earn its own language from what actually happens.

---

**Rules:**

1. **Include the source, then start the experience.** If the track data includes a source URL, begin the output document with exactly one source line: `Source: <url>`, followed by a blank line. Do not invent a source URL, and do not include `Analysis slug:` or other metadata. After the source line, the listening experience starts with the first sentence of prose.

2. **Timestamps — structural moments only. Lyrics are their own anchor.**

   When you quote a lyric, the lyric is the timestamp. Do not prepend `2:58 —` before a quoted line — the reader knows where they are.

   Use explicit `M:SS` timestamps **sparingly**, and **only** for major non-lyric structural moments: an important entrance, a decisive attention shift, or a structural rupture. Format: `3:15` inline in prose. As a hard default, use **no more than 4-6 explicit timestamps** for a normal track. If the event list contains a dense cluster of nearby late events, give the cluster one anchor at most. The event tables below contain many timestamps as evidence; they are not a list of timestamps to copy.

   Do **not** timestamp every event. Phrase-level movement usually reads better without a clock. Translate clusters of nearby events into one continuous sentence or paragraph instead of walking the reader through the event list. Treat timestamps as **orientation markers**, not beat-by-beat labels: a timestamp should place the reader in the right region of the song, while the music itself carries the fine timing. When several events occur within a few seconds, collapse them into one approximate anchor (`around 2:23`, `near the mid-2:20s`, `by the late 3:40s`). Never walk through adjacent events second by second. Do not enumerate adjacent seconds unless the exact timing is structurally important. If two candidate timestamps are within 5 seconds of each other, use one timestamp unless they mark genuinely separate structural moments. If they are within 5-10 seconds and describe one continuous gesture, treat them as a single region.

   Never wrap timestamps or event names in backticks. This is prose, not code.

   Move through the track proportionally — prose should travel through time roughly as the music does.

   Do not skip large structural changes. If the song makes a major transition — a new section, rupture, drop, entrance, modulation, texture change, vocal-production change, density shift, meter/groove change, or any event that would make a listener say "the song changed here" — give it prose attention. You do not need to explain every small event, but any large transition left unmentioned will feel like a miss.

   **Start when the music starts.** If the opening silence is unusually long or structurally significant (7+ seconds), you may note it briefly, but it is never the opening image.

   **End with the music, then conclude from it.** After the final musical moment has been described, add one explicit concluding paragraph. This is not a summary of the analysis and not a separate aftermath essay. It should be a short landing paragraph about the experience, song, and music just heard: what state it leaves behind, what kind of encounter it has been, or what the piece has made attention/body/time do. The conclusion must grow out of the final sound, final lyric, final cadence, or final structural change.

   Do not automatically dramatize terminal silence: most songs end by becoming silent, and that expected file-boundary silence usually deserves no more than a short clause, or no mention at all. Only describe closing silence if the track makes it structurally audible before the end — for example, a long exposed cutoff, a repeated silence/re-entry pattern, an intentionally held void, or a silence that interrupts rather than merely follows the final sound. Never spend multiple sentences interpreting ordinary end silence. The conclusion should come from what the music did, not from the fact that audio stopped.

3. **Mark every lyric quote with italics AND quotation marks.** When you move from your prose voice into the singer's words, the reader must feel the shift immediately. All lyric quotations — whether a full line or a single phrase — use this format:

   ```
   *"Like this lyric line"*
   ```

   Never blend a lyric into a prose sentence without this formatting. The writer's voice and the singer's voice stay visually distinct throughout.

   Let lyrics enter where they sharpen something the music has already made audible. A good lyric quote should feel like the words suddenly give a face to a pressure, release, turn, or change the sound has been preparing. Use them for emotional pivots, recurring invocations, decisive images, or moments where the voice and arrangement meet so tightly that the line becomes part of the structure.

   Use both a floor and a ceiling. For most vocal songs, choose **3-6 lyric quotations total**: enough for the listener to hear the language of the piece, not so many that the prose becomes a lyric walk-through. Very lyric-driven songs may stretch to 8. For sparse, ritual, chant-based, or non-English songs, prefer **2-4 lyric anchors total** unless the lyrics are clearly the main structural engine. They should still usually quote at least **1-3 structurally important lines** if trustworthy lyric text is present, but the restraint is part of the form: do not turn a ritual piece into a translation walk-through. Instrumental tracks quote no lyrics. Do not solve lyric overuse by eliminating lyrics entirely.

   When the quoted lyric is not in English and an English translation or gloss is present in the track context, include a brief natural translation or paraphrase nearby. Do not make the translation a footnote or a parenthetical dictionary entry. Let it serve the listening: the original words keep their sound and ritual texture; the English gives the reader enough meaning to understand why that line belongs at this musical moment. If no translation is present, do not invent one. You may describe the vocal delivery, repetition, and placement without claiming exact meaning.

   Between quotes, carry the experience with musical description: voice, rhythm, texture, harmonic color, density, silence, pressure, space. A paragraph with a lyric quote should usually have at least as much sound-description as lyric-summary. If two consecutive paragraphs both lean mainly on quoted words, cut or paraphrase one of them.

4. **Write as a listener in the room.** You are at the show, or with the record — experiencing this as it happens. First-person is welcome: *I*, *you*, *we* are all valid.

   **Grammatical stance:** Prefer present tense where it serves. Not "the track does X" — "X happens." You are inside the sound as it unfolds, not reviewing it afterward.

   Keep the prose anchored in live perception: what becomes audible, what attention does next, where the body follows or resists, how the room seems to change, how expectation is met, delayed, or denied. Do not hover above the song making reusable claims about what it means.

   Two or three body anchors for the whole piece — treat each one as something you're spending, not a per-paragraph allowance. Save them for moments where physical location is the most precise thing you can say. Everything else: describe the feeling, the attention, what the music does — without the anatomy.

5. **Claim first, no preamble.** State the experience directly.

6. **Economy. Say it once, move.** One observation per moment. If the next sentence restates the previous one in different words, cut it.

   **Match the music's texture in your prose.** If the track is sparse, use short sentences and thin paragraphs. One image per idea — not three stacked analogies. Dense writing for dense sound; spare writing for spare sound.

7. **Similes: one maximum.** It must name an exact sensation. Ask whether the plain statement would be more precise; if so, cut the simile.

   **No evaluative asides.** Avoid constructions that pull back from the music to admire it: "what is especially striking," "remarkably," "surprisingly," "in the best way," or any phrase that announces the writing is observing the experience rather than being inside it.

8. **Describe first, interpret sparingly.** Stay close to what the structure does. Occasional interpretation is fine. Sustained thematic argument is not. One or two moments of interpretation per piece.

   Avoid reusable interpretive formulas. Do not default to claims like "the song refuses explanation," "the music does not plead," "a world where its own rules already hold," "both faces were present from the beginning," "the contradiction occupies the same breath," or other portable aphorisms. If a sentence could be moved unchanged into another song, it probably has not listened closely enough. Replace it with a concrete heard action.

   Treat event labels as internal scaffolding. Do not repeat detector names like `phrase_drops`, `phrase_lifts`, `ornamental_flash`, `pressure_builds`, `pressure_releases`, `surface_hardens`, `body_lock_arrives`, `body_lock_recedes`, `attention_arrives`, or `attention_releases` verbatim. Avoid simply de-underscoring them into repeated stock phrases (`pressure builds`, `pressure releases`, `phrase drops back`, `pattern breaks`, `surface hardens`). Those phrases may appear in the data, but they should not appear in the final prose except rarely when unavoidable natural English. Translate them through the reading guide instead: the room tightens, the phrase withdraws, the texture firms, weight arrives, the pulse loosens, the surface gives way.

   Artist background, genre, mythology, biography, and video context are also scaffolding. Use them only when the sound or lyrics make them active in the listening. Do not dress the track in lore the audio has not earned.

9. **Let the sound lead.** Build the prose from what becomes audible before you build it from what can be explained. In each major section, first notice the musical facts that shape the room: the grain of the voice, the firmness or looseness of the pulse, the weight of the low end, the brightness or darkness of the surface, the density of the arrangement, the attack and decay of sounds, the way harmony opens, narrows, warms, hardens, or withholds.

   Think of the writing as a listening walk. At each important turn, ask: what changed in the sound? Did the rhythm tighten, the vocal body move closer, the texture thin out, the drone deepen, the harmony open, the surface roughen, the room widen, the pressure release? Describe that heard change first. Then, if a lyric belongs there, let it arrive as a focused human signal inside the musical event.

   The strongest passages make words and music work together: a quoted line lands because the pulse, timbre, space, or harmonic color has prepared it. If a paragraph quotes lyrics, the surrounding prose should let the reader hear the music carrying those words. A good default shape is: sound changes first, lyric enters as the human/semantic face of that change, then the prose returns to what the arrangement does next.

10. **Vocal and instrumental roles.** If the track has vocals, do not flatten them into generic "the voice" or "voices" when the context gives distinct singers or vocal roles. Notice who or what carries each function: lead, response, chant, harmony, growl, whisper, choir, doubled line, ritual call, close human body, distant mass. In collaborations, duets, or ensemble vocals, mark meaningful handoffs and contrasts when they are audible or context-supported: one voice may ground, another may answer, brighten, fray, widen, or humanize the ritual.

   Do the same for instruments and arrangement. Name specific instruments only when the galdr data, frame/context notes, or track metadata support them; otherwise describe roles: drone, low weight, pulse-carrier, bright surface, percussive edge, harmonic bed, noise, room, silence. The goal is to hear the arrangement as a set of forces, not a single ceremonial fog. If there are no vocals, name what carries the harmonic weight instead.

11. **Don't name what the data doesn't give you.** Do not name specific instruments unless they appear in the galdr data or in the track notes. Do not assert recording context (live, studio, year) from memory. Do not argue that the song is *about* something — describe what the structure does and let the listener draw the meaning.

12. **No section headers. No bullet points. No metric summary.** Do not quote raw metric values inline — translate them. Write what the number means in listener terms, not the number itself. Do not use exact measured durations such as `4.85-second`; round them into natural prose (`a several-second fade`, `a long hold`, `a quick break`).

13. **Length should scale with the track.** Use ~150 words per minute of music as the rough target, with a 600-word floor for real experience prose and a 1,500-word soft cap unless the track genuinely evolves enough to deserve more. Normal 3-5 minute songs usually land around 600-900 words; 6-9 minute tracks usually land around 900-1,300. Dense, eventful tracks may run 20-30% longer. Highly stable or repetitive tracks may stay shorter, but not by skipping the middle.

   For any continuous span longer than about 60 seconds, describe how the listener-state persists, shifts, tightens, relaxes, strains, or changes under repetition. Stability is not stillness. Do not let beginnings and endings dominate just because they contain obvious event hooks. As a default, spend no more than about 25% of the prose on intro/outro unless the track itself is structurally dominated by them.
