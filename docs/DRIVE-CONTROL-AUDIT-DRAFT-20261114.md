# DRAFT — driving control audit

Do not use this branch as a participant-test or motion-platform release. Live congestion driving reproduced lane departure and then another collision after the projection optimization. Passing source/UI tests is not evidence of safe or correct driving.

This branch isolates a local scalar road-projection draft, diagnostic controller timings and collision/restart guards. Actual traffic-following, asynchronous-clock consistency, background-traffic headway, lane-change traffic manipulation and all scenario transitions require further repair and live verification. No long-run no-collision claim is made.

Keep the UX/audio work separate from baseline driving control. Rebuild validation from one physical ego, then a lead vehicle, then traffic groups and only then interaction actions and the multi-view HMI. Do not merge this draft into the shared deployment branch until these live checks pass.
