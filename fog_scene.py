"""Small native fog scene cast; preserves the recorded roadside truck."""
# Same-scene hatchback; closer source coverage and a less diffuse rear silhouette.
LEAD_TRACK_ID='14'
CONTEXT_TRACK_IDS=('7','36')
ONSET_SECONDS=10.
BASE_GAP_M=8.
FOG_BUILDUP_SECONDS=5.
EXTINCTION_TIMES=(ONSET_SECONDS,ONSET_SECONDS+FOG_BUILDUP_SECONDS,300.)
EXTINCTION_BETAS=(0.,.20,.20)
