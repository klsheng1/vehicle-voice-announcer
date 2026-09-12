"""In-vehicle voice announcement system.

A simulated drive emits traffic events (red lights, stops, school zones,
congestion...); a dispatcher applies priority preemption and cooldown
suppression; a pluggable TTS stack renders the announcements — IndexTTS 2
(zero-shot voice cloning) first, neural edge-tts or offline Windows SAPI as
fallbacks.
"""

__version__ = "1.0.0"
