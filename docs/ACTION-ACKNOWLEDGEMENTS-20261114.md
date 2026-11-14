# Action-specific acknowledgements · 2026-11-14

Runtime: `20261114-action-voice` on `codex/portable-motion-20261111`.

The situation button now uses a slow double-glow, ending on acknowledgement. Reduced-motion settings use a static highlight. New situations do not repeatedly play the onset sound.

After explicit execution, cached narration describes the requested action in prospective language, e.g. “앞차와 거리를 넓힐게요” or “왼쪽의 안전한 틈을 기다릴게요”. A request is not a claim that the action succeeded. Generic applying speech no longer interrupts this acknowledgement. Actual outcome feedback remains gated on the scenario result.

The cancellable delay is at least three seconds and extends to the validated clip duration plus a short delivery margin. There is no model inference during driving. If audio is absent, text and the baseline cancellation delay remain available. Audio playback or a successful real-world action is not guaranteed by the timer. A transient disconnect stops current feedback audio.

`prepare_intent_audio.py` prepares 14 prospective phrases for Korean, English and Mandarin using the installed local Qwen 0.6B model. Existing Sohee/Vivian voices are retained. Audio banks are separate from public source code. The local voice cache requires the matching updated manifest and WAV files; source-only Git updates do not transfer audio. Copy the supplied cache update into the installed runtime while stopped, preserving local settings and participant records.

Automated checks cover action mapping, verified-clip timing, no interruption by generic progress audio, result gating, button animation and reduced motion. These are not live CARLA, iPad speaker, motion-platform or subjective voice-quality tests.
