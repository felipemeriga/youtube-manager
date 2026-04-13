# Thumbnail Pipeline Redesign — 3-Step Workflow

**Goal:** Replace the single-step thumbnail generation with a 3-step pipeline where the user approves each layer: (1) Background + Logo, (2) Person Photo Compositing, (3) Typography overlay.

## Step 1: Background + Logo Generation (Gemini)

Gemini generates ONLY the background imagery + logo placement. No person, no text.

- Topic research (Haiku) still happens first for background visual ideas
- Prompt explicitly says: "Generate ONLY the background. Do NOT add any person or text."
- Logo is provided and placed in its reference position
- User previews, can approve or ask for regeneration

**Output:** Background image (PNG) stored in temp storage

## Step 2: Person Photo Compositing (Pillow)

Show the user a grid of ALL their personal photos with semantic matches highlighted (top 3-5 at the top, rest below).

- User clicks a photo to select it
- Backend composites the selected photo onto the approved background using Pillow
- Person is placed in the position determined from reference analysis (stored from one-time analysis)
- User previews the composite, can re-pick a different photo

**Output:** Background + person composite (PNG)

## Step 3: Typography Overlay (Pillow)

Pillow overlays the title text using the user's actual font file.

- Font file uploaded to a new `fonts` asset bucket
- Text styling (size ratio, color, position, stroke, shadow) determined by one-time reference analysis and stored in `channel_personas` as `text_style` JSONB
- Pillow renders the text with exact styling
- User previews final thumbnail, can approve (save) or go back

**Output:** Final thumbnail (PNG)

## Reference Style Analysis (One-Time)

When reference thumbnails are uploaded (or via a "Re-analyze" button), Haiku vision analyzes them and extracts:

```json
{
  "person_position": "right",
  "person_size": "60%",
  "person_vertical": "bottom-aligned",
  "text_position": "left",
  "text_vertical": "center",
  "text_color": "#FFFFFF",
  "text_stroke_color": "#000000",
  "text_stroke_width": 3,
  "text_shadow": true,
  "text_size_ratio": 0.08,
  "text_max_width_ratio": 0.55,
  "logo_position": "top-left",
  "logo_size_ratio": 0.08
}
```

Stored in `channel_personas.text_style` (JSONB column).

## Pipeline Message Types

New message types for the multi-step flow:

- `background` — Step 1 result (background + logo image)
- `photo_grid` — Step 2 prompt (shows photo selection grid)
- `composite` — Step 2 result (background + person)
- `final_thumbnail` — Step 3 result (complete thumbnail)

## Backend Changes

### New Dependencies
- `Pillow` for image compositing and text overlay

### New/Modified Files
- `backend/services/thumbnail_pipeline.py` — rewrite to 3-step flow
- `backend/services/image_compositor.py` — NEW: Pillow-based compositing + text overlay
- `backend/services/reference_analyzer.py` — NEW: one-time Haiku analysis of reference style
- `backend/services/nano_banana.py` — update prompt to generate background only
- `backend/routes/assets.py` — add `fonts` bucket, add reference analysis endpoint
- `backend/db/schema.sql` — add `text_style` JSONB to channel_personas

### Frontend Changes
- `frontend/src/components/PhotoGrid.tsx` — NEW: photo selection grid with highlighted matches
- `frontend/src/components/MessageBubble.tsx` — handle new message types
- `frontend/src/pages/ChatPage.tsx` — handle photo selection + step progression
- `frontend/src/pages/AssetsPage.tsx` — add fonts bucket + analyze button on references

## Out of Scope
- Drag-and-drop photo positioning
- Custom text editing in the preview
- Multiple text layers
