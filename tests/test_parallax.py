import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from engine.parallax import make_city_layers


def test_city_skyline_layers_scroll_at_distinct_depth_rates():
    pygame.init()
    surface = pygame.Surface((960, 540))
    far, middle = make_city_layers()
    far.draw(surface, 1000, (18, 31, 56), (63, 231, 235))
    middle.draw(surface, 1000, (18, 31, 56), (63, 231, 235))
    assert far.offset == 12
    assert middle.offset == 35
    assert far.offset < middle.offset
    assert surface.get_bounding_rect().width > 0


def test_reduced_motion_freezes_parallax_without_hiding_the_scenery():
    pygame.init()
    surface = pygame.Surface((960, 540))
    far, middle = make_city_layers()
    far.draw(surface, 40_000, (18, 31, 56), (63, 231, 235), reduced_motion=True)
    middle.draw(surface, 40_000, (18, 31, 56), (63, 231, 235), reduced_motion=True)
    assert far.offset == middle.offset == 0
    assert surface.get_bounding_rect().width > 0
