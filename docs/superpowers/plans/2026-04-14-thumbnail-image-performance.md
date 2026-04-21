# Thumbnail Image Performance & Quality Tiers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce SSE payload sizes from ~10MB to ~10KB per image, add user-selectable quality tiers (Fast/Balanced/Quality), progressive image loading, and a download button for full-res images.

**Architecture:** Three layers of change: (1) Backend state + Gemini calls gain a configurable quality tier (model + resolution), (2) Upload pipeline generates 720p JPEG previews alongside originals, SSE sends tiny 200px base64 + preview URL instead of full image, (3) Frontend adds a tier selector, progressive image loading (blur → 720p), and download button.

**Tech Stack:** Python/FastAPI, Pillow (PIL), Google Gemini API, React/MUI/TypeScript, Supabase Storage

---

### Task 1: Add quality tier config to backend state

**Files:**
- Modify: `backend/services/thumbnail_state.py`
- Test: `backend/tests/test_thumbnail_state.py`

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_thumbnail_state.py`, add:

```python
from services.thumbnail_state import QUALITY_TIERS, ThumbnailState


def test_quality_tiers_config():
    assert "fast" in QUALITY_TIERS
    assert "balanced" in QUALITY_TIERS
    assert "quality" in QUALITY_TIERS
    for tier in QUALITY_TIERS.values():
        assert "model" in tier
        assert "image_size" in tier


