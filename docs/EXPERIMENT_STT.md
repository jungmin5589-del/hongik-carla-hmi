# AI OFF/ON experiment and local speech input

This adds an opt-in study workflow at `/experiment`. The original seven-scene
selector and existing navigation design remain available. The study order is
practice (2 min), S1 congestion OFF, S1 congestion ON, S2 weaving lead OFF,
S2 weaving lead ON. The moderator starts the next round after interviewing.

## Start on a PC

1. Use the existing complete portable CARLA bundle. A Git clone alone is not enough.
2. Once per PC, install **system Python 3.12** and run `live/63_SETUP_LOCAL_STT.bat`.
   It creates `%LOCALAPPDATA%/HongikSTT/venv`; CARLA's Python is unchanged.
3. Run `live/64_START_EXPERIMENT.bat`. It uses the calibrated three screens if
   detected, otherwise laptop preview, with motion output OFF. It opens
   `http://127.0.0.1:8774/experiment` and tries to preload speech recognition.
4. On first use, prepare the local model while parked. The public `small` model
   is downloaded to Hugging Face's normal local cache; later starts reuse it.
5. Enter a participant ID, or use unregistered testing. Registered research
   records keep the existing SQLite/CSV and verified private Drive mirror.
6. Use the existing QR page for iPad navigation. Speech capture on iPad needs
   the existing **HTTPS** connection and Safari microphone permission.
   HTTP navigation still supports text and phrase buttons.

When updating the lab by Git, also back up and copy `cache/research-voice` from
the updated SSD bundle. The new monitor acknowledgement/notice clips are cached
in Korean, English and Mandarin, and are deliberately excluded from Git. Existing
clips and their manifest must stay together. Prepare the STT model once per PC;
copying code does not install its separate environment or model cache.

CARLA rendering, physics, safety guards, map projection, and cached Sohee TTS
remain separate from STT. STT turns speech into text; the bounded request parser
maps supported phrases to existing scenario actions. It is not an open-ended
language agent or a perception model. The current study panel and moderation
page are Korean; the recognizer supports Korean/English/Mandarin, with a limited
explicit intent vocabulary. Do not interpret that as full multilingual dialogue.

## Conditions and request flow

OFF is not the old interface A: it hides the AI invitation, passive AI copy,
explanation and free-input panel. Music/navigation/fixed help/stop remain. AI
response speech is suppressed. ON provides the existing alert and vertical
phrases, plus text and push-to-talk without first opening the invitation.
The same physical traffic targets are used in OFF and ON. Starts are not
randomized across lanes. Smooth stimuli change at 10, 25 and 40 seconds.

S1: notify me when a gap opens / increase following distance / enter lane 1 when
safe / horn. S2: notify me of increased risk / increase distance / pass when safe
/ horn. Maintain is an additional choice. Two phrase orders are available;
the order is logged separately from the old interface A/B label.

Speech/text proposes a supported request. The passenger sees the interpretation
and explicitly confirms execution. Ambiguous/unsupported route and negative
requests are rejected. The original physical lane/traffic collision checks still
apply; a request never forces an unsafe maneuver.

No intervention, explanation only and maintain run to the original five-minute
end. Real actions use the existing execution/result/20-second observation and
stop flow. Monitoring stays idle until a real scripted condition is met:

- S1: the adjacent-space and rear-approach physical checks remain clear for 1.5 s.
- S2: the measured gap decreases 2 m below the requested baseline (floor 3 m),
  or the lead's lateral offset exceeds 2 m, for 1.5 s.

It then shows and speaks a new notice and observes for 20 seconds before stopping.
If nothing changes, monitoring continues to the five-minute end. A subsequent
action supersedes the monitoring timer. These are experimental thresholds based
on scenario/actor state, not a production safety assessment or perception output.

Practice only accepts temperature changes (16–30 C) as a **navigation display**
setting. It does not operate physical HVAC or preview road-AI options. Lead
weaving is disabled for practice.

## Local STT

- `faster-whisper==1.2.1`, multilingual `small`, CPU INT8, 4 CPU threads, beam 1,
  VAD, no previous-turn conditioning. Model preloads once in a localhost worker.
- `av==16.1.0` is pinned: PyAV 19 removed an argument used by faster-whisper
  1.2.1; the incompatible combination failed before transcription.
- `ctranslate2==4.9.0` is pinned. No CARLA GPU memory is allocated for STT.
- Capture is at most 10 seconds and stops after speech followed by a short silence.
  One transcription runs at a time. Input is mono PCM WAV, at most 12 seconds.
- Audio is temporarily decoded locally, then deleted; no cloud API is called.
  At most 20 transient job results stay in worker memory until replaced/restart.
  Registered speech transcripts/choices are private research records, not Git data.
- The iPad gateway requires existing pairing/authentication and forwards only
  enumerated endpoints. It cannot install/start the STT worker or operate the engine.

This is completed-utterance recognition, not streaming recognition while someone
speaks. Synthetic cached Korean phrases were transcribed in a laptop smoke test;
that is not an accuracy evaluation with participants or an end-to-end latency
promise under simulator load. Research microphones, noise and non-native accents
must be tested. API usage is not required for this implementation. A cloud live
transcription API can be evaluated later if the measured latency/accuracy is
insufficient, with network/data handling and usage costs considered separately.

Sources: [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[OpenAI transcription workflows](https://developers.openai.com/api/docs/guides/transcription).

## Records and validation

Trial conditions are stored as PRACTICE / AI_OFF / AI_ON in the private research
DB. Trial assignment logs round and option order. Choice records distinguish
phrase / text / voice and retain the submitted transcript for registered trials.
Choice time means when the interface/server receives the interpreted proposal;
it is not speech onset or gaze. Execute and physical-result timestamps stay
separate. Unregistered tests do not create participant DB records.

`test_experiment_protocol.py` and `test_experiment_browser.cjs` cover protocol and
browser fixtures. `validate_experiment.py` checks the actual owned CARLA app with
motion OFF, separately from fixtures. `--audio` accepts a local synthetic sample
for an STT-to-confirmation-to-physical-action smoke test. Detailed telemetry and
synthetic transcripts remain outside Git. Full participant microphone/iPad and
three-screen hardware validation must not be inferred from these fixtures.
