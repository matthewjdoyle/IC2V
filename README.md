# IC2V

Image Collection 2 Video converts collections of PNG images into MP4, WebM,
MOV, or animated GIF files using FFmpeg. It supports single collections and
batch conversion on Windows, macOS, and Linux.

## Installation

Requires Python 3.11 or later and an FFmpeg executable.

```sh
pip install .
ic2v --help
```

Install FFmpeg separately and make sure `ffmpeg -version` works:

- Windows: install an FFmpeg build and add its `bin` directory to your user PATH.
- macOS: if you use Homebrew, run `brew install ffmpeg`.
- Linux: install your distribution's `ffmpeg` package, for example `sudo apt install ffmpeg` on Debian/Ubuntu.

You can also supply `--ffmpeg "path/to/ffmpeg"` to either command. The build
must include `libx264` for MP4/MOV, `libvpx-vp9` for WebM, or `gif` for GIF.
IC2V checks the selected encoder before processing. It does not download FFmpeg.

## Convert a collection

```sh
ic2v convert "path/to/images" --output "movie.mp4"
ic2v convert "path/to/images" --output "movie.webm" --fps 12
ic2v convert "path/to/images" --output "movie.mov" --fps 24 --size 1920x1080
ic2v convert "path/to/images" --output "movie.gif" --fps 6 --background white
```

The output extension selects the format. Only PNG files directly inside the
input directory are included; `.PNG` also works. Filenames sort naturally, so
`frame2.png` comes before `frame10.png`. Equal natural keys use the original
filename as a deterministic tie-breaker. Each image contributes one frame.

Without `--fps`, the CLI asks you to choose 6, 12, 24, 30, or a custom positive
decimal FPS. The previous selection is the default, but you must confirm it
each run. A previous custom value is prefilled after selecting Custom. On
first use, 12 is highlighted. An explicit `--fps` skips the prompt and saves
that rate too. Scripts and other noninteractive runs must supply `--fps`.

Preferences are stored per user in `ic2v/preferences.json` under the platform's
configuration directory (typically `%LOCALAPPDATA%` on Windows,
`~/Library/Application Support` on macOS, and `~/.config` on Linux). Missing
preferences use the initial default; damaged preferences cause a warning.
Saving preferences is best effort and never prevents conversion.

## Batch conversion

```sh
ic2v batch "path/to/collections" --output-dir "videos" --format mp4
ic2v batch "path/to/collections" --output-dir "gifs" --format gif --fps 12
```

Each immediate child folder becomes one output named after that folder.
For example, `collections/scene1/*.png` becomes `videos/scene1.mp4`.
Batch conversion does not recurse and does not include PNGs directly in the
root. The default format is MP4. FPS is selected once for the whole batch;
the default canvas is calculated separately for each collection.

Folders without PNGs are skipped. A failed collection is reported and the
remaining folders continue. The final summary counts successes, skips, and
failures. Any failed collection, or no eligible collections, yields a nonzero
exit code. Successful batches return zero.

## Dimensions, formats, and existing files

By default, the canvas uses the maximum image width and maximum image height
in the collection. `--size WIDTHxHEIGHT` sets it explicitly. Images scale to
fit while preserving aspect ratio, and are centered with padding. Mixed source
dimensions produce a warning that padding may appear. An aspect-ratio mismatch
with an explicit canvas also produces a warning.

Padding defaults to black. Use `--background white` or a quoted hex color such
as `--background "#e0e0e0"` to change it. Transparent PNG pixels are composited
onto the same opaque background. Video dimensions are rounded up to even
numbers when necessary; the actual canvas is reported.

| Extension | Encoding preset |
| --- | --- |
| `.mp4` | H.264, CRF 18, medium preset, YUV 4:2:0, fast start |
| `.mov` | H.264, CRF 18, medium preset, YUV 4:2:0, fast start |
| `.webm` | VP9, CRF 30, unconstrained bitrate, YUV 4:2:0 |
| `.gif` | Generated palette, dithering, infinite loop |

GIF delays have centisecond precision, and viewers may impose a minimum delay,
so playback timing can differ from the requested FPS. No audio, transitions,
per-image hold times, or arbitrary FFmpeg arguments are included.

Existing files are preserved. A requested `movie.mp4` becomes `movie-2.mp4`,
then `movie-3.mp4`, using the first available suffix. This also applies to
batch outputs. IC2V validates images, prepares temporary normalized PNGs,
encodes to a temporary file, then publishes to an available name. Failures and
normal cancellation clean up temporary files. The encoded file is staged directly
in the output directory so published videos inherit its access permissions,
including on Windows. A forced process kill or power loss can leave `.ic2v-*`
temporary files or directories behind.

Temporary frames live beside the output and require disk space proportional
to the normalized collection. Image processing holds one frame at a time;
FFmpeg's own memory use depends on the encoder and GIF palette processing.
Errors include the affected image path or FFmpeg's diagnostic output.

## Development

```sh
python -m venv .venv
# Activate .venv using your shell's activation command.
python -m pip install -e ".[test]"
python -m pytest -q
```

Integration tests require FFmpeg on PATH or an `IC2V_TEST_FFMPEG` environment
variable pointing to the executable. They are skipped if neither is present.
CI runs unit and real encoding tests on Windows, macOS, and Linux with Python
3.11 and the latest stable Python. CI uses `imageio-ffmpeg` only to provision a
test executable; it is not an application dependency.
