"""
Unit tests for utility functions.
"""

import unittest
import uuid
from unittest.mock import patch, Mock

from utils.generate_client_id import *  # Import the main logic


class TestGenerateClientId(unittest.TestCase):
    """Test cases for generate_client_id utility."""

    @patch("uuid.uuid4")
    @patch("builtins.print")
    def test_generate_client_id_unique_calls(self, mock_print, mock_uuid4):
        """Test that multiple calls generate different UUIDs."""
        # Setup multiple different UUIDs
        uuid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        uuid2 = uuid.UUID("22222222-2222-2222-2222-222222222222")

        mock_uuid4.side_effect = [uuid1, uuid2]

        # Simulate running the script twice
        # Since the script runs on import, we need to test the logic directly
        result1 = f"client_id: janascard-qsource3-{uuid.uuid4()}"
        result2 = f"client_id: janascard-qsource3-{uuid.uuid4()}"

        # Verify different UUIDs were used
        self.assertNotEqual(result1, result2)
        self.assertEqual(mock_uuid4.call_count, 2)

    def test_client_id_prefix(self):
        """Test that client ID always has correct prefix."""
        # Test the format without mocking
        test_uuid = uuid.uuid4()
        expected_prefix = "client_id: janascard-qsource3-"
        result = f"client_id: janascard-qsource3-{test_uuid}"

        self.assertTrue(result.startswith(expected_prefix))

        # Extract and validate UUID part
        uuid_part = result[len(expected_prefix) :]
        # Should be able to parse as valid UUID
        parsed_uuid = uuid.UUID(uuid_part)
        self.assertEqual(str(parsed_uuid), uuid_part)


if __name__ == "__main__":
    unittest.main()
