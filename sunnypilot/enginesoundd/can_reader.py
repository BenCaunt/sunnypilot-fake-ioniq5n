"""
CAN reader for paddle shifter detection.

This module reads CAN messages to detect paddle shifter usage on Hyundai CAN-FD
vehicles. It only READS data - it never writes to any CAN bus.

Verified on Hyundai Ioniq 5 SE:
- Message: CRUISE_BUTTONS (ID 463 / 0x1CF)
- Bus: 0 (ECAN)
- RIGHT_PADDLE: bit 25 (upshift) - byte 3 value 34 when pressed
- LEFT_PADDLE: bit 27 (downshift) - byte 3 value 40 when pressed
"""

from typing import Optional

from openpilot.common.swaglog import cloudlog

from sunnypilot.enginesoundd.config import (
    HYUNDAI_CANFD_DBC,
    CAN_BUS_ECAN,
    PADDLE_CAN_MESSAGE,
    PADDLE_CAN_MESSAGE_ID,
    PADDLE_CAN_FREQUENCY,
    PADDLE_RIGHT_SIGNAL,
    PADDLE_LEFT_SIGNAL,
    PADDLE_BYTE_INDEX,
    PADDLE_LEFT_BYTE_VALUE,
    PADDLE_RIGHT_BYTE_VALUE,
)


class PaddleShifterReader:
    """
    Reads paddle shifter signals from CAN bus.

    This class uses CANParser in read-only mode to detect paddle shifter usage.
    It performs edge detection (0→1 transition) to trigger shift events.
    Falls back to raw byte parsing if CANParser signals aren't available.
    """

    def __init__(self):
        self.can_parser = None
        self.initialized = False
        self.use_raw_parsing = False

        # Edge detection state
        self.prev_right_paddle = 0
        self.prev_left_paddle = 0

        # Event flags - set when paddle is pulled, cleared after reading
        self.shift_up_triggered = False
        self.shift_down_triggered = False

        self._init_parser()

    def _init_parser(self) -> None:
        """Initialize the CAN parser for paddle shifter messages."""
        try:
            from opendbc.can import CANParser

            # Define the messages to parse: (message_name, frequency_hz)
            messages = [(PADDLE_CAN_MESSAGE, PADDLE_CAN_FREQUENCY)]

            self.can_parser = CANParser(HYUNDAI_CANFD_DBC, messages, CAN_BUS_ECAN)
            self.initialized = True
            cloudlog.info(f"PaddleShifterReader initialized: {PADDLE_CAN_MESSAGE} (0x{PADDLE_CAN_MESSAGE_ID:X}) on bus {CAN_BUS_ECAN}")

        except ImportError as e:
            cloudlog.warning(f"CANParser not available, using raw parsing: {e}")
            self.initialized = True
            self.use_raw_parsing = True
        except Exception as e:
            cloudlog.warning(f"CANParser init failed, using raw parsing: {e}")
            self.initialized = True
            self.use_raw_parsing = True

    def update(self, can_strings: list) -> None:
        """
        Update the parser with new CAN data and detect paddle events.

        Args:
            can_strings: List of CAN message strings from the 'can' socket
        """
        if not self.initialized:
            return

        try:
            if self.use_raw_parsing:
                self._update_raw(can_strings)
            else:
                self._update_canparser(can_strings)
        except Exception as e:
            cloudlog.error(f"Error reading paddle signals: {e}")

    def _update_canparser(self, can_strings: list) -> None:
        """Update using CANParser for signal decoding."""
        if self.can_parser is None:
            return

        # Update the parser with new CAN data
        self.can_parser.update_strings(can_strings)

        # Read paddle signals
        vl = self.can_parser.vl
        if PADDLE_CAN_MESSAGE not in vl:
            return

        msg = vl[PADDLE_CAN_MESSAGE]
        right_paddle = int(msg.get(PADDLE_RIGHT_SIGNAL, 0))
        left_paddle = int(msg.get(PADDLE_LEFT_SIGNAL, 0))

        self._process_paddle_state(right_paddle, left_paddle)

    def _update_raw(self, can_strings: list) -> None:
        """
        Update using raw byte parsing as fallback.

        Parses CAN messages directly looking for message ID 0x1CF (463)
        and checking byte 3 for paddle values.
        """
        from cereal import messaging

        # Parse the can strings to find our message
        for can_str in can_strings:
            try:
                # can_strings is a list of capnp Event messages
                for msg in can_str.can:
                    # Check if this is our message on the right bus
                    if msg.address == PADDLE_CAN_MESSAGE_ID and msg.src == CAN_BUS_ECAN:
                        if len(msg.dat) > PADDLE_BYTE_INDEX:
                            byte_val = msg.dat[PADDLE_BYTE_INDEX]

                            # Decode paddle state from byte value
                            left_paddle = 1 if byte_val == PADDLE_LEFT_BYTE_VALUE else 0
                            right_paddle = 1 if byte_val == PADDLE_RIGHT_BYTE_VALUE else 0

                            self._process_paddle_state(right_paddle, left_paddle)
            except Exception:
                # Skip malformed messages
                pass

    def _process_paddle_state(self, right_paddle: int, left_paddle: int) -> None:
        """Process paddle state and detect edges."""
        # Edge detection: trigger on 0→1 transition
        if right_paddle == 1 and self.prev_right_paddle == 0:
            self.shift_up_triggered = True
            cloudlog.debug("Right paddle (upshift) detected")

        if left_paddle == 1 and self.prev_left_paddle == 0:
            self.shift_down_triggered = True
            cloudlog.debug("Left paddle (downshift) detected")

        # Store current state for next comparison
        self.prev_right_paddle = right_paddle
        self.prev_left_paddle = left_paddle

    def pop_shift_up(self) -> bool:
        """
        Check and clear the shift up event flag.

        Returns:
            True if an upshift was triggered since last check
        """
        if self.shift_up_triggered:
            self.shift_up_triggered = False
            return True
        return False

    def pop_shift_down(self) -> bool:
        """
        Check and clear the shift down event flag.

        Returns:
            True if a downshift was triggered since last check
        """
        if self.shift_down_triggered:
            self.shift_down_triggered = False
            return True
        return False

    def is_available(self) -> bool:
        """Check if the CAN parser was successfully initialized."""
        return self.initialized


