# Xiaoxia Architecture Guardrails

> **Status:** Active architectural decision  
> **Decision date:** 2026-09-21  
> **Principle:** **只搬家，不裝潢。**

## 1. Legacy Core

`lobster_discord.py` is the production-stable **Legacy Core** of Xiaoxia.

Do not refactor, split, deduplicate, delete, or reduce this file merely for code cleanliness or to make the file smaller.

Do not add new features to `lobster_discord.py` unless doing so is technically necessary to maintain existing behavior.

Dead-looking, duplicate-looking, or historical code is **not by itself sufficient reason for deletion**. Dynamic references, callbacks, aliases, monkey patches, compatibility paths, and external runtime modules may still depend on it.

## 2. New Development Direction

New functionality should normally be implemented under `xiaoxia/*`, instead of being added to `lobster_discord.py`.

Current and future structure may look like:

```text
xiaoxia/
 ├─ pose/
 ├─ photo/
 ├─ video/
 ├─ wardrobe/
 ├─ calendar/       # create only when Calendar work actually requires it
 ├─ sport/          # create only when Sport work actually requires it
 ├─ autonomy/       # create only when Autonomy work actually requires it
 └─ <new_feature>/
```

**Do NOT create empty modules merely to match this diagram.**

The entries above are an architectural direction, not a migration checklist.

## 3. Production Composition Root

`xiaoxia_runtime_flat.py` is the **single production composition root**.

Conceptually:

```text
xiaoxia_runtime_flat.py
        │
        ├── import lobster_discord as app   # Legacy Core
        │
        ├── install_pose(app)
        ├── install_video(app)
        ├── install_<new_feature>(app)
        └── ...
```

Do **NOT** recreate the historical `xiaoxia_runtime_vxxxxx.py` wrapper-chain architecture.

New modules should be activated from `xiaoxia_runtime_flat.py` only when activation is actually required.

## 4. Existing Lobster Subsystems

Existing working functionality should remain in `lobster_discord.py` unless there is a concrete functional reason to modify that subsystem.

When an existing subsystem requires substantial functional work:

```text
Existing subsystem needs major change
              ↓
    Consider extracting it
              ↓
         xiaoxia/<module>/
              ↓
    Preserve existing behavior
              ↓
Activate through xiaoxia_runtime_flat.py
```

Extraction is **opportunistic**, not a cleanup project.

Do not proactively extract Calendar, Sport, Autonomy, Memory, Diary, Photo, or other existing subsystems solely to make `lobster_discord.py` smaller.

## 5. Strict Refactoring Invariant

Structural work must not silently change existing:

- prompts or prompt wording
- model IDs
- temperature
- resolution, duration, or aspect ratio
- generation/API parameters
- Seedream or H3 behavior
- reference-image roles or ordering
- retry, fallback, or safety-retry behavior
- Discord command semantics or pending-state behavior
- environment-variable names or defaults
- JSON, schema, or stored-data formats
- installer ordering or arguments
- monkey patches
- import side effects

If behavior needs to change, treat it as a **separate functional change**, not as part of structural refactoring.

## 6. Maintenance Rule

The goal is **not** to make `lobster_discord.py` aesthetically clean.

The goal is to stop the Legacy Core from continuing to grow while preserving known-good production behavior.

In short:

> **If it works, leave it alone. New code grows outward under `xiaoxia/*`. Existing code moves only when a real change gives us a reason to move it.**