def test_state_has_quality_tier():
    state = ThumbnailState(
        conversation_id="c",
        user_id="u",
        topic="t",
        topic_research="",
        platforms=["youtube"],
        background_urls={},
        photo_name=None,
        composite_urls={},
        final_urls={},
        thumb_text=None,
        user_input="",
        user_intent=None,
        extra_instructions=None,
        photo_list=[],
        uploaded_image_url=None,
        quality_tier="balanced",
    )
    assert state["quality_tier"] == "balanced"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_thumbnail_state.py -v`
Expected: FAIL — `QUALITY_TIERS` not importable, `quality_tier` not in TypedDict

- [ ] **Step 3: Implement quality tier config**

In `backend/services/thumbnail_state.py`, add `QUALITY_TIERS` dict and `quality_tier` field to `ThumbnailState`:

```python
QUALITY_TIERS = {
    "fast": {"model": "gemini-3.1-flash-image-preview", "image_size": "1K"},
    "balanced": {"model": "gemini-3-pro-image-preview", "image_size": "1K"},
    "quality": {"model": "gemini-3-pro-image-preview", "image_size": "4K"},
}
```

Add to `ThumbnailState` class:
```python
    # Quality tier: "fast", "balanced", "quality"
    quality_tier: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_thumbnail_state.py -v`
Expected: PASS

- [ ] **Step 5: Update existing tests that construct ThumbnailState**

The `make_base_state()` helper in `backend/tests/test_thumbnail_nodes.py` and any other test files that construct `ThumbnailState` need the new `quality_tier` field. Add `quality_tier="balanced"` to the defaults dict in `make_base_state()`.

Also update `backend/tests/test_thumbnail_graph.py` and `backend/tests/test_thumbnail_integration.py` — search for any `ThumbnailState(` or dict construction that initializes state and add the field.

- [ ] **Step 6: Run all thumbnail tests to verify nothing broke**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_thumbnail_state.py backend/tests/test_thumbnail_nodes.py backend/tests/test_thumbnail_graph.py backend/tests/test_thumbnail_integration.py -v`
Expected: ALL PASS

- [ ] **Step 7: Lint and commit**

```bash
backend/.venv/bin/ruff check --fix backend/ && backend/.venv/bin/ruff format backend/
git add backend/services/thumbnail_state.py backend/tests/test_thumbnail_state.py backend/tests/test_thumbnail_nodes.py backend/tests/test_thumbnail_graph.py backend/tests/test_thumbnail_integration.py
git commit -m "feat: add quality tier config and state field for thumbnail generation"
```

---

### Task 2: Wire quality tier into Gemini generation calls

**Files:**
- Modify: `backend/services/nano_banana.py`
- Modify: `backend/services/thumbnail_nodes.py`
- Test: `backend/tests/test_thumbnail_nodes.py`

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_thumbnail_nodes.py`, add a test that verifies the model from quality tier is passed to generate_background:

```python
@pytest.mark.asyncio
async def test_generate_background_uses_quality_tier_model():
    from services.thumbnail_nodes import generate_background_node

    state = make_base_state(topic="Test topic", quality_tier="fast")
    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch(
        "services.thumbnail_nodes._research_topic",
        new_callable=AsyncMock,
        return_value="",
    ):
        with patch(
            "services.thumbnail_nodes.get_relevant_memories",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with patch(
                "services.thumbnail_nodes._get_supabase", new_callable=AsyncMock
            ) as mock_sb:
                sb = MagicMock()
                mock_sb.return_value = sb
                sb.storage.from_.return_value.list = AsyncMock(return_value=[])
                sb.storage.from_.return_value.upload = AsyncMock()
                with patch(
                    "services.thumbnail_nodes.generate_background",
                    new_callable=AsyncMock,
                    return_value=fake_image,
                ) as mock_gen:
                    await generate_background_node(state)

    # Verify model from "fast" tier was passed
    call_kwargs = mock_gen.call_args[1]
    assert call_kwargs["model"] == "gemini-3.1-flash-image-preview"
    assert call_kwargs["image_size"] == "1K"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_thumbnail_nodes.py::test_generate_background_uses_quality_tier_model -v`
Expected: FAIL — `model` not in call kwargs

- [ ] **Step 3: Add `model` parameter to nano_banana functions**

In `backend/services/nano_banana.py`, add `model: str = "gemini-3-pro-image-preview"` parameter to all three functions (`generate_background`, `composite_with_effects`, `add_text_with_style`). Replace the hardcoded model string in each `client.models.generate_content()` call with the `model` parameter.

For `generate_background`:
```python
async def generate_background(
    prompt: str,
    reference_images: list[bytes],
    logos: list[bytes] | None = None,
    previous_image: bytes | None = None,
    model: str = "gemini-3-pro-image-preview",
    aspect_ratio: str = "16:9",
    image_size: str = "4K",
) -> bytes:
```

Then change `model="gemini-3-pro-image-preview"` in the `generate_content` call to `model=model`.

Repeat for `composite_with_effects` and `add_text_with_style`.

- [ ] **Step 4: Wire quality tier in thumbnail_nodes.py**

In `backend/services/thumbnail_nodes.py`, import `QUALITY_TIERS` from `thumbnail_state`:

```python
from services.thumbnail_state import PLATFORM_CONFIGS, DEFAULT_PLATFORMS, QUALITY_TIERS, ThumbnailState
```

In each generation node (`generate_background_node`, `composite_node`, `add_text_node`), read the tier config and pass `model` + `image_size`:

```python
tier = QUALITY_TIERS.get(state.get("quality_tier") or "balanced", QUALITY_TIERS["balanced"])
```

Then in the inner generation function, use `tier["image_size"]` instead of `cfg["image_size"]`, and pass `model=tier["model"]`:

For `generate_background_node`, the `_gen_bg` inner function becomes:
```python
async def _gen_bg(platform: str) -> tuple[str, bytes]:
    cfg = PLATFORM_CONFIGS[platform]
    bg_bytes = await generate_background(
        prompt=prompt,
        reference_images=ref_thumbs,
        logos=logos,
        previous_image=previous_bgs.get(platform),
        model=tier["model"],
        aspect_ratio=cfg["aspect_ratio"],
        image_size=tier["image_size"],
    )
    return platform, bg_bytes
```

Apply the same pattern to `composite_node` and `add_text_node`.

- [ ] **Step 5: Run test to verify it passes**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_thumbnail_nodes.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run all thumbnail tests**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_thumbnail_state.py backend/tests/test_thumbnail_nodes.py backend/tests/test_thumbnail_graph.py backend/tests/test_thumbnail_integration.py -v`
Expected: ALL PASS

- [ ] **Step 7: Lint and commit**

```bash
backend/.venv/bin/ruff check --fix backend/ && backend/.venv/bin/ruff format backend/
git add backend/services/nano_banana.py backend/services/thumbnail_nodes.py backend/tests/test_thumbnail_nodes.py
git commit -m "feat: wire quality tier model and resolution into Gemini generation calls"
```

---

### Task 3: Generate 720p preview at upload time

**Files:**
- Modify: `backend/services/thumbnail_nodes.py`
- Test: `backend/tests/test_thumbnail_nodes.py`

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_thumbnail_nodes.py`, add:

```python
@pytest.mark.asyncio
async def test_upload_image_creates_preview():
    from services.thumbnail_nodes import _upload_image_with_preview

    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch(
        "services.thumbnail_nodes._get_supabase", new_callable=AsyncMock
    ) as mock_sb:
        sb = MagicMock()
        mock_sb.return_value = sb
        sb.storage.from_.return_value.upload = AsyncMock()

        with patch("services.thumbnail_nodes._make_preview", return_value=b"preview-jpg"):
            original_path, preview_path = await _upload_image_with_preview(
                "user-1", "bg_youtube", fake_image
            )

    assert original_path.startswith("user-1/bg_youtube_")
    assert original_path.endswith(".png")
    assert preview_path.startswith("user-1/preview_bg_youtube_")
    assert preview_path.endswith(".jpg")
    # Two uploads: original + preview
    assert sb.storage.from_.return_value.upload.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_thumbnail_nodes.py::test_upload_image_creates_preview -v`
Expected: FAIL — `_upload_image_with_preview` not defined

- [ ] **Step 3: Implement preview generation**

In `backend/services/thumbnail_nodes.py`, add PIL import at the top:

```python
import io
from PIL import Image
```

Add the `_make_preview` helper:

```python
def _make_preview(image_bytes: bytes, max_edge: int = 720) -> bytes:
    """Resize image to max_edge on longest side, return as JPEG bytes."""
    img = Image.open(io.BytesIO(image_bytes))
    img.thumbnail((max_edge, max_edge), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=80)
    return buf.getvalue()
```

Add `_upload_image_with_preview`:

```python
async def _upload_image_with_preview(
    user_id: str, prefix: str, image_bytes: bytes
) -> tuple[str, str]:
    """Upload original image and 720p JPEG preview. Returns (original_path, preview_path)."""
    sb = await _get_supabase()
    name_id = uuid.uuid4().hex[:8]
    original_name = f"{prefix}_{name_id}.png"
    preview_name = f"preview_{prefix}_{name_id}.jpg"
    original_path = f"{user_id}/{original_name}"
    preview_path = f"{user_id}/{preview_name}"

    await sb.storage.from_("outputs").upload(
        original_path, image_bytes, {"content-type": "image/png"}
    )

    try:
        preview_bytes = _make_preview(image_bytes)
        await sb.storage.from_("outputs").upload(
            preview_path, preview_bytes, {"content-type": "image/jpeg"}
        )
    except Exception:
        logger.warning("preview upload failed for %s, skipping", original_path)
        preview_path = ""

    return original_path, preview_path
```

- [ ] **Step 4: Replace `_upload_image` calls with `_upload_image_with_preview`**

Update the state dicts to store both original and preview paths. Change the `background_urls`, `composite_urls`, and `final_urls` values from `str` to `dict` with `url` and `preview_url` keys.

In `thumbnail_state.py`, update the type hints:

```python
    # Artifacts per platform: {"youtube": {"url": "path", "preview_url": "path"}, ...}
    background_urls: dict[str, dict[str, str]]
    composite_urls: dict[str, dict[str, str]]
    final_urls: dict[str, dict[str, str]]
```

Update `generate_background_node`:
```python
background_urls = {}
for platform, bg_bytes in gen_results:
    original_path, preview_path = await _upload_image_with_preview(
        user_id, f"bg_{platform}", bg_bytes
    )
    background_urls[platform] = {"url": original_path, "preview_url": preview_path}
```

Apply the same pattern to `composite_node` and `add_text_node`.

Also update `save_node` to handle the new dict format:
```python
for platform, paths in final_urls.items():
    temp_url = paths["url"] if isinstance(paths, dict) else paths
    ...
    saved_urls[platform] = {"url": final_path, "preview_url": ""}
```

Update all places that READ from these dicts (e.g., `composite_node` reading `background_urls`, `add_text_node` reading `composite_urls`, and the previous-image download logic) to use `paths["url"]` instead of the raw string.

- [ ] **Step 5: Update all tests for new dict format**

Update `make_base_state` defaults and all test assertions that reference `background_urls`, `composite_urls`, `final_urls` to use the `{"url": "...", "preview_url": "..."}` format.

For example in `test_composite_node_returns_url`:
```python
state = make_base_state(
    background_urls={"youtube": {"url": "user-1/bg_abc.png", "preview_url": "user-1/preview_bg_abc.jpg"}},
    photo_name="photo1.jpg",
)
```

And assertions become:
```python
assert result["composite_urls"]["youtube"]["url"].startswith("user-1/comp_")
assert result["composite_urls"]["youtube"]["preview_url"].startswith("user-1/preview_comp_")
```

- [ ] **Step 6: Run all thumbnail tests**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_thumbnail_state.py backend/tests/test_thumbnail_nodes.py backend/tests/test_thumbnail_graph.py backend/tests/test_thumbnail_integration.py -v`
Expected: ALL PASS

- [ ] **Step 7: Lint and commit**

```bash
backend/.venv/bin/ruff check --fix backend/ && backend/.venv/bin/ruff format backend/
git add backend/services/thumbnail_state.py backend/services/thumbnail_nodes.py backend/tests/
git commit -m "feat: generate 720p JPEG preview alongside original at upload time"
```

---

### Task 4: Update SSE to send tiny preview + URLs

**Files:**
- Modify: `backend/routes/chat.py`

- [ ] **Step 1: Add tiny preview helper**

At the top of `backend/routes/chat.py`, add:

```python
from services.thumbnail_nodes import _make_preview
```

- [ ] **Step 2: Update the image SSE event block**

In `thumbnail_stream()`, replace the block that downloads and base64-encodes full images (lines ~211-264) with the new progressive approach.

Replace the image download + base64 block:

```python
if msg_type in ("background", "composite", "image"):
    image_urls = interrupt_value.get("image_urls") or {}
    if image_urls:
        images_payload = {}
        for platform, paths in image_urls.items():
            url = paths["url"] if isinstance(paths, dict) else paths
            preview_url = paths.get("preview_url", "") if isinstance(paths, dict) else ""

            # Download preview (or original as fallback) for tiny base64
            preview_data = None
            for attempt in range(3):
                try:
                    dl_path = preview_url or url
                    preview_data = await sb.storage.from_("outputs").download(dl_path)
                    break
                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(1)

            if not preview_data:
                continue

            # Generate tiny ~200px placeholder for SSE
            try:
                tiny_bytes = _make_preview(preview_data, max_edge=200)
                tiny_b64 = base64.b64encode(tiny_bytes).decode()
            except Exception:
                # Fallback: send full preview as base64
                tiny_b64 = base64.b64encode(preview_data).decode()

            images_payload[platform] = {
                "preview_base64": tiny_b64,
                "preview_url": preview_url,
                "url": url,
            }

        if not images_payload:
            yield sse_event({"error": "Falha ao baixar imagem", "done": True})
            return

        # Save assistant message
        labels = {
            "background": "Aqui está o fundo.",
            "composite": "Aqui está a composição.",
            "image": "Aqui está sua thumbnail final!",
        }
        first_paths = next(iter(image_urls.values()))
        first_url = first_paths["url"] if isinstance(first_paths, dict) else first_paths
        await _save_message(
            sb, conversation_id, "assistant",
            labels.get(msg_type, ""), msg_type,
            image_url=first_url,
        )

        # Backward compat fields
        first_payload = next(iter(images_payload.values()))
        yield sse_event({
            "done": True,
            "message_type": msg_type,
            "images": images_payload,
            "image_base64": first_payload["preview_base64"],
            "image_url": first_url,
        })
        return
```

- [ ] **Step 3: Wire quality_tier from request into graph state**

In `ChatRequest` model, add:
```python
quality_tier: str | None = None
```

In the fresh start block of `thumbnail_stream`, add `quality_tier` to the initial state dict:
```python
"quality_tier": quality_tier or "balanced",
```

Add `quality_tier` parameter to `thumbnail_stream` function signature and pass from the router.

For resume (interrupt), update the state with the new tier if provided. After `result = await graph.ainvoke(Command(resume=resume_value), config)`, add an update if quality_tier changed — actually, the simpler approach is to pass `quality_tier` in the initial state and let the user update it via the request. Add a state update before resume:

```python
if quality_tier:
    await graph.aupdate_state(config, {"quality_tier": quality_tier})
```

- [ ] **Step 4: Update the chat endpoint to pass quality_tier**

In the `chat()` endpoint, pass `quality_tier` to `thumbnail_stream`:
```python
stream = thumbnail_stream(
    conversation_id=request.conversation_id,
    content=request.content,
    user_id=user_id,
    image_url=request.image_url,
    platforms=request.platforms,
    quality_tier=request.quality_tier,
)
```

- [ ] **Step 5: Run all backend tests**

Run: `backend/.venv/bin/python -m pytest backend/tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Lint and commit**

```bash
backend/.venv/bin/ruff check --fix backend/ && backend/.venv/bin/ruff format backend/
git add backend/routes/chat.py
git commit -m "feat: send tiny preview base64 in SSE and wire quality_tier from request"
```

---

### Task 5: Frontend — quality tier selector

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/ChatInput.tsx`
- Modify: `frontend/src/components/ChatArea.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`

- [ ] **Step 1: Add quality_tier to API client**

In `frontend/src/lib/api.ts`, update `streamChat` to accept and send `qualityTier`:

Add to function signature:
```typescript
export async function streamChat(
  conversationId: string,
  content: string,
  type: string,
  callbacks: StreamCallbacks,
  imageUrl?: string,
  platforms?: string[],
  qualityTier?: string,
): Promise<void> {
```

Add to body construction:
```typescript
if (qualityTier) body.quality_tier = qualityTier;
```

Update `StreamCallbacks` interface — update `onImages` to match new payload:
```typescript
onImages?: (images: Record<string, { preview_base64?: string; preview_url?: string; url?: string; base64?: string }>) => void;
```

- [ ] **Step 2: Add quality tier selector to ChatInput**

In `frontend/src/components/ChatInput.tsx`, add quality tier props and a segmented control.

Add to `ChatInputProps`:
```typescript
qualityTier?: string;
onQualityTierChange?: (tier: string) => void;
showQualityTier?: boolean;
```

Add the segmented control in the input bar area (above the text field row, next to the model selector). Use MUI `ToggleButtonGroup`:

```typescript
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import BoltIcon from "@mui/icons-material/Bolt";
import BalanceIcon from "@mui/icons-material/Balance";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
```

```tsx
{showQualityTier && onQualityTierChange && (
  <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
    <ToggleButtonGroup
      value={qualityTier || "balanced"}
      exclusive
      onChange={(_, val) => val && onQualityTierChange(val)}
      size="small"
      sx={{
        "& .MuiToggleButton-root": {
          fontSize: "0.7rem",
          py: 0.25,
          px: 1.5,
          color: "rgba(255,255,255,0.5)",
          borderColor: "rgba(255,255,255,0.1)",
          textTransform: "none",
          "&.Mui-selected": {
            color: "#a78bfa",
            backgroundColor: "rgba(124,58,237,0.15)",
            borderColor: "rgba(124,58,237,0.3)",
          },
        },
      }}
    >
      <ToggleButton value="fast">
        <Tooltip title="Gemini Flash · 1K">
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            <BoltIcon sx={{ fontSize: 14 }} /> Rapido
          </Box>
        </Tooltip>
      </ToggleButton>
      <ToggleButton value="balanced">
        <Tooltip title="Gemini Pro · 1K">
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            <BalanceIcon sx={{ fontSize: 14 }} /> Balanceado
          </Box>
        </Tooltip>
      </ToggleButton>
      <ToggleButton value="quality">
        <Tooltip title="Gemini Pro · 4K">
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            <AutoAwesomeIcon sx={{ fontSize: 14 }} /> Qualidade
          </Box>
        </Tooltip>
      </ToggleButton>
    </ToggleButtonGroup>
  </Box>
)}
```

- [ ] **Step 3: Wire quality tier through ChatArea**

In `frontend/src/components/ChatArea.tsx`, add quality tier props:

```typescript
interface ChatAreaProps {
  // ... existing props
  qualityTier?: string;
  onQualityTierChange?: (tier: string) => void;
  showQualityTier?: boolean;
}
```

Pass them to `ChatInput`:
```tsx
<ChatInput
  onSend={onSend}
  disabled={isStreaming}
  models={models}
  selectedModel={selectedModel}
  onModelChange={onModelChange}
  qualityTier={qualityTier}
  onQualityTierChange={onQualityTierChange}
  showQualityTier={showQualityTier}
/>
```

- [ ] **Step 4: Wire quality tier in ChatPage**

In `frontend/src/pages/ChatPage.tsx`:

Add state:
```typescript
const [qualityTier, setQualityTier] = useState("balanced");
```

Pass to `streamChat` calls — update `doStream`:
```typescript
await streamChat(conversationId, content, type, {
  // ... callbacks
}, imageUrl, platforms, qualityTier);
```

Pass to `ChatArea`:
```tsx
<ChatArea
  // ... existing props
  qualityTier={qualityTier}
  onQualityTierChange={setQualityTier}
  showQualityTier={conversationMode === "thumbnail"}
/>
```

- [ ] **Step 5: Lint and commit**

```bash
cd frontend && npx eslint --fix src/ && npx prettier --write src/
git add frontend/src/lib/api.ts frontend/src/components/ChatInput.tsx frontend/src/components/ChatArea.tsx frontend/src/pages/ChatPage.tsx
git commit -m "feat: add quality tier selector UI for thumbnail generation"
```

---

### Task 6: Frontend — progressive image loading and download button

**Files:**
- Modify: `frontend/src/components/MessageBubble.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`

- [ ] **Step 1: Update Message interface**

In both `frontend/src/pages/ChatPage.tsx` and `frontend/src/components/MessageBubble.tsx`, update the `Message` interface:

```typescript
interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  type: string;
  image_url?: string | null;
  image_base64?: string;
  images?: Record<string, {
    preview_base64?: string;
    preview_url?: string;
    url?: string;
    base64?: string;  // backward compat
  }>;
}
```

- [ ] **Step 2: Rewrite AuthOutputImage for progressive loading**

In `frontend/src/components/MessageBubble.tsx`, rewrite the `AuthOutputImage` component. Add `DownloadIcon` import:

```typescript
import DownloadIcon from "@mui/icons-material/Download";
```

Update the component props and implementation:

```typescript
function AuthOutputImage({
  previewBase64,
  previewUrl,
  originalUrl,
  base64,
  storagePath,
}: {
  previewBase64?: string;
  previewUrl?: string;
  originalUrl?: string;
  base64?: string;       // backward compat
  storagePath?: string;   // backward compat
}) {
  // Priority: previewBase64 (instant) → fetch previewUrl (720p) → base64 fallback → fetch storagePath
  const initialSrc = previewBase64
    ? `data:image/jpeg;base64,${previewBase64}`
    : base64
      ? `data:image/png;base64,${base64}`
      : null;

  const [src, setSrc] = useState<string | null>(initialSrc);
  const [loading, setLoading] = useState(!initialSrc);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    // Fetch the 720p preview to replace the tiny placeholder
    const fetchPath = previewUrl || storagePath;
    if (!fetchPath) return;
    // If we already have full base64 (old flow), skip preview fetch
    if (base64 && !previewBase64) return;

    let revoke: string | null = null;
    const fetchPreview = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const filename = fetchPath.includes("/") ? fetchPath.split("/").pop()! : fetchPath;
      try {
        const res = await fetch(`/api/assets/outputs/${filename}`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (res.ok) {
          const blob = await res.blob();
          revoke = URL.createObjectURL(blob);
          setSrc(revoke);
        }
      } catch {
        // keep whatever we have
      }
      setLoading(false);
    };
    fetchPreview();

    return () => { if (revoke) URL.revokeObjectURL(revoke); };
  }, [previewUrl, storagePath, base64, previewBase64]);

  const handleDownload = async () => {
    const dlPath = originalUrl || storagePath;
    if (!dlPath) return;
    setDownloading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const filename = dlPath.includes("/") ? dlPath.split("/").pop()! : dlPath;
      const res = await fetch(`/api/assets/outputs/${filename}`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.ok) {
        const blob = await res.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
      }
    } catch {
      // silent fail
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ width: "100%", maxWidth: 512, height: 200, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 1, mb: 1, backgroundColor: "rgba(255,255,255,0.03)" }}>
        <CircularProgress size={24} sx={{ color: "#7c3aed" }} />
      </Box>
    );
  }

  if (!src) return null;

  return (
    <Box sx={{ position: "relative", display: "inline-block", mb: 1 }}>
      <Box
        component="img"
        src={src}
        alt="Thumbnail"
        sx={{ width: "100%", maxWidth: 512, borderRadius: 1, display: "block" }}
      />
      {(originalUrl || storagePath) && (
        <IconButton
          onClick={handleDownload}
          disabled={downloading}
          size="small"
          sx={{
            position: "absolute",
            bottom: 8,
            right: 8,
            backgroundColor: "rgba(0,0,0,0.6)",
            color: "#fff",
            "&:hover": { backgroundColor: "rgba(0,0,0,0.8)" },
            width: 32,
            height: 32,
          }}
        >
          {downloading ? <CircularProgress size={16} sx={{ color: "#fff" }} /> : <DownloadIcon sx={{ fontSize: 18 }} />}
        </IconButton>
      )}
    </Box>
  );
}
```

Add `IconButton` to the MUI import at the top of the file.

- [ ] **Step 3: Update image rendering in MessageBubble**

Update where `AuthOutputImage` is used in `MessageBubble` to pass the new props:

Multi-platform block:
```tsx
{message.images && Object.keys(message.images).length > 1 ? (
  <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: 1 }}>
    {Object.entries(message.images).map(([platform, img]) => (
      <Box key={platform} sx={{ flex: "1 1 0", minWidth: 150 }}>
        <Typography variant="caption" sx={{ color: "#a78bfa", mb: 0.5, display: "block" }}>
          {platformLabels[platform] || platform}
        </Typography>
        <AuthOutputImage
          previewBase64={img.preview_base64}
          previewUrl={img.preview_url}
          originalUrl={img.url}
          base64={img.base64}
          storagePath={img.url || ""}
        />
      </Box>
    ))}
  </Box>
) : (
  (message.image_base64 || message.image_url || (message.images && Object.keys(message.images).length === 1)) && (
    (() => {
      const singleImg = message.images ? Object.values(message.images)[0] : null;
      return (
        <AuthOutputImage
          previewBase64={singleImg?.preview_base64}
          previewUrl={singleImg?.preview_url}
          originalUrl={singleImg?.url}
          base64={message.image_base64 || singleImg?.base64}
          storagePath={message.image_url || singleImg?.url || ""}
        />
      );
    })()
  )
)}
```

- [ ] **Step 4: Update ChatPage onDone handler for new image format**

In `frontend/src/pages/ChatPage.tsx`, update the `onDone` callback to handle the new image payload structure:

```typescript
onDone: (data) => {
  const messageType = (data.message_type as string) || "text";
  const newMessage: Message = {
    role: "assistant",
    content: streamingRef.current || (data.content as string) || "",
    type: messageType,
  };
  if (imagesRef.current) {
    newMessage.images = imagesRef.current;
    // Backward compat fields from first platform
    const firstImg = Object.values(imagesRef.current)[0];
    if (firstImg) {
      newMessage.image_base64 = firstImg.preview_base64 || firstImg.base64;
      newMessage.image_url = firstImg.url;
    }
  } else if (imageRef.current) {
    newMessage.image_base64 = imageRef.current.base64;
    newMessage.image_url = imageRef.current.url;
  }
  // ... rest unchanged
```

- [ ] **Step 5: Lint and commit**

```bash
cd frontend && npx eslint --fix src/ && npx prettier --write src/
git add frontend/src/components/MessageBubble.tsx frontend/src/pages/ChatPage.tsx
git commit -m "feat: progressive image loading with download button in chat"
```

---

### Task 7: Final integration verification and push

- [ ] **Step 1: Run all backend tests**

Run: `backend/.venv/bin/python -m pytest backend/tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run frontend lint**

Run: `cd frontend && npx eslint src/ && npx prettier --check src/`
Expected: No errors

- [ ] **Step 3: Push all commits**

```bash
git push
```
