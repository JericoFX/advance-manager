# Instructions for `rs.py`

This repository contains a single Python utility, `rs.py`, which provides tooling for working with Asura RS managed archives used by Advance Manager. Future changes touching `rs.py` should respect the following context and behavioural notes.

## High-level responsibilities

* Implements both command-line and Tkinter-based GUI interfaces for extracting and repacking `.asr`/`.pc` archives following the RSFL format.
* Handles reading, decompressing, and rewriting the `Asura`, `AsuraZlb`, and `AsuraZbb` container variants while preserving metadata required for lossless repacks.
* Automatically memory-maps large archives (configurable via the `RS_MEMORY_MAP_THRESHOLD` environment variable) to avoid loading multi-hundred-megabyte files entirely into RAM.
* Provides helper routines for texture previewing and exporting, including batch export logic shared between CLI and GUI actions.

## Command-line workflow (`rs.py extract` / `rs.py repack`)

1. **Extraction**
   * Loads the archive bytes directly, memory-mapping files that exceed the configured threshold so large inputs do not need to be copied into RAM.
   * Decompresses the underlying container if necessary, parses RSFL tables, and writes each entry to the chosen output directory.
   * Always writes a `manifest.json` alongside the extracted files that captures offsets, sizes, and metadata necessary to reconstruct the archive.
   * Stores a verbatim copy of the original archive next to the extraction results for convenient repacking.

2. **Repacking**
   * Loads the manifest to determine the original file ordering and chunk metadata.
   * Reuses unchanged payloads directly from the manifest data and appends resized entries to the end of the file, updating offsets while keeping RSCF-controlled entries at fixed sizes.
   * Writes the new archive to the requested path without mutating the input extraction directory.

## GUI workflow (`python rs.py --gui`)

* Launches a Tkinter application for browsing and exporting textures contained within an archive.
* Uses Pillow (if available) to decode supported image formats for preview.
* Keeps track of the most recently activated list item so the preview panel always reflects the last clicked entry, even when multiple selections are active.
* Provides per-item export and "Export All" actions that funnel through shared export helpers to keep behaviour consistent with the CLI.

## Implementation tips

* Avoid try/except wrappers around imports beyond the existing optional dependency checks for Tkinter and Pillow.
* Maintain manifest compatibility: new metadata fields should be strictly additive and backwards compatible.
* Any GUI changes should fall back gracefully when Pillow or ImageTk are unavailable; the script must still function in CLI-only environments.
* Use the supplied helper functions for normalising paths and manipulating RSFL entries to keep checksum and offset calculations consistent.

