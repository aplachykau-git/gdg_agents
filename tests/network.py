"""Tests that call real external services run only with RUN_NETWORK_TESTS=1."""

import os
import unittest

requires_network = unittest.skipUnless(
    os.getenv("RUN_NETWORK_TESTS") == "1", "calls a real external service; set RUN_NETWORK_TESTS=1 to run"
)
