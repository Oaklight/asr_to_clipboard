#!/usr/bin/env python3

import argparse
import os
import sys
import tempfile
import signal
import time

import numpy as np
from openai import OpenAI  # Updated import for OpenAI client
import pyperclip
import sounddevice as sd
import yaml
from scipy.io.wavfile import write


def read_config(config_file):
    try:
        with open(config_file, "r") as file:
            config = yaml.safe_load(file)
            return config
    except Exception as e:
        print(f"Could not read configuration file {config_file}: {e}")
        sys.exit(1)


def record_audio(fs):
    print("Recording... Press Ctrl+C to stop.")
    try:
        # Initialize an empty list to store audio chunks
        audio_chunks = []

        # Start recording in a loop until stop_recording is True
        with sd.InputStream(
            samplerate=fs,
            channels=1,
            callback=lambda indata, frames, time, status: audio_chunks.append(
                indata.copy()
            ),
        ):
            while not stop_recording:
                sd.sleep(100)  # Sleep for 100ms to avoid busy-waiting

        # Concatenate all recorded chunks into a single numpy array
        recording = np.concatenate(audio_chunks)
        print("Recording stopped.")
        return recording
    except Exception as e:
        print(f"An error occurred while recording audio: {e}")
        sys.exit(1)


def save_audio(recording, fs, filename):
    # Normalize and convert to 16-bit data
    recording = recording / np.max(np.abs(recording))
    recording = np.int16(recording * 32767)
    write(filename, fs, recording)


def transcribe_audio(filename, api_key, api_base_url, model_name):
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key, base_url=api_base_url)

        # Open the audio file
        with open(filename, "rb") as audio_file:
            print("Transcribing audio...")
            transcript = client.audio.transcriptions.create(
                model=model_name,
                file=audio_file,
            )
            return transcript
    except Exception as e:
        print(f"An error occurred during transcription: {e}")
        sys.exit(1)


def signal_handler(sig, frame):
    global stop_recording
    stop_recording = True
    print("\nReceived interrupt signal. Press Ctrl+C again to exit.")
    signal.signal(signal.SIGINT, signal_handler_exit)


def signal_handler_exit(sig, frame):
    print("\nExiting...")
    sys.exit(0)


def main():
    global stop_recording
    stop_recording = False

    parser = argparse.ArgumentParser(
        description="Real-time speech recognizer that copies transcribed text to the clipboard."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to the configuration file. Default is 'config.yaml'.",
    )

    args = parser.parse_args()

    # Read configuration
    config = read_config(args.config)
    asr_config = config.get("asr_model", {})
    api_key = asr_config.get("api_key", os.environ.get("OPENAI_API_KEY"))
    api_base_url = asr_config.get("api_base_url", "https://api.openai.com/v1")
    model_name = asr_config.get("model_name", "whisper-1")

    # Check API key
    if not api_key:
        print("Error: API key not found in the configuration file.")
        sys.exit(1)

    fs = 44100  # Sample rate

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)

    print("Press Ctrl+C to stop recording and transcribe the audio.")
    print("Press Ctrl+C again to exit the program.")

    while not stop_recording:
        # Record audio continuously until stop signal is issued
        recording = record_audio(fs)

        # Save to a temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmpfile:
            filename = tmpfile.name
            save_audio(recording, fs, filename)

            # Transcribe audio
            transcript = transcribe_audio(filename, api_key, api_base_url, model_name)

        # Copy to clipboard
        text = transcript.text

        pyperclip.copy(text)
        print("\nTranscribed Text:")
        print("-----------------")
        print(text)
        print("\nThe transcribed text has been copied to the clipboard.")

        # Wait for a short period before recording again
        time.sleep(1)


if __name__ == "__main__":
    main()
