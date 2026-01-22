#!/usr/bin/env python3
"""
Generate placeholder engine and shift sounds for testing.

This script creates synthetic WAV files that simulate engine sounds at different
RPM ranges and gear shift sounds. These are placeholders - real engine sounds
can be substituted later.

Usage:
  python generate_sounds.py [output_dir]

If output_dir is not specified, sounds are saved to selfdrive/assets/sounds/engine/
"""

import os
import sys
import wave
import struct
import math

# Audio parameters matching config.py
SAMPLE_RATE = 48000
BITS_PER_SAMPLE = 16
NUM_CHANNELS = 1

# Engine sound durations (in seconds) - these will loop
ENGINE_SOUND_DURATION = 3.0

# Shift sound duration
SHIFT_SOUND_DURATION = 0.4


def generate_sine_wave(frequency: float, duration: float, amplitude: float = 0.5) -> list[int]:
    """Generate a sine wave at the given frequency."""
    num_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        value = amplitude * math.sin(2 * math.pi * frequency * t)
        # Convert to 16-bit integer
        samples.append(int(value * 32767))
    return samples


def generate_engine_sound(base_frequency: float, duration: float, amplitude: float = 0.4) -> list[int]:
    """
    Generate a multi-harmonic engine-like sound.

    Engine sounds consist of a fundamental frequency plus several harmonics
    with decreasing amplitude, plus some low-frequency rumble.
    """
    num_samples = int(SAMPLE_RATE * duration)
    samples = [0.0] * num_samples

    # Harmonic structure for engine sound
    # Fundamental + 2nd, 3rd, 4th harmonics with decreasing amplitude
    harmonics = [
        (1.0, 1.0),      # Fundamental
        (2.0, 0.5),      # 2nd harmonic
        (3.0, 0.25),     # 3rd harmonic
        (4.0, 0.15),     # 4th harmonic
        (0.5, 0.3),      # Sub-harmonic (rumble)
    ]

    for harmonic_mult, harmonic_amp in harmonics:
        freq = base_frequency * harmonic_mult
        for i in range(num_samples):
            t = i / SAMPLE_RATE
            # Add slight frequency modulation for more organic sound
            freq_mod = 1.0 + 0.02 * math.sin(2 * math.pi * 5 * t)
            value = harmonic_amp * math.sin(2 * math.pi * freq * freq_mod * t)
            samples[i] += value

    # Normalize and apply amplitude
    max_val = max(abs(s) for s in samples) or 1.0
    samples = [int((s / max_val) * amplitude * 32767) for s in samples]

    # Apply fade in/out for seamless looping
    fade_samples = int(SAMPLE_RATE * 0.05)  # 50ms fade
    for i in range(fade_samples):
        fade = i / fade_samples
        samples[i] = int(samples[i] * fade)
        samples[-(i + 1)] = int(samples[-(i + 1)] * fade)

    return samples


def generate_shift_sound(start_freq: float, end_freq: float, duration: float, amplitude: float = 0.6) -> list[int]:
    """
    Generate a frequency sweep (chirp) for shift sounds.

    Upshift: rising frequency
    Downshift: falling frequency
    """
    num_samples = int(SAMPLE_RATE * duration)
    samples = []

    for i in range(num_samples):
        t = i / SAMPLE_RATE
        progress = t / duration

        # Exponential frequency sweep sounds more natural
        freq = start_freq * math.pow(end_freq / start_freq, progress)

        # Apply envelope: quick attack, sustained, quick release
        if progress < 0.1:
            envelope = progress / 0.1
        elif progress > 0.8:
            envelope = (1.0 - progress) / 0.2
        else:
            envelope = 1.0

        value = amplitude * envelope * math.sin(2 * math.pi * freq * t)
        samples.append(int(value * 32767))

    return samples


def write_wav_file(filename: str, samples: list[int]) -> None:
    """Write samples to a WAV file."""
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(NUM_CHANNELS)
        wav_file.setsampwidth(BITS_PER_SAMPLE // 8)
        wav_file.setframerate(SAMPLE_RATE)

        # Pack samples as signed 16-bit integers
        packed_samples = struct.pack('<' + 'h' * len(samples), *samples)
        wav_file.writeframes(packed_samples)


def main():
    # Determine output directory
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        # Default to selfdrive/assets/sounds/engine/
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, "..", "..", "selfdrive", "assets", "sounds", "engine")

    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    print(f"Generating placeholder engine sounds in: {output_dir}")

    # Engine sounds at different base frequencies
    engine_sounds = [
        ("engine_idle.wav", 80),    # Idle: low rumble
        ("engine_low.wav", 120),    # Low RPM
        ("engine_mid.wav", 180),    # Mid RPM
        ("engine_high.wav", 250),   # High RPM
    ]

    for filename, base_freq in engine_sounds:
        filepath = os.path.join(output_dir, filename)
        print(f"  Generating {filename} (base freq: {base_freq}Hz)...")
        samples = generate_engine_sound(base_freq, ENGINE_SOUND_DURATION)
        write_wav_file(filepath, samples)

    # Shift sounds
    shift_sounds = [
        ("shift_up.wav", 200, 400),    # Rising sweep
        ("shift_down.wav", 400, 200),  # Falling sweep
    ]

    for filename, start_freq, end_freq in shift_sounds:
        filepath = os.path.join(output_dir, filename)
        print(f"  Generating {filename} ({start_freq}Hz -> {end_freq}Hz)...")
        samples = generate_shift_sound(start_freq, end_freq, SHIFT_SOUND_DURATION)
        write_wav_file(filepath, samples)

    print("Done! Generated placeholder sounds:")
    for f in os.listdir(output_dir):
        if f.endswith('.wav'):
            filepath = os.path.join(output_dir, f)
            size = os.path.getsize(filepath)
            print(f"  {f}: {size} bytes")


if __name__ == "__main__":
    main()
