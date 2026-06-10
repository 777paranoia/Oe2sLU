# Oe2sLU
Oe2sLU / Open electribe2 Sampler Loop Utility is a GUI designed for batch auto-slicing audio sample loops for the Korg electribe2 Sampler and Hacktribe, as well as a fork of the Oe2sSLE-0.2.2; integrating the orginal Open Editor GUI into the Loop Utility's GUI to manage samples as they're being processed. 

<img width="1441" height="1330" alt="Screenshot 2026-06-10 at 3 06 35 PM" src="https://github.com/user-attachments/assets/8432f280-385b-42c2-998c-81609f5ba9ec" />

Loop Utility also includes other tools like pre-process BPM detection, Demucs stem splitting, direct exporting batches as e2sSample.all bundles, and various parameter controls to dial in the placement and frequency of slicing. 

Additionally, the Oe2sSLE-0.2.2 code bundled into the GUI is patched and updated for Mac compatibility; of which was previously unavailable. 

This is an ongoing development and is currently only available for Mac OSX. 

All suggestions and feedback welcomed. 

Donate and check my music out.

---

## Features

- **Batch auto-slicing**: writes slice tables directly into Korg `esli` metadata
- **Tempo-aware slicing**: BPM is detected first, 16th-note grid derived from it; no slice shorter than one grid step
- **Three slice modes:** `transient` (default), `grid`, `hybrid`
- **Pre-process BPM detection**: check detected tempos before committing
- **Demucs stem splitting**: slice an isolated stem, or split without slicing
- **Auto input conversion**: WAV, AIFF, FLAC, MP3, M4A, AAC, OGG, etc. to 16-bit WAV
- **Direct e2sSample.all export**: whole folder as a single bank, or one WAV per input
- **Chop tool**: split a sliced WAV into one file per slice, with optional click-free fades
- **Embedded Oe2sSLE editor**: manage, rename, and reorder samples as you process

---

## Download & Run

Grab the latest `Oe2sLU.app` from [Releases](../../releases), unzip, drag to Applications.

App is **unsigned**: on first launch macOS will block it. Either right-click -> **Open** -> **Open**, or:
```
xattr -dr com.apple.quarantine /path/to/Oe2sLU.app
```
Nothing else to install: Python, audio engine, ffmpeg, and the stem splitter are all bundled.

---

## Slicing Controls

| Control | Description |
|---|---|
| **Inputs** | Files or folders; drag-and-drop works |
| **Output folder** | Where sliced files/banks are written |
| **Append to filename** | Suffix for output names (e.g. `_chop`) |
| **Mode** | `transient`: onset detection; `grid`: equal divisions; `hybrid`: grid snapped to hits |
| **Steps** | Grid steps/slices, max 64. Blank = auto |
| **BPM** | Blank = auto-detect. Override if tempo octave reads wrong |
| **Beat** | Step resolution: `16`, `32`, `8 Tri`, `16 Tri` |
| **Category** | electribe sample category |
| **Tolerance** | Hybrid snap range as fraction of a step (default ~0.35) |
| **Sensitivity** | Onset sensitivity 1-15 (1 = strongest hits only, 15 = catch everything; default 8) |
| **First slot** | Starting sample number for e2sSample.all export |

**Output formats:** `wav` (default, one per input with Korg slice metadata) or `e2sSample.all` (single bank). Output is capped at the electribe memory limit (26,214,396 bytes).

---

## Tools

- **Detect BPM**: shows BPM/bars/steps per file before slicing
- **Stem split**: Demucs separation into drums/bass/vocals/other; slice selected stems or export without slicing
- **Chop tool**: split a sliced WAV by cue/esli markers, optional fade
- **Editor**: toggle the full Oe2sSLE sample library editor
- **Manual**: in-app reference

---

## Supported Formats

WAV, AIFF/AIF, FLAC, MP3, M4A, AAC, OGG/OPUS, WMA, CAF, W64

---

## BPM / Tempo Octave

Detection is solid in the ~90-160 BPM range. Very slow (~75-85) or fast (~170+ DnB) material can read at half/double tempo: just type the correct BPM to override.

---

## Building from Source

Mac with Python 3 (incl. Tk): double-click `build_mac_app.command`. Sets up a throwaway environment, installs deps, bundles ffmpeg, outputs `dist/Oe2sLU.app`.

To run without building:
```
python3 e2s_autoslice_gui.py
```

---

## Support

PayPal: `777paranoia@gmail.com` / music: [soundcloud.com/speedsick](https://soundcloud.com/speedsick)

---

## License

GPL-3.0-or-later. Continuation of [Oe2sSLE](https://github.com/JonathanTaquet/Oe2sSLE) by Jonathan Taquet (© 2015-2017). New code © 2026 777PARANOIA. See [LICENSE](LICENSE) and [ATTRIBUTION.txt](ATTRIBUTION.txt).
