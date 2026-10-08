# MiniMax H3 on RunPod — preparation note

Status: **prepared only; not activated in production**.

This note captures the baseline for adding open-weight MiniMax H3 image-to-video
to Xiaoxia's existing RunPod + ComfyUI deployment without disturbing the
working Qwen Image 2.1 endpoint.

## Official baseline selected

Use the official Comfy-Org **MiniMax H3 Image to Video** workflow as the source
of truth.  The workflow uses `MiniMaxH3ImageToVideo` with a first frame and
native video+audio output.

Initial model set:

- `diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors`
- `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
- `vae/minimax_h3_video_vae_int8_convrot.safetensors`
- `vae/minimax_h3_audio_vae_fp32.safetensors`

Do **not** add Ref2VA for the first milestone.  Xiaoxia already has a completed
first-frame image; FL2VA is the correct first implementation.

## First validation target

Do not touch the Discord UI yet.  First prove the backend contract:

1. one PNG first frame;
2. one Chinese H3 director prompt;
3. 5-second I2V;
4. native stereo audio;
5. MP4 returned by RunPod worker-comfyui.

After that, increase to 10 seconds, then 15 seconds.

The official template currently demonstrates 1344×768 and 5 seconds, with H3's
native short edge around 768 px and dimensions rounded to multiples of 32.

## Reuse the existing Qwen worker architecture

Current Qwen worker already provides:

- RunPod Serverless endpoint authentication;
- official `runpod/worker-comfyui` handler;
- cached-model storage under `/runpod-volume/huggingface-cache/hub`;
- pinned ComfyUI replacement inside the worker image;
- job submit/status polling on the Zeabur side.

Current repository check: the Qwen worker pins ComfyUI commit `a7169322485d0049380fb207fa17e9fb3ec40486`, and that exact commit already contains `comfy_extras/nodes_minimax_h3.py` with the native `MiniMaxH3ImageToVideo` implementation.  Therefore the first H3 trial should **not** upgrade ComfyUI pre-emptively; reuse the pinned commit unless the official I2V API workflow proves a missing-node incompatibility.

Preferred deployment sequence:

1. inspect the current RunPod endpoint GPU / VRAM / cached model / storage;
2. clone the current template or endpoint for a non-production H3 test;
3. update ComfyUI only in the test worker if H3 nodes require a newer commit;
4. add the H3 cached model;
5. convert the official H3 I2V workflow to API format;
6. verify Qwen + H3 can coexist;
7. only then decide whether one endpoint should serve both workflows.

There is no reason to force a 24 GB configuration.  If the current Qwen
deployment is already a 48 GB-class GPU and the price is acceptable, use the
same GPU tier for first-pass H3 validation and optimize later.

## Future Discord contract

Keep one existing button:

`🎬 H3影片生成`

Then select provider:

- `fal.ai`
- `RunPod`
- `自動`

Provider routing and story semantics are independent.

`自動` means: try fal.ai first; on final fal.ai failure, immediately try
RunPod without asking the user again.

The RunPod path is not limited to special images.  Ordinary images can also use
RunPod.  If the user manually sends an unsupported image to fal.ai and fal.ai
rejects it, that is a normal provider failure.

## H3 Director continuity contract

The current image is always frame 1 and visual truth.  For a derivative
Love-Intent / 情不自禁 image, inherit the original scene as story truth.

Natural-language Director rules should be Chinese.  Programmatic trace keys can
remain English.

Core solo-subject rules:

- the whole clip contains Xiaoxia only;
- no man, no second woman, no other person's hand/arm/leg/body/reflection;
- do not imply an unseen second person is touching or interacting with Xiaoxia;
- no intercourse or explicit sex act;
- sensuality is expressed through Xiaoxia's own gaze, expression, posture,
  movement and self-directed gestures;
- preserve the current frame's scene, pose/camera logic and spatial continuity.

For a derivative scene, the wardrobe/body-state change is already complete
before frame 1.  H3 must continue the same scene rather than explain the change.

## Trace fields planned

At minimum:

- `provider_requested`
- `provider_attempted`
- `provider_final`
- `h3_backend=open_weights_comfyui`
- `checkpoint_family=FL2VA`
- checkpoint filenames
- first-frame SHA-256
- final H3 prompt
- duration / width / height / steps
- `scene_inheritance`
- `solo_subject_lock`
- RunPod job id
- terminal status and returned video metadata

## Known follow-up: /photo auto mode

The current Love Intent auto path is not truly automatic.  The code says
"Seedream first; if it ultimately fails, let the user decide whether to switch
to Qwen-2.1", and the installed fallback module intentionally renders an
explicit-confirmation button.

This should be changed separately so that **auto** really means:

`Seedream -> failure -> RunPod/Qwen-2.1`

with no second confirmation.

Do not confuse this fix with H3 provider routing; they should share the same UX
principle but remain separate implementations.


## Preparation completed in repository

The repository now also contains:

- `xiaoxia/serverless/workflows/minimax_h3_fl2va_api.json`
  - API-format first-frame FL2VA graph derived from the official Comfy-Org H3 I2V template.
  - Baseline: 864×480, 5 seconds, 20 steps, `res_multistep` + `simple`.
  - Output is explicit MP4 through ComfyUI `SaveVideo`.
- `xiaoxia/serverless/validate_h3_workflow.py`
  - offline graph-contract validation; no RunPod login/GPU required.
- `xiaoxia/media/h3_runpod.py`
  - inactive RunPod submit/poll/decode client.
  - supports a separate `XIAOXIA_H3_RUNPOD_ENDPOINT_ID` and falls back to the existing RunPod endpoint id.
- `xiaoxia/video/h3_provider_router.py`
  - inactive provider routing primitive for `fal.ai | RunPod | auto`.
  - auto is true automatic fallback: fal.ai failure immediately tries RunPod with no second confirmation.
  - contains the Chinese solo-subject / scene-continuation Director contract.

### Important worker-comfyui compatibility finding

A custom video-return handler is **not required** for the current worker-comfyui transport.

At the pinned ComfyUI commit, `PreviewVideo.as_dict()` intentionally serializes
saved video results under the UI key `images` with `animated=true`.
RunPod worker-comfyui already processes `output.images[]` by fetching each
saved result through ComfyUI's `/view` endpoint, preserving the original file
extension, and returning the bytes as base64 when S3 output is not configured.

Therefore an H3 `SaveVideo` result such as `.mp4` can travel through the
existing worker response shape:

`output.images[] -> { filename: "*.mp4", type: "base64", data: "..." }`

The inactive H3 client already decodes that contract and rejects non-video
extensions.

### Activation boundary

Nothing above is imported by `xiaoxia_runtime_flat.py` yet.
The existing fal.ai H3 flow and Qwen-2.1 RunPod flow remain unchanged.

Before activation, the only remaining infrastructure facts to verify in RunPod are:

1. current endpoint GPU / VRAM;
2. cached-model storage capacity and model id layout;
3. whether H3 should be added to a cloned test endpoint first or directly to
   the existing template after a test clone proves coexistence.
