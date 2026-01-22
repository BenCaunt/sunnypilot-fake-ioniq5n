"""
Audio engine for the engine sound simulator.

This module handles audio playback with pitch shifting based on vehicle speed.
It follows the pattern established in selfdrive/ui/soundd.py using sounddevice
with callback-based streaming.
"""

import os
import wave
import numpy as np
from typing import Optional

from openpilot.common.basedir import BASEDIR
from openpilot.common.swaglog import cloudlog

from sunnypilot.enginesoundd.config import (
    SAMPLE_RATE,
    SAMPLE_BUFFER,
    DEFAULT_VOLUME,
    SPEED_THRESHOLDS_MS,
    PITCH_RANGES,
    TIER_SOUND_FILES,
    SHIFT_UP_SOUND,
    SHIFT_DOWN_SOUND,
    CROSSFADE_DURATION,
)

SOUNDS_DIR = os.path.join(BASEDIR, "selfdrive", "assets", "sounds", "engine")


class AudioEngine:
    """
    Manages engine sound playback with speed-based pitch shifting.

    The audio engine loads WAV files for different speed tiers and plays them
    in a loop, adjusting pitch based on vehicle speed. It also handles one-shot
    shift sounds triggered by paddle shifters.
    """

    def __init__(self):
        self.volume = DEFAULT_VOLUME
        self.current_speed = 0.0
        self.current_tier = 0
        self.current_pitch = 1.0

        # Sound buffers
        self.tier_sounds: dict[int, np.ndarray] = {}
        self.shift_up_sound: Optional[np.ndarray] = None
        self.shift_down_sound: Optional[np.ndarray] = None

        # Playback state
        self.engine_sound_position = 0
        self.shift_sound_buffer: Optional[np.ndarray] = None
        self.shift_sound_position = 0

        # Crossfade state
        self.crossfade_samples = int(SAMPLE_RATE * CROSSFADE_DURATION)
        self.crossfade_position = 0
        self.previous_tier = 0
        self.is_crossfading = False

        self._load_sounds()

    def _load_sounds(self) -> None:
        """Load all sound files into memory."""
        # Load tier sounds
        for tier, filename in enumerate(TIER_SOUND_FILES):
            filepath = os.path.join(SOUNDS_DIR, filename)
            try:
                sound_data = self._load_wav(filepath)
                if sound_data is not None:
                    self.tier_sounds[tier] = sound_data
                    cloudlog.info(f"Loaded engine sound tier {tier}: {filename}")
            except Exception as e:
                cloudlog.error(f"Failed to load {filename}: {e}")

        # Load shift sounds
        try:
            shift_up_path = os.path.join(SOUNDS_DIR, SHIFT_UP_SOUND)
            self.shift_up_sound = self._load_wav(shift_up_path)
            if self.shift_up_sound is not None:
                cloudlog.info(f"Loaded shift up sound: {SHIFT_UP_SOUND}")
        except Exception as e:
            cloudlog.error(f"Failed to load {SHIFT_UP_SOUND}: {e}")

        try:
            shift_down_path = os.path.join(SOUNDS_DIR, SHIFT_DOWN_SOUND)
            self.shift_down_sound = self._load_wav(shift_down_path)
            if self.shift_down_sound is not None:
                cloudlog.info(f"Loaded shift down sound: {SHIFT_DOWN_SOUND}")
        except Exception as e:
            cloudlog.error(f"Failed to load {SHIFT_DOWN_SOUND}: {e}")

    def _load_wav(self, filepath: str) -> Optional[np.ndarray]:
        """Load a WAV file and return as float32 numpy array normalized to [-1, 1]."""
        if not os.path.exists(filepath):
            cloudlog.warning(f"Sound file not found: {filepath}")
            return None

        with wave.open(filepath, 'r') as wav_file:
            # Verify format
            if wav_file.getnchannels() != 1:
                cloudlog.warning(f"Expected mono audio, got {wav_file.getnchannels()} channels: {filepath}")
            if wav_file.getsampwidth() != 2:
                cloudlog.warning(f"Expected 16-bit audio, got {wav_file.getsampwidth() * 8}-bit: {filepath}")
            if wav_file.getframerate() != SAMPLE_RATE:
                cloudlog.warning(f"Expected {SAMPLE_RATE}Hz, got {wav_file.getframerate()}Hz: {filepath}")

            # Read and convert to float32
            num_frames = wav_file.getnframes()
            raw_data = wav_file.readframes(num_frames)
            samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
            # Normalize to [-1, 1]
            samples = samples / 32768.0
            return samples

    def get_speed_tier(self, speed_ms: float) -> int:
        """Determine the sound tier based on speed in m/s."""
        for tier, threshold in enumerate(SPEED_THRESHOLDS_MS):
            if speed_ms < threshold:
                return tier
        return len(SPEED_THRESHOLDS_MS)

    def get_pitch_for_speed(self, speed_ms: float, tier: int) -> float:
        """Calculate pitch multiplier based on speed within the current tier."""
        if tier >= len(PITCH_RANGES):
            tier = len(PITCH_RANGES) - 1

        min_pitch, max_pitch = PITCH_RANGES[tier]

        # Calculate where we are within this tier
        if tier == 0:
            tier_start = 0.0
            tier_end = SPEED_THRESHOLDS_MS[0]
        elif tier < len(SPEED_THRESHOLDS_MS):
            tier_start = SPEED_THRESHOLDS_MS[tier - 1]
            tier_end = SPEED_THRESHOLDS_MS[tier]
        else:
            # Top tier: extrapolate slightly
            tier_start = SPEED_THRESHOLDS_MS[-1]
            tier_end = tier_start * 1.5  # Approximate upper bound

        # Linear interpolation within tier
        if tier_end > tier_start:
            progress = (speed_ms - tier_start) / (tier_end - tier_start)
            progress = max(0.0, min(1.0, progress))
        else:
            progress = 0.5

        return min_pitch + progress * (max_pitch - min_pitch)

    def update_speed(self, speed_ms: float) -> None:
        """Update the current speed and recalculate pitch."""
        self.current_speed = max(0.0, speed_ms)
        new_tier = self.get_speed_tier(self.current_speed)

        # Start crossfade if tier changed
        if new_tier != self.current_tier and new_tier in self.tier_sounds:
            self.previous_tier = self.current_tier
            self.current_tier = new_tier
            self.is_crossfading = True
            self.crossfade_position = 0

        self.current_pitch = self.get_pitch_for_speed(self.current_speed, self.current_tier)

    def trigger_shift_up(self) -> None:
        """Trigger an upshift sound."""
        if self.shift_up_sound is not None:
            self.shift_sound_buffer = self.shift_up_sound
            self.shift_sound_position = 0
            cloudlog.debug("Triggered shift up sound")

    def trigger_shift_down(self) -> None:
        """Trigger a downshift sound."""
        if self.shift_down_sound is not None:
            self.shift_sound_buffer = self.shift_down_sound
            self.shift_sound_position = 0
            cloudlog.debug("Triggered shift down sound")

    def set_volume(self, volume: float) -> None:
        """Set the output volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, volume))

    def _get_pitched_samples(self, sound: np.ndarray, position: int, num_frames: int, pitch: float) -> tuple[np.ndarray, int]:
        """
        Get samples with pitch shifting via linear interpolation.

        Pitch shifting is done by resampling: a pitch > 1.0 plays the sound faster
        (consuming more source samples per output frame), resulting in higher pitch.
        """
        output = np.zeros(num_frames, dtype=np.float32)

        if len(sound) == 0:
            return output, position

        # Number of source samples to consume
        source_samples_needed = num_frames * pitch

        for i in range(num_frames):
            # Calculate the source position for this output sample
            source_pos = position + (i * pitch)

            # Wrap around for looping
            source_pos = source_pos % len(sound)

            # Linear interpolation between adjacent samples
            idx = int(source_pos)
            frac = source_pos - idx
            next_idx = (idx + 1) % len(sound)

            output[i] = sound[idx] * (1 - frac) + sound[next_idx] * frac

        # Update position for next call
        new_position = (position + source_samples_needed) % len(sound)
        return output, int(new_position)

    def get_audio_data(self, num_frames: int) -> np.ndarray:
        """
        Get the next chunk of audio data for playback.

        This method is called by the audio callback to fill the output buffer.
        It mixes the engine sound (with pitch shifting) and any active shift sound.
        """
        output = np.zeros(num_frames, dtype=np.float32)

        # Get engine sound
        if self.current_tier in self.tier_sounds:
            current_sound = self.tier_sounds[self.current_tier]
            engine_data, self.engine_sound_position = self._get_pitched_samples(
                current_sound,
                self.engine_sound_position,
                num_frames,
                self.current_pitch
            )

            # Handle crossfade between tiers
            if self.is_crossfading and self.previous_tier in self.tier_sounds:
                previous_sound = self.tier_sounds[self.previous_tier]
                prev_data, _ = self._get_pitched_samples(
                    previous_sound,
                    self.engine_sound_position,
                    num_frames,
                    self.current_pitch
                )

                # Calculate crossfade weights
                for i in range(num_frames):
                    if self.crossfade_position + i < self.crossfade_samples:
                        fade = (self.crossfade_position + i) / self.crossfade_samples
                        engine_data[i] = prev_data[i] * (1 - fade) + engine_data[i] * fade
                    else:
                        break

                self.crossfade_position += num_frames
                if self.crossfade_position >= self.crossfade_samples:
                    self.is_crossfading = False

            output += engine_data

        # Mix in shift sound if active
        if self.shift_sound_buffer is not None:
            remaining = len(self.shift_sound_buffer) - self.shift_sound_position
            if remaining > 0:
                samples_to_copy = min(remaining, num_frames)
                shift_data = self.shift_sound_buffer[
                    self.shift_sound_position:self.shift_sound_position + samples_to_copy
                ]
                output[:samples_to_copy] += shift_data
                self.shift_sound_position += samples_to_copy
            else:
                self.shift_sound_buffer = None
                self.shift_sound_position = 0

        # Apply volume
        output *= self.volume

        # Clip to prevent distortion
        np.clip(output, -1.0, 1.0, out=output)

        return output

    def callback(self, outdata: np.ndarray, frames: int, time_info, status) -> None:
        """
        Sounddevice callback for audio streaming.

        This follows the pattern from soundd.py.
        """
        if status:
            cloudlog.warning(f"Audio stream status: {status}")

        audio_data = self.get_audio_data(frames)
        outdata[:frames, 0] = audio_data

    def has_sounds_loaded(self) -> bool:
        """Check if any sounds were successfully loaded."""
        return len(self.tier_sounds) > 0
