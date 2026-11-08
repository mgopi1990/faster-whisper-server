#!/usr/bin/env python3

import argparse
import sys
import wave
from datetime import datetime
from pathlib import Path

import requests
import sounddevice as sd


# Start the server with:
#   cd /home/gopi/gopi/faster-whisper-text
#   . .venv/bin/activate
#   faster-whisper-server --config config.yaml --host 127.0.0.1 --port 8000
#

DEFAULT_URL = "http://127.0.0.1:8000/v1/audio/transcriptions"
DEFAULT_FILE_FORMAT = "%Y%m%d-%H%M%S"
MAX_RECORDING_TIME_SECONDS = 5 * 60
RECORDING_PROGRESS_INTERVAL_SECONDS = 5
AUDIO_CONTENT_TYPES = {".wav": "audio/wav", ".mp3": "audio/mpeg"}

OUTPUT_DIR = Path("output")

OUTPUT_DIR.mkdir(exist_ok=True)


def _print_recording_progress(elapsed: float, last_tick: int):
    current_tick = int(elapsed // RECORDING_PROGRESS_INTERVAL_SECONDS)
    ticks_per_minute = 60 // RECORDING_PROGRESS_INTERVAL_SECONDS
    while last_tick < current_tick:
        last_tick += 1
        print("#", end="", flush=True)
        if last_tick % ticks_per_minute == 0:
            print()
            if last_tick * RECORDING_PROGRESS_INTERVAL_SECONDS < MAX_RECORDING_TIME_SECONDS:
                print(f"{last_tick // ticks_per_minute + 1:02d} ", end="", flush=True)
    return last_tick


def _record_wav(output_path: Path, samplerate: int = 16000, channels: int = 1, duration: float | None = None):
    frames = []
    stream = sd.InputStream(samplerate=samplerate, channels=channels, dtype="int16")
    stream.start()
    started = datetime.now()
    last_tick = 0
    total_seconds = 0.0
    print(f"input file: {output_path}")
    try:
        if duration is not None:
            total = 0.0
            print("01 ", end="", flush=True)
            while total < duration:
                block, overflow = stream.read(4096)
                frames.append(block.copy())
                total += len(block) / samplerate / channels
                total_seconds = total
                elapsed = (datetime.now() - started).total_seconds()
                last_tick = _print_recording_progress(elapsed, last_tick)
                if elapsed >= MAX_RECORDING_TIME_SECONDS:
                    print(f"\nMaximum recording time reached ({MAX_RECORDING_TIME_SECONDS // 60} minutes). Stopping automatically.")
                    break
        else:
            print(f"recording continuously: {output_path}. Press Ctrl+C to stop, or it will stop after {MAX_RECORDING_TIME_SECONDS // 60} minutes.")
            print("01 ", end="", flush=True)
            while True:
                block, overflow = stream.read(4096)
                frames.append(block.copy())
                total_seconds += len(block) / samplerate / channels
                elapsed = (datetime.now() - started).total_seconds()
                last_tick = _print_recording_progress(elapsed, last_tick)
                if elapsed >= MAX_RECORDING_TIME_SECONDS:
                    print(f"\nMaximum recording time reached ({MAX_RECORDING_TIME_SECONDS // 60} minutes). Stopping automatically.")
                    break
    except KeyboardInterrupt:
        print("\nStopping recording.")
    finally:
        stream.stop()
        stream.close()
        print()

    if not frames:
        raise RuntimeError("No audio captured before Ctrl+C.")

    audio = b"".join(frame.tobytes() for frame in frames)
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(samplerate)
        wav_file.writeframes(audio)

    return total_seconds


def _audio_file_stats(path: Path):
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        duration = frames / float(rate)
    size = path.stat().st_size
    return size, duration


def record_push_to_talk(output_path: Path, samplerate: int = 16000, channels: int = 1, duration: float | None = None):
    if output_path.suffix.lower() != ".wav":
        raise ValueError("Recording output must use the .wav extension.")

    recorded_seconds = _record_wav(output_path, samplerate=samplerate, channels=channels, duration=duration)
    size_bytes, audio_seconds = _audio_file_stats(output_path)
    print(f"stopped after: {recorded_seconds:.2f}s | saved audio: {output_path.name} | size: {size_bytes} bytes | duration: {audio_seconds:.2f}s")
    return output_path


def transcribe_audio(file_path: Path, url: str = DEFAULT_URL, model_name: str = "base"):
    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")
    try:
        content_type = AUDIO_CONTENT_TYPES[file_path.suffix.lower()]
    except KeyError:
        supported_types = ", ".join(sorted(AUDIO_CONTENT_TYPES))
        raise ValueError(f"Unsupported audio file extension {file_path.suffix!r}; expected one of: {supported_types}") from None

    print("sending to server...")
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, content_type)}
        data = {"model_name": model_name, "response_format": "json"}
        response = requests.post(url, files=files, data=data, timeout=300)

    payload = response.json() if response.headers.get("Content-Type", "").startswith("application/json") else {"text": response.text}
    text = payload.get("text", "")
    base_name = file_path.stem
    text_out = OUTPUT_DIR / f"{base_name}.txt"
    text_out.write_text(text, encoding="utf-8")
    print(f"saved transcript: {text_out}")
    print("Transcript:")
    print(text if text else "[no speech detected]")
    return text


def main():
    parser = argparse.ArgumentParser(description="Record microphone input until Ctrl+C, then upload to the Faster Whisper server.")
    parser.add_argument("--output", default=None, help="WAV audio output path, default: output/YYYYMMDD-HHMMSS.wav")
    parser.add_argument("--url", default=DEFAULT_URL, help="Transcription API URL")
    parser.add_argument("--model", default="base", help="Model name as configured in the server")
    parser.add_argument("--samplerate", type=int, default=16000, help="Audio sample rate")
    parser.add_argument("--duration", type=float, default=None, help="Optional fixed recording duration in seconds; otherwise record until Ctrl+C")
    args = parser.parse_args()

    timestamp = datetime.now().strftime(DEFAULT_FILE_FORMAT)
    if args.output is None:
        audio_file = OUTPUT_DIR / f"{timestamp}.wav"
    else:
        audio_file = Path(args.output)
        audio_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"Recording until Ctrl+C. Output: {audio_file}")
    try:
        record_push_to_talk(audio_file, samplerate=args.samplerate, duration=args.duration)
        transcribe_audio(audio_file, url=args.url, model_name=args.model)
    except KeyboardInterrupt:
        print("\nInterrupted. Upload cancelled.")
    except Exception as exc:
        print(f"Error: {exc}")
        raise


if __name__ == "__main__":
    main()
