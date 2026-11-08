# Faster Whisper Server Recorder

A command-line microphone recorder that sends audio to a local
[faster-whisper-server](https://github.com/andyjjrt/faster-whisper-server)
instance and saves the transcription as a text file.

## Features

- Records from the system's default microphone.
- Stops recording with `Ctrl+C`, after a specified duration, or automatically
  after five minutes.
- Shows recording progress with one `#` every five seconds and a numbered line
  for each minute.
- Saves recordings and transcripts together under `output/` by default.
- Lets you configure the server URL, model, sample rate, duration, and output
  path with command-line options.

## Requirements

- Python 3.10 or later.
- A working microphone and audio input device.
- PortAudio, required by `sounddevice` (on Debian/Ubuntu, install
  `libportaudio2`).
- A running faster-whisper-server instance. GPU support is optional; the
  supplied configuration uses CUDA.

## Installation

From the project directory, create and activate a virtual environment, then
install the Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Debian/Ubuntu, install the system audio and conversion utilities with:

```bash
sudo apt update
sudo apt install libportaudio2
```

The first server startup may need internet access to download the configured
Whisper model.

## Configuration

The server reads `config.yaml`. The included configuration selects the
`Systran/faster-whisper-base` model and sets the device to CUDA with `float16`
compute.

If CUDA is unavailable, edit the model's `config` in `config.yaml` to use CPU,
for example:

```yaml
config:
  model: base
  device: cpu
  compute_type: int8
```

Use the compute type supported by your hardware and faster-whisper/CTranslate2
installation.

## Usage

Start the server in one terminal:

```bash
source .venv/bin/activate
faster-whisper-server --config config.yaml --host 127.0.0.1 --port 8000
```

In another terminal, activate the same environment and start recording:

```bash
source .venv/bin/activate
python faster-whisper-text.py
```

The script records until you press `Ctrl+C`, then uploads the audio for
transcription. It also stops automatically after five minutes. By default,
recordings and transcripts are saved under `output/`. After transcription, the
first 32 characters of the recognized text are added to the transcript filename
only, with spaces replaced by underscores. For example, the audio remains
`output/20261109-123456.wav`, and its transcript is saved as
`output/20261109-123456_turn_left_at_the.txt`.

Recordings are written directly as WAV, so FFmpeg is not needed. If
`transcribe_audio` is used with an existing MP3 file, the request uses the
`audio/mpeg` content type; WAV uploads use `audio/wav`.

### Command-line options

```text
--output PATH       WAV audio output path (default: output/<timestamp>.wav)
--url URL           Transcription API URL (default:
                    http://127.0.0.1:8000/v1/audio/transcriptions)
--model NAME        Model name configured on the server (default: base)
--samplerate HZ     Recording sample rate (default: 16000)
--duration SECONDS  Stop after this many seconds instead of waiting for Ctrl+C
```

Examples:

```bash
# Record for 30 seconds
python faster-whisper-text.py --duration 30

# Use a custom output file and server URL
python faster-whisper-text.py \
  --output output/meeting.wav \
  --url http://127.0.0.1:8000/v1/audio/transcriptions
```

The requested duration cannot exceed the five-minute recording limit. The
`--output` option changes the WAV recording path; it must end in `.wav`.
The transcript is saved beside the recording with the recognized-text suffix
in its filename; the audio filename is unchanged.

## Output

- `output/`: WAV recordings and UTF-8 transcription files.

The directory is created automatically when the script starts.

## Troubleshooting

- **Cannot connect to the transcription server:** Confirm the server is
  running and that `--url` matches its host and port.
- **Microphone or PortAudio errors:** Check that an input device is available
  and that PortAudio is installed.
- **Large recordings:** WAV files are uncompressed. A five-minute mono
  16 kHz, 16-bit recording is approximately 9.6 MB.
- **PyAV `metadata_errors` error:** The installed `av` package must remain
  below version 19; `requirements.txt` pins the compatible version.
- **CUDA or compute-type errors:** Adjust `device` and `compute_type` in
  `config.yaml` to match the server's hardware.

## Project files

```text
.
├── config.yaml
├── faster-whisper-text.py
├── requirements.txt
└── output/
```
