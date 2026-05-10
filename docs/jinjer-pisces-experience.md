# Jinjer — Pisces: audience experience pass

This is not a metric report. It is an attempt to hear the track as someone in the room, then check whether galdr's metrics explain the experience without flattening it.

The main lesson is already visible: the song's biggest transformation is not a single metric. It is a compound surface change riding on top of continuous bodily lock.

## 0:00–0:14 — the room opens before the threat arrives

The opening does not feel weak. It feels held.

From the audience, the body already has somewhere to go. The guitar is clean and suspended, but the pulse is not vague. It is a quiet grid. You lean in, not because the song is small, but because it has made the space precise.

Galdr sees that contradiction clearly:

- body entrainment is already high: ~`0.767`
- pattern lock is very high: ~`0.982`
- WDS is high/suspended: ~`0.432`
- texture is strongly harmonic: ~`-0.747`
- loudness is low: ~`-21.6 LUFS`
- chroma flux is high: ~`0.783`
- foreground pitch evidence is highest here: vocal presence peaks up to `0.424`

So the first state is not "soft = loose." It is soft, suspended, and already locked.

That matters because the later violence does not have to create the body. The body is already there.

## 0:14–0:35 — the surface hardens, but the body does not lose the thread

When the harder material enters, the room changes fast. This is the first major perceptual switch.

It is not just vocal. Calling it a vocal switch is too narrow. The voice matters, obviously, but what changes is the whole surface: loudness, percussive bite, texture density, harmonic cleanliness, and the listener's sense of threat.

Galdr sees the hardening as a cluster:

- loudness jumps from ~`-21.6` to ~`-13.9 LUFS`
- harmonic texture weakens: texture balance moves from ~`-0.747` to ~`-0.443`
- percussive weight rises: ~`0.017` to ~`0.070`
- harmonic weight also rises: ~`0.083` to ~`0.176`
- WDS drops from suspended ~`0.432` to present/light ~`0.241`
- body entrainment stays high and even rises: ~`0.791`
- momentum stays high: ~`0.955`

This is why the switch feels so dramatic while WDS alone does not fully describe it.

WDS says: the music stops floating so much and becomes more grounded/present.

The full metric stack says: the entire surface has hardened while the body remains locked.

That is closer to the audience experience.

## The central trick — transformation without losing time

The song's power is not simply that it moves from clean to heavy. Lots of songs do that.

The trick is that the transformation does not feel like the band changed songs. The clean surface and harsh surface belong to the same current. The listener's body is prepared before the harshness arrives, so the impact lands as revelation rather than interruption.

This is where galdr's split between body metrics and surface metrics is useful:

- body entrainment remains high
- momentum remains high
- pattern lock remains high
- WDS changes, but not enough to own the whole perceptual event
- texture/loudness/harm-perc explain more of the shock

So the audience experience is: "the same body reveals a harder skin."

Not: "a quiet song becomes a loud song."

Not even: "a clean voice becomes a harsh voice."

The voice is the most human sign of the transformation, but the transformation is carried by the whole band.

## Around 1:26 — the false lift

A raw WDS event labeled this area as `weight_lifts`. That is probably wrong as listening language.

From the audience, this is still the middle of the heavy section. Nothing feels like the weight has meaningfully lifted away. If there is a small breath or clearance in the waveform, it does not change the embodied state.

The surrounding metrics agree with the listener more than the label:

- body entrainment: ~`0.749`
- momentum: ~`0.959`
- pattern lock: ~`0.966`
- loudness: ~`-12.4 LUFS`
- texture is much less harmonic than the opening: ~`-0.155`
- percussive weight remains elevated: ~`0.118`

So the event word is bad. The model saw a WDS local drop and over-named it. A better system would suppress that as phrase-internal motion unless other metrics confirm a real experiential release.

## 2:45–3:16 — one head-nod groove, not a pile of events

As an audience member, this section reads as one continuous slow metal rhythm. It is the kind of groove where the head moves back and forth to the beat. The interesting thing is continuity, not event density.

Jason's listening note is important: `2:45–2:57` and `2:57–3:16` feel basically the same.

The full metrics mostly support that.

### 2:45–2:57

- weight: ~`0.254`
- body entrainment: ~`0.741`
- momentum: ~`0.960`
- pattern lock: ~`0.962`
- WDS: ~`0.232`
- texture balance: ~`-0.128`
- loudness: ~`-12.18 LUFS`
- harmonic tension: ~`0.230`
- chroma flux: ~`0.438`

### 2:57–3:16

