# Pilot UX fixes · 2026-11-14

Runtime revision: `20261114-pilot-feedback`. Shared branch: `codex/portable-motion-20261111`.

- Localization does not rewrite an unchanged Korean attribute. This prevents an unbounded MutationObserver loop when an untranslated music control is inserted.
- Transient disconnection keeps the AI control visible with a reconnecting message and disables stale actions until fresh state arrives.
- English and Chinese request acknowledgements and the new invitation copy are translated. Missing staged explanation audio cannot permanently hide choices: there is an explicit choices button and a five-second fallback.
- The existing Tesla-style cockpit remains. The AI entry is a bordered rectangular button labelled “상황 확인 · 대응 선택”, with a situation preview, low-volume onset cue and persistent gentle emphasis. Reduced-motion preference is respected.
- Choosing a horn response no longer bypasses confirmation. The usual explicit execution and three-second cancellation apply. Horn playback completion does not navigate away or immediately end the drive.
- A congestion lane-entry request no longer intentionally stops the experiment in the current lane. It waits for the existing lane-clear and rear-approach checks. After a stable clear interval, the target offset transitions over five seconds. This requires live CARLA validation before participant use.
- Results remain observable for twenty seconds before the existing completion flow. Assistance confirmation distinguishes recording a request from connecting to a live operator.
- Physical passing traffic retains a fixed actor pool. After an off-screen reset, old snapshots are ignored for three frames; late samples cannot insert a car in the visible forward corridor.

## Verification and limitations

The local test suite and isolated English/Chinese browser fixtures cover the changed request flow and translation regression. Browser fixtures use mocked state and acknowledgements, not real vehicle control. Actual 5-minute traffic continuity, no-collision shoulder approach, driving comfort, iPad audio, three-view rendering and motion hardware need separate live verification. Existing voice tone and intonation have not been regenerated. No claim is made of a working remote-operator service.

## Applying

Stop the owned application before updating. Pull this shared branch into the code checkout, then apply the reviewed source files to the installed `live` folder and restart the normal profile. A Git pull does not automatically replace a different runtime folder. Verify the revision on `/state`. Existing Drive ZIP packages are not automatically refreshed by this commit. Keep `lab.local.json`, participant records, audio banks and hardware settings unchanged.
