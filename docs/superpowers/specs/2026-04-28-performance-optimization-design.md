# Performance Optimization — Design Spec

## Problem

Thumbnail results work well, but loading and response times are slow due to:
- New Supabase client created per request (connection exhaustion)
- Sequential uploads/downloads where parallel I/O is possible
- Missing database indexes on vector columns and sort columns
- No frontend code splitting (896KB single bundle)
- No pagination for photos or messages
- Unnecessary base64 in SSE responses
- Unthrottled photo indexing

## Tier 1 Fixes (Biggest impact)

### 1. Supabase Client Pooling
Replace per-request `create_client()` / `create_async_client()` calls with shared singletons.

- New module `backend/supabase_pool.py` with `get_sync_client()` and `get_async_client()`
- Both return cached singleton instances
- All route files and services import from this module instead of creating clients

### 2. Parallelize Uploads/Downloads
- `thumbnail_nodes.py`: batch uploads with `asyncio.gather()` after generation (lines 242-248, 340-346, 407-413)
- `thumbnail_nodes._fetch_all_assets()`: use shared client + semaphore instead of per-file client creation
- `chat.py` status endpoint: batch downloads with `asyncio.gather()` instead of sequential loop (lines 398-424)
- `chat.py` thumbnail_stream: batch downloads with `asyncio.gather()` (lines 228-241)

### 3. Database Indexes
Add migration file with:
- `IVFFLAT` indexes on `photo_embeddings(embedding)` and `thumbnail_memories(embedding)`
- `created_at` indexes on `messages` and `conversations(updated_at)`

### 4. Frontend Code Splitting
- Use `React.lazy()` + `Suspense` in `App.tsx` for ChatPage, AssetsPage, SettingsPage
- LoginPage stays eager (first route users hit)

## Tier 2 Fixes (Quality & scalability)

### 5. Photo Grid Pagination
- Load thumbnails in pages of 20 in PhotoGrid dialog
- "Load more" button or scroll-based loading

### 6. Message Pagination
- Backend: add `limit` and `before` params to GET `/api/conversations/{id}`
- Frontend: load last 50 messages initially, "load more" for history

### 7. Remove Base64 from SSE
- Stop generating/sending `preview_base64` and `image_base64` in SSE events
- Frontend already uses `preview_url` — base64 is dead weight
- Keep backward-compat field as empty string

### 8. Rate-limit Photo Indexing
- Module-level `asyncio.Semaphore(3)` to cap concurrent indexing tasks
- Applies to both single upload and batch reindex
