from __future__ import annotations

import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass(slots=True)
class AudioCue:
    """A short synthesized sound to place on the offline audio timeline."""

    time_seconds: float
    sound_type: str
    amplitude: float = 0.35


class AudioSynthesizer:
    """Generate simple retro-style WAV audio from event-linked cues."""

    def __init__(self, sample_rate: int = 44_100) -> None:
        self.sample_rate = sample_rate

    def synthesize_sound(self, sound_type: str, amplitude: float = 0.35) -> np.ndarray:
        if sound_type == "frontier_push":
            return self._tone(660.0, 0.025, amplitude * 0.55)
        if sound_type == "node_visit":
            return self._tone(440.0, 0.03, amplitude * 0.6)
        if sound_type == "node_expand":
            return self._tone(520.0, 0.045, amplitude * 0.85, harmonic=2.0)
        if sound_type == "goal_reached":
            return self._chord((523.25, 659.25, 783.99), 0.12, amplitude)
        if sound_type == "final_path":
            return self._arpeggio((392.0, 523.25, 659.25), 0.14, amplitude * 0.9)
        raise ValueError(f"Unsupported sound type: {sound_type}")

    def render_cues(self, cues: Iterable[AudioCue], duration_seconds: float) -> np.ndarray:
        total_samples = max(1, int(math.ceil(duration_seconds * self.sample_rate)))
        mix = np.zeros(total_samples, dtype=np.float32)

        for cue in cues:
            sound = self.synthesize_sound(cue.sound_type, cue.amplitude)
            start = int(cue.time_seconds * self.sample_rate)
            end = min(total_samples, start + len(sound))
            if start >= total_samples:
                continue
            mix[start:end] += sound[: end - start]

        return np.clip(mix, -1.0, 1.0)

    def write_wav(self, samples: np.ndarray, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        pcm = np.int16(np.clip(samples, -1.0, 1.0) * 32767)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm.tobytes())
        return path

    def render_timeline_to_wav(
        self,
        cues: Iterable[AudioCue],
        duration_seconds: float,
        output_path: Path,
    ) -> Path:
        samples = self.render_cues(cues, duration_seconds)
        return self.write_wav(samples, output_path)

    def _tone(
        self,
        frequency: float,
        duration_seconds: float,
        amplitude: float,
        harmonic: float = 1.5,
    ) -> np.ndarray:
        count = max(1, int(self.sample_rate * duration_seconds))
        t = np.linspace(0.0, duration_seconds, count, endpoint=False, dtype=np.float32)
        envelope = np.exp(-8.0 * t / max(duration_seconds, 1e-6)).astype(np.float32)
        fundamental = np.sin(2.0 * math.pi * frequency * t)
        overtone = 0.25 * np.sin(2.0 * math.pi * frequency * harmonic * t)
        click_free = np.sin(math.pi * np.clip(t / max(duration_seconds, 1e-6), 0.0, 1.0))
        return (amplitude * (fundamental + overtone) * envelope * click_free).astype(np.float32)

    def _chord(self, frequencies: tuple[float, ...], duration_seconds: float, amplitude: float) -> np.ndarray:
        layers = [self._tone(freq, duration_seconds, amplitude / max(len(frequencies), 1)) for freq in frequencies]
        return np.sum(layers, axis=0, dtype=np.float32)

    def _arpeggio(self, frequencies: tuple[float, ...], duration_seconds: float, amplitude: float) -> np.ndarray:
        segment_duration = duration_seconds / max(len(frequencies), 1)
        segments = [self._tone(freq, segment_duration, amplitude) for freq in frequencies]
        return np.concatenate(segments).astype(np.float32)
