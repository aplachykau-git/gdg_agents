"""Community AI Studio agent packages."""

from .common.a2a_patches import apply_a2a_patches
from .gemini_config import load_gemini_environment

apply_a2a_patches()
load_gemini_environment()
