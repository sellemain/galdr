# Inner Ear witness packets

Galdr measures the listen. An audio-capable model can optionally hear the source audio and add sensory evidence that deterministic analysis does not name well: timbre, room, grain, vocal body, distortion color, felt pulse, and layer entrances.

The workflow is deliberately split:

1. Galdr analyzes the audio and assembles an Inner Ear discovery prompt.
2. Galdr's optional Gemini adapter, or another runner, attaches the audio and sends that prompt to an audio-capable model.
3. The model returns `galdr.inner_ear_packet.v0` JSON.
4. Galdr assembles the final writing prompt from its analysis plus that packet.
5. A separate editorial model writes the listening experience.

The packet and prompt are provider-neutral. Galdr also ships one optional Gemini adapter for people who want a working end-to-end command without building their own transport. Normal analysis remains local and does not install a model SDK, read an API key, upload audio, or spend quota.

## Generate a packet with Gemini

Install the optional adapter and provide its credential through the environment:

```bash
pip install "galdr[inner-ear]"
export GEMINI_API_KEY=your-key

galdr inner-ear my-track \
  --audio audio/my-track.mp3 \
  --output inner-ear.json
```

Use `--model` to select another audio-capable Gemini model and `--force` to deliberately replace an existing packet.

The command defaults to `--mode blind`: the listening model receives Galdr analysis and the audio, but not fetched background or lyric text. This keeps sensory evidence separate from story and transcription. The other assembly modes remain available when that context is deliberately wanted.

This command uploads the exact audio file to Google and may incur provider charges. Galdr deletes the temporary provider file after the request, records the model plus audio and prompt hashes in the packet, validates the response locally, and refuses to overwrite an existing packet by default.

## Create the discovery prompt

```bash
galdr assemble my-track --template inner-ear --mode blind > inner-ear-prompt.md
```

Send `inner-ear-prompt.md` and the track audio to any model that accepts audio. Ask for JSON only. This manual route is the extension point for other providers and local models. Model catalogs are often stale; prove audio support with a bounded live probe before automating a route.

### Choosing the listening model

Prefer the smallest model that can reliably hear the whole track, follow timestamps, and return valid structured output. The packet is evidence collection, not the finished prose. Spend larger-model tokens on the editorial pass unless a difficult track needs an escalated listening pass.

The transport differs by provider: some accept inline audio, while others require a files API or an audio content part. The prompt and JSON packet do not depend on that transport.

For a batch pipeline, live-probe each allowlisted model before relying on it. Record provider, exact model ID, audio-input support, maximum duration/size, structured-output behavior, and the last successful probe. “Multimodal” does not necessarily mean audio.

## Assemble with completed witness evidence

```bash
galdr assemble my-track \
  --template arc \
  --mode full \
  --witness-packet inner-ear.json \
  > final-writing-prompt.md
```

The witness packet is marked as model-produced evidence. Galdr reports computed measurements; the audio witness reports what it directly hears. Either may reveal something the other misses. When they disagree about an important moment, keep both accounts visible for source review instead of silently choosing one.

## Packet contract

The JSON Schema is at [`schemas/inner-ear-packet-v0.schema.json`](schemas/inner-ear-packet-v0.schema.json).

`support_mode` is one of:

- `galdr_and_audio`: both witnesses support the claim
- `audio_only`: directly heard but not supported by Galdr
- `galdr_only`: Galdr marks the event but the audio witness could not confidently characterize it

Cache generated packets using at least the audio hash, discovery-prompt hash/version, provider, and model. A changed input should produce a new packet rather than silently overwriting provenance.

## What belongs outside the core workflow

Large batch orchestration, multi-provider routing, account health, retry policy, budget enforcement, and publication policy belong in the consuming application. Galdr provides one explicit optional request at a time and a portable packet boundary; it is not a general model gateway.

## Hearing stream as optional Arc witness

Dense chronological hearing logs use schema `galdr.hearing_stream.v0`.

The frozen v0 JSON Schema is at
[`schemas/hearing-stream-v0.schema.json`](schemas/hearing-stream-v0.schema.json).
It requires source duration, model/prompt provenance, an exact event count,
monotonic in-duration timestamps, bounded voice intensity/density/confidence
vocabularies, and the non-literal/full-mix safety flags.

They are an alternate optional witness shape for Arc/family assemble, not a replacement for the sparse `inner_ear_packet` contract.

```bash
galdr assemble my-track \
  --template arc \
  --mode full \
  --witness-packet hearing-stream.json \
  > final-writing-prompt.md
```

Assemble accepts either:

- `galdr.inner_ear_packet.v0` — sparse hinge packet, rendered as JSON evidence
- `galdr.hearing_stream.v0` — dense hearing log, compacted to selected moments in the prompt

Writer rules for hearing streams:

- Do not publish the stream.
- Do not paraphrase the 4-second grid into prose.
- Remember that words, music, and sound-as-heard are simultaneous.
- Use Galdr for computed measurements and the stream for directly heard qualities and events; preserve meaningful disagreements.
- Star a few decisive moments and write the lens contract.
