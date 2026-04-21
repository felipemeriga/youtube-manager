# Thumbnail Image Performance & Quality Tiers

**Date**: 2026-04-14
**Branch**: feat/multi-platform-thumbnails
**Status**: Approved

## Problem

1. **Missing images in chat**: Multi-platform thumbnail generation sends full 4K PNGs as base64 over SSE. A single 4K PNG can be 5-10MB; as base64 that's ~7-14MB per image. With 3 platforms, SSE events reach 20-40MB, causing images to silently fail to appear.
2. **Slow iteration**: All images are generated at 4K using `gemini-3-pro-image-preview` regardless of whether the user is exploring ideas or ready for final output.
3. **No download option**: Users can't download the full-resolution image from the chat.

## Solution

Three changes working together:

### 1. Quality Tier Selector

User-selectable quality tier, switchable at any step (like switching between Haiku/Opus).

| Tier | Label | Model | Resolution |
|------|-------|-------|-----------|
| Fast | Rapido | `gemini-3.1-flash-image-preview` | 1K |
| Balanced | Balanceado | `gemini-3-pro-image-preview` | 1K |
| Quality | Qualidade | `gemini-3-pro-image-preview` | 4K |

- Default: **Balanced**
- Persisted in conversation state, survives page reloads
- Each step reads the current tier — user can switch mid-flow
- No forced re-generation on save; the saved file uses whatever tier the user selected
- Quality label shown below each image: e.g., "1K . Balanceado"

**State change**: Add `quality_tier: str` to `ThumbnailState` (default `"balanced"`).

**Tier config** (new dict in `thumbnail_state.py`):
```python
QUALITY_TIERS = {
    "fast":     {"model": "gemini-3.1-flash-image-preview", "image_size": "1K"},
    "balanced": {"model": "gemini-3-pro-image-preview",     "image_size": "1K"},
    "quality":  {"model": "gemini-3-pro-image-preview",     "image_size": "4K"},
}
```

**nano_banana.py**: All three generation functions receive `model` as a parameter instead of hardcoding it.

**thumbnail_nodes.py**: Each generation node reads `state["quality_tier"]`, looks up the tier config, passes `model` + `image_size` to nano_banana functions.

**chat.py**: Reads `quality_tier` from request payload, passes into graph state. On resume (feedback), updates the tier in state.

### 2. Progressive Image Loading (Preview Pipeline)

Replace full 4K base64 SSE payloads with a three-stage progressive loading approach.

**At upload time** (`_upload_image` in `thumbnail_nodes.py`):
1. Upload original image as today: `user_id/bg_youtube_abc123.png`
2. Resize to 720px on the longest edge (maintaining aspect ratio) as JPEG (quality 80) using PIL
3. Upload preview: `user_id/preview_bg_youtube_abc123.jpg`

**SSE events** (`chat.py`):
1. Download the 720p preview from Supabase (not the original)
2. Resize in-memory to ~200px tiny JPEG — base64 encode (~5-10KB)
3. Send in SSE payload per platform:
```python
{
  "preview_base64": "<tiny 200px JPEG>",
  "preview_url": "user_id/preview_bg_youtube_abc123.jpg",
  "url": "user_id/bg_youtube_abc123.png",
  "quality_tier": "balanced",
  "resolution": "1K"
}
```

**Frontend `AuthOutputImage`**:
1. Show `preview_base64` immediately (blurry but instant)
2. Fetch `preview_url` (720p) via `/api/assets/outputs/` — replace blurry preview
3. Download button fetches `url` (original full-res)

**Payload reduction**: From ~7-14MB per image down to ~5-10KB per image in SSE.

### 3. Download Button

A small download icon overlaid on the bottom-right corner of each image in the chat.

- On click: fetches the original from `/api/assets/outputs/{filename}` with auth header
- Triggers browser file save dialog
- Available on all image types (background, composite, final)

### Frontend UI Components

**Quality Tier Selector**: Segmented control near chat input:
```
[ lightning Rapido ] [ scales Balanceado ] [ palette Qualidade ]
```
- Tooltip on each option: model name + resolution
- Selected tier sent as `quality_tier` field with every chat message

**Quality Label**: Small text below each generated image showing the tier and resolution.

## Error Handling

- **Failed preview upload**: Fall back to sending the original as base64 (current behavior). Preview is an optimization, not a hard requirement.
- **Tier switching mid-flow**: Each step reads current `quality_tier` from state independently. No special handling needed.
- **Backward compatibility**: Old conversations without `quality_tier` default to `"balanced"`. Old messages without `preview_base64`/`preview_url` work via existing `image_base64`/`image_url` fallback.

## Files to Change

### Backend
- `backend/services/thumbnail_state.py` — Add `quality_tier` field, `QUALITY_TIERS` dict
- `backend/services/nano_banana.py` — Accept `model` parameter in all generation functions
- `backend/services/thumbnail_nodes.py` — Read tier config, generate 720p previews at upload, pass model to nano_banana
- `backend/routes/chat.py` — Read `quality_tier` from request, send progressive SSE payloads

### Frontend
- `frontend/src/lib/api.ts` — Send `quality_tier` in request, parse new SSE fields
- `frontend/src/pages/ChatPage.tsx` — Quality tier selector state, pass to API
- `frontend/src/components/MessageBubble.tsx` — Updated image fields, quality label, download button
- `frontend/src/components/AuthOutputImage.tsx` (or inline in MessageBubble) — Progressive loading: preview_base64 → preview_url fetch → download via url
