"""
ScreenExplorer - A Python app for capturing screen areas and extracting text using Ollama
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from .screen_capture import ScreenSelector
from .text_extractor import extract_text_and_describe
from .main import ScreenExplorerApp