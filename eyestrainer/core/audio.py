from __future__ import annotations

import math
import random
from array import array

import pygame

from ..config import AudioConfig


class Audio:
    def __init__(self, config: AudioConfig) -> None:
        self.config = config
        self.available = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            pygame.mixer.set_num_channels(12)
            self._sounds = {
                "hit": self._make_hit(),
                "miss": self._make_tone(180.0, 60.0, 0.35),
                "countdown": self._make_tone(660.0, 55.0, 0.25),
                "round_end": self._make_round_end(),
                "click": self._make_tone(440.0, 22.0, 0.18),
            }
            self.available = True
        except (pygame.error, OSError):
            self.available = False
        self.apply_config(config)

    def apply_config(self, config: AudioConfig) -> None:
        self.config = config
        volume = max(0.0, min(1.0, config.volume))
        for sound in self._sounds.values():
            sound.set_volume(volume)

    def play(self, name: str) -> None:
        if not self.available:
            return
        if name == "hit" and not self.config.hit:
            return
        if name == "miss" and not self.config.miss:
            return
        if name == "round_end" and not self.config.round_end:
            return
        sound = self._sounds.get(name)
        if sound is not None:
            sound.play()

    def _make_hit(self) -> pygame.mixer.Sound:
        samples = self._samples(880.0, 25.0, 0.5, noise=0.35)
        return self._sound_from_samples(samples)

    def _make_round_end(self) -> pygame.mixer.Sound:
        first = self._samples(660.0, 120.0, 0.35)
        second = self._samples(880.0, 180.0, 0.35)
        return self._sound_from_samples(first + second)

    def _make_tone(
        self, freq: float, duration_ms: float, volume: float
    ) -> pygame.mixer.Sound:
        return self._sound_from_samples(
            self._samples(freq, duration_ms, volume)
        )

    def _samples(
        self, freq: float, duration_ms: float, volume: float, noise: float = 0.0
    ) -> array:
        rate = 44100
        count = max(1, int(rate * duration_ms / 1000.0))
        data = array("h")
        rng = random.Random(int(freq) * 1000 + count)
        for i in range(count):
            t = i / rate
            envelope = min(1.0, i / max(1, rate * 0.002))
            envelope *= max(0.0, 1.0 - i / count) ** 1.5
            value = math.sin(2.0 * math.pi * freq * t) * volume
            if noise:
                value += (rng.random() * 2.0 - 1.0) * noise * 0.35
            data.append(int(max(-1.0, min(1.0, value * envelope)) * 32767))
        return data

    def _sound_from_samples(self, data: array) -> pygame.mixer.Sound:
        return pygame.mixer.Sound(buffer=data.tobytes())
