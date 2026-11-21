import os

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from engine.audio import AudioBus


def test_generated_audio_supports_independent_clamped_levels_mute_and_boost():
    pygame.mixer.quit()
    bus = AudioBus()
    assert bus.enabled
    bus.set_music_volume(-2)
    bus.set_sfx_volume(2)
    assert bus.music_volume == 0
    assert bus.sfx_volume == .5
    bus.set_intensity(5)
    assert bus.intensity == 1
    bus.set_environment("metro")
    assert bus.environment == "metro"
    bus.play("coin")
    bus.set_boost(True)
    assert bus.boost_channel.get_busy()
    bus.toggle_mute()
    assert bus.muted
    bus.play("hit")
    bus.toggle_mute()
    assert not bus.muted
    bus.set_boost(False)
    pygame.mixer.quit()
