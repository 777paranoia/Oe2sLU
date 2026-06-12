Drop font files here to bundle them with the app — no system install needed.

Any .ttf / .otf / .otb in this folder is loaded automatically at startup
(via tkextrafont) and made available to the GUI. If a loaded family's name
contains "gohu", it is selected as the GUI font; otherwise the app falls back
to Menlo / Helvetica.

To use Gohu (https://font.gohu.org/, WTFPL-licensed, free to redistribute):
  1. Download a Gohu build that includes a .ttf (or .otf/.otb).
  2. Copy that file into this folder.
  3. Relaunch the app.

These files are bundled into the standalone .app by e2s_autoslice_gui.spec.