class MockPaddleShifterReader:
    """
    Mock paddle shifter reader for testing without CAN bus.

    This can be used when testing on a development machine or when
    the CAN parser fails to initialize.
    """

    def __init__(self):
        self.shift_up_triggered = False
        self.shift_down_triggered = False
        cloudlog.info("Using MockPaddleShifterReader (no CAN available)")

    def update(self, can_strings: list) -> None:
        """Mock update - does nothing."""
        pass

    def pop_shift_up(self) -> bool:
        """Check and clear the shift up event flag."""
        if self.shift_up_triggered:
            self.shift_up_triggered = False
            return True
        return False

    def pop_shift_down(self) -> bool:
        """Check and clear the shift down event flag."""
        if self.shift_down_triggered:
            self.shift_down_triggered = False
            return True
        return False

    def is_available(self) -> bool:
        """Mock reader is always 'available' but does nothing."""
        return True

    def simulate_shift_up(self) -> None:
        """Simulate an upshift for testing."""
        self.shift_up_triggered = True

    def simulate_shift_down(self) -> None:
        """Simulate a downshift for testing."""
        self.shift_down_triggered = True


def create_paddle_reader() -> PaddleShifterReader:
    """
    Factory function to create the appropriate paddle reader.

    Returns a real PaddleShifterReader if CANParser is available,
    otherwise returns a MockPaddleShifterReader.
    """
    reader = PaddleShifterReader()
    if reader.is_available():
        return reader
    else:
        cloudlog.warning("CANParser not available, using mock paddle reader")
        return MockPaddleShifterReader()
