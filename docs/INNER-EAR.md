# Inner Ear witness packets

Galdr measures the listen. An audio-capable model can optionally hear the source audio and add sensory evidence that deterministic analysis does not name well: timbre, room, grain, vocal body, distortion color, felt pulse, and layer entrances.

The default production shape is deliberately split:

1. Galdr analyzes the audio and assembles an Inner Ear discovery prompt.
2. An external runner attaches the audio and sends that prompt to an audio-capable model.
3. The model returns `galdr.inner_ear_packet.v0` JSON.
4. Galdr assembles the final writing prompt from its analysis plus that packet.
5. A separate editorial model writes the listening experience.

Galdr does not choose providers, manage credentials, spend quota, or call the model. This keeps the packet portable and lets an operator use a cheap listening model with a larger writing model.

## Create the discovery prompt

```bash
galdr assemble my-track --template inner-ear --mode full > inner-ear-prompt.md
```

Send `inner-ear-prompt.md` and the track audio to a model that accepts audio. Ask for JSON only. Model catalogs are often stale; prove audio support with a bounded live probe before automating a route.

### Choosing the listening model

Prefer the smallest model that can reliably hear the whole track, follow timestamps, and return valid structured output. The packet is evidence collection, not the finished prose. Spend larger-model tokens on the editorial pass unless a difficult track needs an escalated listening pass.

Gemini audio-input models are one tested route, both through Google directly and through compatible gateways. The transport differs by provider: some accept inline audio, while others require a files API or an audio content part. Galdr deliberately emits text and local evidence references rather than prescribing one request format.

For a batch pipeline, live-probe each allowlisted model before relying on it. Record provider, exact model ID, audio-input support, maximum duration/size, structured-output behavior, and the last successful probe. “Multimodal” does not necessarily mean audio.

## Assemble with completed witness evidence

```bash
galdr assemble my-track \
  --template arc \
  --mode full \
  --witness-packet inner-ear.json \
  > final-writing-prompt.md
```

The witness packet is marked as model-produced evidence. Galdr remains authoritative for measured timing and structure. Audio-only structural claims stay candidates; surface descriptions can lead when they describe directly heard qualities.

## Packet contract

The JSON Schema is at [`schemas/inner-ear-packet-v0.schema.json`](schemas/inner-ear-packet-v0.schema.json).

`support_mode` is one of:

- `galdr_and_audio`: both witnesses support the claim
- `audio_only`: directly heard but not supported by Galdr
- `galdr_only`: Galdr marks the event but the audio witness could not confidently characterize it

Cache generated packets using at least the audio hash, Galdr evidence hash, discovery-prompt version, provider, and model. A changed input should produce a new packet rather than silently overwriting provenance.

## What belongs outside Galdr

Batch generation for a private catalog, model routing, free-tier health, retries, cost limits, and publication policy belong in the consuming pipeline. Video frames, deterministic sounds-like tags, and model audio witnesses can all become optional evidence artifacts without making Galdr a provider SDK.
