# LT Android phase 4-5 decisions

## Phase 5 editor integration

- LT Maker invokes the existing Phase-4 PowerShell entry point through
  `QProcess`; the Android builder remains separate from the desktop
  PyInstaller `LTProjectBuilder`.
- The editor always saves with `as_chunks=False`, then re-reads the serialized
  `metadata.json` before build. This prevents a stale in-memory metadata object
  from bypassing the fatal-error gate.
- Android configuration lives at `.ltproj/build/android.json` and contains no
  keystore or password fields. The project backup/replacement save path
  explicitly preserves this folder.
- Build output is streamed to the dialog and to an editor-side log. On success,
  the verified immutable artifact directory and its published `build.log`
  become the authoritative result paths.
- Package ID is editable but changing a previously saved value requires an
  explicit warning acknowledgement because it breaks Android upgrade/save
  continuity.
- Phase 5 exposes Debug and native-optimized Release modes. Release output is
  signed with the existing development certificate and is never presented as a
  production or Play Store artifact.

Phase 4 productizes the runtime proven in phases 1-3 into a repeatable,
auditable command-line APK pipeline. It deliberately does not add an LT Maker
menu or release-signing UI; those are phase 5.

## Reuse instead of a second Android tree

The existing `utilities/build_tools/android_runtime/` directory already owns
the working SDL2 entrypoint, custom pygame-ce recipe, controls, and device
diagnostics. Phase 4 extends that directory rather than creating a competing
`android/` implementation with duplicated native pins and fixes.

## Build identity and toolchain

- `toolchain_manifest.json` is authoritative for runtime/tool versions.
- Default APK identity is `org.lextalionis.ltandroidruntime`, version `0.4.0`,
  numeric version `1026400`.
- The CLI accepts identity/icon overrides so phase 5 can reuse the same
  pipeline without modifying its internals.
- ARM64 Debug and development-signed native Release APKs are allowed. Production
  release keystores, secrets, AAB, and Play delivery are out of scope.

## Source and snapshot safety

- Preflight and staging are read-only with respect to the `.ltproj`.
- The project is hashed before copy and the filtered staging copy is hashed
  again. A mismatch aborts rather than producing a mixed snapshot.
- `.pyc`, caches, tests, backup files, and editor temporaries are excluded.
- python-for-android packages private data as USTAR. Overlong, unlisted
  portrait-import leftovers may be excluded from staging and are recorded in
  the runtime manifest; an overlong catalogued/runtime path remains fatal.
- Staging is assembled in a temporary sibling and renamed into place only when
  complete.
- Buildozer runs only in a persistent native-key Linux cache. Source data may
  be read through `/mnt`, but native build output is never placed there.
- A per-native-key/package `flock` serializes access to each Buildozer
  workspace. The workspace uses compact prefixes of the full native key and
  package-ID hash under a short `n/` path, preventing generated host-Python
  `pip` shebangs from exceeding Linux's 255-byte limit. Project/version edits
  retain compiled p4a recipes while staging and APK packaging remain fresh for
  every distinct input.
- A cache is marked verified only after APK verification passes. A failed p4a
  build marks that workspace dirty so the next build discards only its native
  intermediates rather than publishing from uncertain state.

The CLI cannot save in-memory editor state. It requires an already-saved
project and rejects persisted fatal-error metadata. Phase 5 must call the
editor save operation before launching this same builder.

## Preflight policy

Fatal checks cover:

- invalid package/app/version/ABI/mode/icon;
- stale serialization version or `has_fatal_errors`;
- case-insensitive path collisions;
- missing or wrong-case files in core resource catalogs;
- unsupported/broken project music and SFX;
- custom-component syntax and imports of desktop-only UI/build modules;
- insufficient project-side snapshot space or Linux build-cache space.

The report includes source digest, file count, byte count, audio/custom-Python
counts, free space, effective config, warnings, and errors. It is packaged in
the APK and copied into the final artifact batch.

## APK verification policy

A build is not publishable until:

- `aapt` reports the requested package ID and version name/code;
- minimum API and target API match the toolchain manifest;
- the only native ABI directory is `arm64-v8a`;
- `apksigner` verifies APK Signature Scheme v2;
- `assets/private.tar` contains passing preflight and phase-4 runtime manifests;
- the packaged build config matches the requested config.

## Artifact publication

Every successful build receives an immutable directory named with project,
version, UTC timestamp, and an APK hash prefix. APK, SHA-256, effective config,
preflight, verification, manifest, and build log are moved into place as one
directory. Existing immutable batches are never deleted. Only the documented
latest APK/SHA aliases are atomically replaced after verification succeeds.

## Phase 4 exit gate

- Focused phase-4 pipeline tests pass.
- Default-project preflight and staging validation pass.
- A clean Linux-cache build produces version 0.4.0.
- The emitted `apk-verification.json` passes package, version, API, ABI,
  signature, and embedded-manifest checks.
- The final immutable artifact batch contains all seven required deliverables.
- Source project digest is unchanged across preflight and staging.

Physical-device gameplay is still reported separately: no build-only check is
presented as proof of touch, audio, lifecycle, FPS, save persistence, or
Golden Knight compatibility.
