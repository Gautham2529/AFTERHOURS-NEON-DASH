"""Tiny synthesized chip soundtrack and effects; no external audio assets required."""

from array import array
import math

import pygame


class AudioBus:
    """Manage synthesized background music and rate-limited sound effects."""

    RATE = 22050

    def __init__(self) -> None:
        self.enabled = False
        self.muted = False
        self.last_coin_sound = -1.0
        self.music_volume = 0.24
        self.sfx_volume = 0.18
        self.intensity = 0.35
        self.last_effect_time: dict[str, float] = {}
        self.base_channel = None
        self.boost_channel = None
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=self.RATE, size=-16, channels=1, buffer=512)
            pygame.mixer.set_num_channels(12)
            self.base_channel = pygame.mixer.Channel(0)
            self.boost_channel = pygame.mixer.Channel(1)
            self.base = self._loop((110, 165, 220, 247, 196, 220, 165, 147,
                                    110, 165, 220, 294, 247, 220, 165, 196), 0.22, 0.34)
            self.environment_tracks = {
                "city": (110, 165, 220, 247, 196, 220, 165, 147),
                "metro": (98, 147, 196, 220, 165, 196, 147, 131),
                "industrial": (82, 123, 164, 185, 138, 164, 123, 110),
                "rooftops": (123, 185, 247, 277, 220, 247, 185, 165),
                "night_market": (131, 196, 262, 294, 233, 262, 196, 175),
                "highway": (147, 220, 294, 330, 262, 294, 220, 196),
                "arcade": (165, 247, 330, 370, 294, 330, 247, 220),
            }
            self.environment = "city"
            self.boost = self._loop((330, 392, 494, 659, 494, 554, 740, 880,
                                     330, 494, 659, 740, 554, 659, 880, 988), 0.16, 0.23)
            self.effects = {
                "coin": self._effect((740, 988, 1318), 0.17),
                "magnet": self._effect((247, 330, 440, 554), 0.42),
                "battery": self._effect((330, 440, 587, 784), 0.32),
                "shield": self._effect((330, 440, 660), 0.36),
                "dash": self._effect((180, 360, 720, 1080), 0.4),
                "hit": self._effect((220, 165, 110), 0.32),
                "level": self._effect((523, 659, 784, 1046), 0.48),
                "boost": self._effect((440, 554, 740), 0.35),
                "coin_bonus": self._effect((523, 784, 1046), 0.28),
                "near_miss": self._effect((660, 880), 0.12),
                "jump": self._effect((294, 392, 523), 0.16),
                "slide": self._effect((247, 220, 196), 0.18),
            }
            self.base_channel.set_volume(self.music_volume)
            self.boost_channel.set_volume(self.music_volume * 0.72)
            self.base_channel.play(self.base, loops=-1)
            self.enabled = True
        except (pygame.error, AttributeError):
            self.enabled = False

    @classmethod
    def _loop(cls, notes: tuple[int, ...], seconds: float, volume: float) -> pygame.mixer.Sound:
        samples_per_note = int(cls.RATE * seconds)
        data = array("h")
        for frequency in notes:
            for i in range(samples_per_note):
                t = i / cls.RATE
                fade = min(1.0, i / 250, (samples_per_note-i) / 900)
                wave = math.sin(math.tau * frequency * t) * 0.66
                wave += math.sin(math.tau * frequency * 2 * t) * 0.20
                wave += math.sin(math.tau * frequency * 0.5 * t) * 0.14
                data.append(int(max(-1, min(1, wave * fade * volume)) * 32767))
        return pygame.mixer.Sound(buffer=data.tobytes())

    @classmethod
    def _effect(cls, notes: tuple[int, ...], duration: float) -> pygame.mixer.Sound:
        count = max(1, int(cls.RATE * duration))
        data = array("h")
        for i in range(count):
            t = i / cls.RATE
            pos = min(len(notes)-1, int(t / duration * len(notes)))
            local = (t / duration * len(notes)) % 1
            freq = notes[pos]
            env = (1-local) ** 1.7
            tone = math.sin(math.tau * freq * t) * 0.7 + math.sin(math.tau * freq * 2.01 * t) * 0.3
            data.append(int(tone * env * 0.52 * 32767))
        return pygame.mixer.Sound(buffer=data.tobytes())

    def play(self, name: str) -> None:
        """Play a known sound effect when audio is enabled and not muted."""
        if self.enabled and not self.muted and name in self.effects:
            now = pygame.time.get_ticks() / 1000
            cooldown = .55 if name == "near_miss" else .12 if name == "coin" else 0.0
            if now - self.last_effect_time.get(name, -999.0) < cooldown:
                return
            self.last_effect_time[name] = now
            if name == "coin" and now - self.last_coin_sound < 0.12:
                return
            if name == "coin":
                self.last_coin_sound = now
            self.effects[name].set_volume(self.sfx_volume)
            self.effects[name].play()

    def set_music_volume(self, value: float) -> None:
        """Set the backing-music volume, clamped to the supported range."""
        self.music_volume = max(0.0, min(0.5, value))
        if self.enabled:
            self.base_channel.set_volume(self.music_volume * (.82 + .18 * self.intensity))
            self.boost_channel.set_volume(self.music_volume * (.58 + .42 * self.intensity) * 0.72)

    def set_intensity(self, value: float) -> None:
        """Modulate backing layers within the user's configured volume ceiling."""
        self.intensity = max(0.0, min(1.0, float(value)))
        if self.enabled:
            self.base_channel.set_volume(self.music_volume * (.82 + .18 * self.intensity))
            self.boost_channel.set_volume(self.music_volume * (.58 + .42 * self.intensity) * 0.72)

    def set_sfx_volume(self, value: float) -> None:
        """Set the sound-effect volume, clamped to the supported range."""
        self.sfx_volume = max(0.0, min(0.5, value))

    def set_boost(self, active: bool) -> None:
        """Start or stop the boost music layer."""
        if not self.enabled or self.muted:
            return
        if active and not self.boost_channel.get_busy():
            self.boost_channel.play(self.boost, loops=-1)
        elif not active and self.boost_channel.get_busy():
            self.boost_channel.stop()

    def set_environment(self, key: str) -> None:
        """Swap the synthesized backing motif when the run enters a new world."""
        if not self.enabled or key == self.environment or key not in self.environment_tracks:
            return
        try:
            self.environment = key
            self.base = self._loop(self.environment_tracks[key], 0.22, 0.30)
            if not self.muted:
                self.base_channel.play(self.base, loops=-1)
                self.base_channel.set_volume(self.music_volume * (.82 + .18 * self.intensity))
        except pygame.error:
            pass

    def toggle_mute(self) -> None:
        """Toggle music playback without changing the configured volumes."""
        self.muted = not self.muted
        if self.enabled:
            if self.muted:
                self.base_channel.stop()
                self.boost_channel.stop()
            elif not self.base_channel.get_busy():
                self.base_channel.play(self.base, loops=-1)
