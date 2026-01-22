#!/usr/bin/env python3
"""
Engine Sound Simulator Daemon

This process plays simulated engine sounds based on vehicle speed and
shift sounds when paddle shifters are used. It is a non-critical process
that only READS data (carState, CAN) and cannot affect vehicle operation.

Safety Guarantee:
- This process only reads from carState (for speed) and CAN (for paddles)
- It never publishes to sendcan or any control topics
- All failures are logged but don't crash - graceful degradation
- Process isolation via separate subprocess

Follows patterns from:
- selfdrive/ui/soundd.py for audio playback
- system/manager/process_config.py for process registration
"""

from cereal import messaging
from openpilot.common.realtime import Ratekeeper
from openpilot.common.swaglog import cloudlog
from openpilot.common.retry import retry

from sunnypilot.enginesoundd.config import (
    SAMPLE_RATE,
    SAMPLE_BUFFER,
    LOOP_FREQUENCY_HZ,
)
from sunnypilot.enginesoundd.audio_engine import AudioEngine
from sunnypilot.enginesoundd.can_reader import create_paddle_reader


class EngineSoundd:
    """
    Main engine sound daemon class.

    Coordinates the audio engine and CAN reader to play speed-based
    engine sounds and paddle-triggered shift sounds.
    """

    def __init__(self):
        cloudlog.info("Initializing EngineSoundd")

        # Initialize audio engine
        self.audio_engine = AudioEngine()
        if not self.audio_engine.has_sounds_loaded():
            cloudlog.warning("No engine sounds loaded - audio will be silent")

        # Initialize paddle reader (will gracefully degrade if CAN unavailable)
        self.paddle_reader = create_paddle_reader()

        # Track last known good speed for graceful degradation
        self.last_speed = 0.0

    @retry(attempts=7, delay=3)
    def get_stream(self, sd):
        """
        Get an audio output stream with retry logic.

        Follows the pattern from soundd.py for robustness.
        """
        # Reload sounddevice to reinitialize portaudio
        sd._terminate()
        sd._initialize()
        return sd.OutputStream(
            channels=1,
            samplerate=SAMPLE_RATE,
            callback=self.audio_engine.callback,
            blocksize=SAMPLE_BUFFER
        )

    def run(self) -> None:
        """
        Main daemon loop.

        Subscribes to carState for speed and can for paddle detection.
        Runs at 50Hz and updates the audio engine accordingly.
        """
        # Import sounddevice after fork (required by portaudio)
        import sounddevice as sd

        # Subscribe to messages (read-only)
        sm = messaging.SubMaster(['carState', 'can'])

        try:
            with self.get_stream(sd) as stream:
                cloudlog.info(f"EngineSoundd stream started: "
                             f"samplerate={stream.samplerate} "
                             f"channels={stream.channels} "
                             f"blocksize={stream.blocksize}")

                rk = Ratekeeper(LOOP_FREQUENCY_HZ)

                while True:
                    # Non-blocking update
                    sm.update(0)

                    # Update speed from carState
                    self._update_speed(sm)

                    # Update paddle reader with CAN data
                    self._update_paddles(sm)

                    # Check for paddle shift events
                    self._check_shift_events()

                    # Keep the loop timing
                    rk.keep_time()

                    # Verify stream is still active
                    if not stream.active:
                        cloudlog.error("Audio stream became inactive")
                        break

        except Exception as e:
            cloudlog.exception(f"EngineSoundd main loop error: {e}")
            raise

    def _update_speed(self, sm) -> None:
        """Update the audio engine with current vehicle speed."""
        try:
            if sm.updated['carState']:
                # vEgo is velocity in m/s
                speed = sm['carState'].vEgo
                self.last_speed = speed
                self.audio_engine.update_speed(speed)
            elif sm.recv_time['carState'] == 0:
                # No carState received yet - use 0 speed
                self.audio_engine.update_speed(0.0)
            # else: use last known speed (carState not updated this frame)
        except Exception as e:
            cloudlog.error(f"Error updating speed: {e}")
            # Fall back to last known speed
            self.audio_engine.update_speed(self.last_speed)

    def _update_paddles(self, sm) -> None:
        """Update paddle reader with CAN data."""
        try:
            if sm.updated['can']:
                can_strings = sm['can']
                self.paddle_reader.update(can_strings)
        except Exception as e:
            cloudlog.error(f"Error updating paddle reader: {e}")

    def _check_shift_events(self) -> None:
        """Check for and handle paddle shift events."""
        try:
            if self.paddle_reader.pop_shift_up():
                self.audio_engine.trigger_shift_up()

            if self.paddle_reader.pop_shift_down():
                self.audio_engine.trigger_shift_down()
        except Exception as e:
            cloudlog.error(f"Error checking shift events: {e}")


def main():
    """Entry point for the enginesoundd process."""
    try:
        daemon = EngineSoundd()
        daemon.run()
    except Exception as e:
        cloudlog.exception(f"EngineSoundd crashed: {e}")
        # Don't re-raise - let the process manager restart us
        raise


if __name__ == "__main__":
    main()
