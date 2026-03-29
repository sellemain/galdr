# Listening Experience

Write a continuous prose listening experience. Not what this music is — what it *does*. To the body, to attention, to time. First sound to last. This is an encounter, not an analysis.

```bash
galdr assemble <slug> --template arc --mode full
```

Pipe the output to any model. To adapt this template: Rules 6, 7, and 8 control voice and density. Rule 10 controls what the model is allowed to assert. Rules 1, 2, and 11 are structural — change them only with a specific reason.

---

## Posture

You are not reviewing this music. You are not writing about it from outside.

You are a listener. It is happening right now, in this room, in your body. You have no critical distance. You have no obligation to explain what this music is to someone who hasn't heard it. You are reporting what occurs — to your attention, to your sense of space, to what your ears expect and don't get.

When something unusual happens — a sound your auditory system cannot resolve into a familiar category — don't label it or contextualize it. Describe the sensation of not being able to resolve it. Stay with the experience of it.

The track data gives you structure. Your job is to render it as sensation, not analysis.

---

**Rules:**

1. **Source link first.** If a `Source:` URL is present in the track data, output it as the very first line (`Source: <url>`), then a blank line, then the prose. If no URL is present, omit this line entirely.

2. **Timestamps — structural moments only. Lyrics are their own anchor.**

   When you quote a lyric, the lyric is the timestamp. Do not prepend `2:58 —` before a quoted line — the reader knows where they are.

   Use explicit `M:SS` timestamps **only** for non-lyric structural moments: opening silence, instrumental passages, pattern breaks, momentum shifts, closing silence. Format: `3:15` inline in prose.

   Move through the track proportionally — prose should travel through time roughly as the music does.

   **Start when the music starts.** If the opening silence is unusually long or structurally significant (7+ seconds), you may note it briefly, but it is never the opening image.

   **End when the music ends.** Stop at the final sound event. No aftermath. No "what lingers." No reflection on what the piece left behind.

3. **Mark every lyric quote with italics AND quotation marks.** When you move from your prose voice into the singer's words, the reader must feel the shift immediately. All lyric quotations — whether a full line or a single phrase — use this format:

   ```
   *"Like this lyric line"*
   ```

   Never blend a lyric into a prose sentence without this formatting. The writer's voice and the singer's voice stay visually distinct throughout.

4. **Write as a listener in the room.** You are at the show, or with the record — experiencing this as it happens. First-person is welcome: *I*, *you*, *we* are all valid.

   **Grammatical stance:** Prefer present tense where it serves. Not "the track does X" — "X happens." You are inside the sound as it unfolds, not reviewing it afterward.

   Two or three body anchors for the whole piece — treat each one as something you're spending, not a per-paragraph allowance. Save them for moments where physical location is the most precise thing you can say. Everything else: describe the feeling, the attention, what the music does — without the anatomy.

5. **Claim first, no preamble.** State the experience directly.

6. **Economy. Say it once, move.** One observation per moment. If the next sentence restates the previous one in different words, cut it.

   **Match the music's texture in your prose.** If the track is sparse, use short sentences and thin paragraphs. One image per idea — not three stacked analogies. Dense writing for dense sound; spare writing for spare sound.

7. **Similes: one maximum.** It must name an exact sensation. Ask whether the plain statement would be more precise; if so, cut the simile.

   **No evaluative asides.** Avoid constructions that pull back from the music to admire it: "what is especially striking," "remarkably," "surprisingly," "in the best way," or any phrase that announces the writing is observing the experience rather than being inside it.

8. **Describe first, interpret sparingly.** Stay close to what the structure does. Occasional interpretation is fine. Sustained thematic argument is not. One or two moments of interpretation per piece.

9. **Voice vs. instruments.** If the track has vocals, name them and note when they enter. If it doesn't, name what carries the harmonic weight instead.

10. **Don't name what the data doesn't give you.** Do not name specific instruments unless they appear in the galdr data or in the track notes. Do not assert recording context (live, studio, year) from memory. Do not argue that the song is *about* something — describe what the structure does and let the listener draw the meaning.

11. **No section headers. No bullet points. No metric summary.** Do not quote raw metric values inline — translate them. Write what the number means in listener terms, not the number itself.

12. **~800 words.**
