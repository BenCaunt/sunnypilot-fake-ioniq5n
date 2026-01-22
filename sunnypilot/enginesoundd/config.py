"""
Configuration constants for the engine sound simulator.

This module contains all configurable parameters for the enginesoundd process.
"""

# Audio settings
SAMPLE_RATE = 48000
SAMPLE_BUFFER = 4096  # Approx 85ms at 48kHz
DEFAULT_VOLUME = 0.5
MAX_VOLUME = 1.0
MIN_VOLUME = 0.1

# Main loop frequency
LOOP_FREQUENCY_HZ = 50

# Speed thresholds in m/s (converted from mph)
# 5 mph = 2.24 m/s, 25 mph = 11.18 m/s, 50 mph = 22.35 m/s, 80 mph = 35.76 m/s
SPEED_THRESHOLDS_MS = [2.24, 11.18, 22.35, 35.76]

# Pitch ranges for each speed tier [min_pitch, max_pitch]
# Tier 0 (0-5 mph): idle sound
# Tier 1 (5-25 mph): low sound
# Tier 2 (25-50 mph): mid sound
# Tier 3 (50-80 mph): high sound
# Tier 4 (80+ mph): high sound (extended)
PITCH_RANGES = [
    (0.8, 1.0),   # Tier 0: Idle
    (1.0, 1.3),   # Tier 1: Low
    (1.2, 1.5),   # Tier 2: Mid
    (1.4, 1.8),   # Tier 3: High
    (1.7, 2.0),   # Tier 4: Very high
]

# Sound file names for each tier
TIER_SOUND_FILES = [
    "engine_idle.wav",
    "engine_low.wav",
    "engine_mid.wav",
    "engine_high.wav",
    "engine_high.wav",  # Tier 4 reuses high sound
]

# Shift sound files
SHIFT_UP_SOUND = "shift_up.wav"
SHIFT_DOWN_SOUND = "shift_down.wav"

# CAN Configuration for Hyundai CAN-FD (Ioniq 5 SE verified)
# Based on hyundai_canfd_generated.dbc and vehicle testing
HYUNDAI_CANFD_DBC = "hyundai_canfd_generated"

# CAN bus number - verified on Ioniq 5 SE
CAN_BUS_ECAN = 0

# CRUISE_BUTTONS message (ID 463 / 0x1CF)
PADDLE_CAN_MESSAGE = "CRUISE_BUTTONS"
PADDLE_CAN_MESSAGE_ID = 463  # 0x1CF
PADDLE_CAN_FREQUENCY = 50  # Hz

# Paddle shifter signals within CRUISE_BUTTONS message
# Verified from Ioniq 5 SE CAN analysis:
# - RIGHT_PADDLE at bit 25, size 1 (upshift)
# - LEFT_PADDLE at bit 27, size 1 (downshift)
# Values: 0 = "Not Pulled", 1 = "Pulled"
PADDLE_RIGHT_SIGNAL = "RIGHT_PADDLE"  # Upshift
PADDLE_LEFT_SIGNAL = "LEFT_PADDLE"    # Downshift

# Raw byte parsing fallback (byte 3 of message)
# When LEFT_PADDLE pressed: byte 3 = 40 (0x28) - bit 3 set + SET_ME_1
# When RIGHT_PADDLE pressed: byte 3 = 34 (0x22) - bit 1 set + SET_ME_1
# When neither pressed: byte 3 = 32 (0x20) - just SET_ME_1
PADDLE_BYTE_INDEX = 3
PADDLE_LEFT_BYTE_VALUE = 40   # 0x28 - left paddle pulled
PADDLE_RIGHT_BYTE_VALUE = 34  # 0x22 - right paddle pulled
PADDLE_IDLE_BYTE_VALUE = 32   # 0x20 - neither paddle pulled

# Crossfade duration when changing sound tiers (in seconds)
CROSSFADE_DURATION = 0.1

# Shift sound duration (approximate, actual depends on file)
SHIFT_SOUND_DURATION = 0.5
