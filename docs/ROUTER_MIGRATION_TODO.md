# Router Migration Guide for Multi-Tenant Support

## Overview

All routers need to be updated to use the `get_rag_instance` dependency function instead of a global `rag` instance.

## Changes Required

### 1. Update Function Signatures

**Before:**
```python
def create_xxx_routes(rag: LightRAG, api_key: Optional[str] = None):
```

**After:**
```python
def create_xxx_routes(
    api_key: Optional[str] = None,
    get_rag_instance: Optional[Callable[[Request], LightRAG]] = None,
):
```

### 2. Update Imports

Add `Request` and `Callable` to imports:

```python
from typing import Any, Callable, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from lightrag import LightRAG
```

### 3. Update Route Handlers

For each route handler that uses `rag`:

**Before:**
```python
@router.post("/endpoint")
async def my_endpoint(request: SomeRequest):
    result = await rag.some_method(...)
```

**After:**
```python
@router.post("/endpoint")
async def my_endpoint(http_request: Request, request: SomeRequest):
    # Get the LightRAG instance for this tenant/project
    rag = await get_rag_instance(http_request)
    
    result = await rag.some_method(...)
```

### 4. Parameter Name Conflict

When the route already has a `request` parameter (for Pydantic models), rename the FastAPI Request to `http_request`:

```python
async def my_endpoint(http_request: Request, request: MyRequestModel):
    rag = await get_rag_instance(http_request)
```

When there's no Pydantic model, you can keep `request`:

```python
async def my_endpoint(request: Request):
    rag = await get_rag_instance(request)
```

## Files to Update

### ✅ Partially Done
- `lightrag/api/routers/query_routes.py`
  - ✅ Updated function signature
  - ✅ Updated imports
  - ✅ Updated `query_text` handler
  - ⏳ Need to update: `query_text_stream`, `query_data`

### ⏳ TODO
- `lightrag/api/routers/document_routes.py`
  - Functions using `rag`: scan_for_new_documents, upload_to_input_dir, insert_text, delete_documents, list_documents, check_document_status, get_document_chunks, etc.
  - Estimated handlers to update: ~15

- `lightrag/api/routers/graph_routes.py`
  - Functions using `rag`: export_graph_data, search_entities, search_relationships, get_entity_details, get_relationship_details, etc.
  - Estimated handlers to update: ~8

- `lightrag/api/routers/ollama_api.py`
  - This is a class-based router using `self.rag`
  - Different pattern: store `get_rag_instance` in `self.get_rag_func`
  - Update all methods to call `rag = await self.get_rag_func(request)`

## Step-by-Step Process

For each router file:

1. Update function signature to accept `get_rag_instance` parameter
2. Add required imports (`Request`, `Callable`, `LightRAG`)
3. Find all route handlers (search for `async def` inside the function)
4. For each handler:
   - Add `http_request: Request` (or `request: Request` if no conflict) as first parameter
   - Add `rag = await get_rag_instance(http_request)` at the start
   - Keep all other code unchanged

## Testing Strategy

After updating each router:

1. Start the server: `uvicorn lightrag.api.lightrag_server:app --reload`
2. Test endpoints with different tenant/project headers:
   ```bash
   curl -X POST http://localhost:9621/endpoint \
     -H "X-Tenant-ID: tenant1" \
     -H "X-Project-ID: project1" \
     ...
   ```
3. Verify data isolation:
   - Insert data for tenant1/project1
   - Query from tenant1/project2 → should not see the data
   - Query from tenant2/project1 → should not see the data

## Example: Complete Handler Update

### Before
```python
@router.post("/documents/upload")
async def upload_to_input_dir(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    track_id = generate_track_id("upload")
    background_tasks.add_task(process_file, rag, file, track_id)
    return {"status": "success", "track_id": track_id}
```

### After
```python
@router.post("/documents/upload")
async def upload_to_input_dir(
    http_request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    # Get the LightRAG instance for this tenant/project
    rag = await get_rag_instance(http_request)
    
    track_id = generate_track_id("upload")
    background_tasks.add_task(process_file, rag, file, track_id)
    return {"status": "success", "track_id": track_id}
```

## Common Pitfalls

1. **Forgetting to await**: `rag = get_rag_instance(request)` ❌ → `rag = await get_rag_instance(request)` ✅

2. **Parameter order**: FastAPI requires `Request` before other dependencies:
   ```python
   # Wrong order
   async def handler(file: UploadFile, request: Request): ...
   
   # Correct order
   async def handler(request: Request, file: UploadFile): ...
   ```

3. **Background tasks**: When passing `rag` to background tasks, make sure it's the instance, not the function:
   ```python
   # Get instance first
   rag = await get_rag_instance(request)
   # Then pass to background task
   background_tasks.add_task(process, rag, ...)
   ```

## Progress Tracking

- [x] Create instance_manager.py
- [x] Update lightrag_server.py to use instance manager
- [x] Update env.example with new config
- [x] Create documentation
- [x] Update query_routes.py (partial - 1/3 handlers)
- [ ] Complete query_routes.py (2 more handlers)
- [ ] Update document_routes.py (~15 handlers)
- [ ] Update graph_routes.py (~8 handlers)
- [ ] Update ollama_api.py (class-based, different pattern)
- [ ] Test complete multi-tenant flow
- [ ] Update test suite for multi-tenancy