- weight: ~`0.255`
- body entrainment: ~`0.754`
- momentum: ~`0.960`
- pattern lock: ~`0.965`
- WDS: ~`0.213`
- texture balance: ~`-0.131`
- loudness: ~`-11.98 LUFS`
- harmonic tension: ~`0.207`
- chroma flux: ~`0.405`

Those are not two different listener states. They are the same groove with a slightly wider WDS local swing in the second half.

The event stream over-speaks because WDS crosses the light/present boundary repeatedly. But the rest of the stack says: no, the body is still in one mode.

Audience-language version:

> The song is nodding in a slow, heavy cycle. The second half has a little more internal wobble in the weight curve, but it does not become a new experience. It is still the same metal rhythm.

This points to a needed galdr rule: if body, momentum, pattern lock, texture, loudness, and harmony stay continuous, repeated WDS boundary crossings should collapse into phrase-internal motion, not separate prose events.

## 3:47–3:55 — the harmonic floor churns under a stable body

This section is different. It is not just more heavy. It feels like the floor under the song turns over.

Galdr sees that mostly through harmony and pitch-surface metrics:

- harmonic tension rises: ~`0.357`, peaking up to `0.739`
- chroma flux surges: ~`0.813`, peaking at `1.000`
- vocal/pitch evidence rises: ~`0.120`
- pitch range widens: ~`18.4 st`
- overtone richness is relatively high: ~`0.398`
- body entrainment remains high: ~`0.793`
- pattern lock remains high: ~`0.975`

This is a different kind of event from the early hardening. The early switch changes the surface from suspended/clean into harder/grounded. This later moment churns the harmonic color under a still-stable rhythmic body.

Audience-language version:

> The body still knows where the beat is, but the harmonic water underneath turns black and moves sideways.

That is the kind of thing WDS is not designed to own. WDS can say whether the body feels heavier/lighter/suspended. Harmony has to say when the floor changes color.

## 4:30–5:00 — the final weight becomes punishing

The ending stretch is less about surprise and more about endurance. The track has proved the identity split. Now it holds the listener under it.

Galdr sees the final section as high-force continuity:

- weight is high: ~`0.262`
- WDS is present and elevated: ~`0.272`
- loudness is high: ~`-11.9 LUFS`
- percussive weight remains forward: ~`0.126`
- momentum remains high until the final stop
- pattern lock remains high: ~`0.964`
- breath trends negative/releasing: ~`-0.115`

The body is still held, but the hold has become punishing rather than elegant.

Then the ending matters because it is one of the only true breaks. The song finally stops carrying the listener. Silence becomes an event because almost nothing else in the track truly lets go.

## What the metrics are teaching us

WDS is not a general detector for "this sounds radically different."

WDS is best at detecting body-carriage changes:

- suspended vs grounded
- light vs present/heavy
- drag/sway/weight under the pulse
- whether the sound makes the listener lean, sink, float, or brace

In `Pisces`, the huge early transformation is only partly WDS. The bigger event is a compound surface-impact switch:

- loudness jumps
- texture hardens
- percussive material comes forward
- harmonic cleanliness changes
- vocal/foreground surface changes
- WDS moves from suspended toward present
- body lock remains continuous

That last point is the song's genius. The listener hears a massive identity change, but the body does not get thrown out of the song. The track changes skin without changing current.

## Proposed perceptual vocabulary

The current event vocabulary is too narrow. `weight_arrives` and `weight_lifts` cannot carry this whole experience.

Better event language for this track would include:

- `surface_hardens` — clean/suspended material becomes louder, rougher, more percussive, more threatening
- `surface_clears` — hard surface recedes into clearer harmonic/voiced material
- `body_current_holds` — strong listener continuity despite surface transformation
- `harmonic_floor_churns` — chroma/tension surge while body lock remains stable
- `phrase_internal_weight_motion` — WDS oscillates but the groove remains one experience

For Jinjer, the decisive early moment is probably:

> `surface_hardens` while `body_current_holds`.

That is the missing sentence.

## Bottom line

As someone in the audience, I would not hear `Pisces` as a sequence of isolated weight lifts and arrivals.

I would hear it as one disciplined current with multiple skins:

1. a suspended clean opening that is already bodily locked
2. a sudden hardening of the whole surface, not just the voice
3. heavy sections where the body remains inside the same timing architecture
4. a slow head-nod groove around `2:45–3:16` that should be treated as one continuous state
5. a later harmonic churn where the floor moves under the still-locked body
6. a final stretch where the lock becomes punishing, then silence finally releases it

The track is so different to the ear because the surface changes violently while the body remains continuous. That is exactly the kind of distinction galdr should be able to express.
