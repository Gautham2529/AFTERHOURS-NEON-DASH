"""Original, palette-driven pixel art primitives used by the world renderer."""

import pygame


def draw_person(target: pygame.Surface, x: int, y: int,
                accent: tuple[int, int, int], name: str,
                facing: str = "down", motion: float = 0) -> None:
    """Draw a shaded 12x16 humanoid sprite with directional walk frames."""
    sprite = pygame.Surface((12, 16), pygame.SRCALPHA)
    skin = (224, 174, 133) if name != "Kestrel" else (188, 157, 139)
    hair = {"Eli": (26, 31, 43), "Iko": (33, 49, 62),
            "Mrs. Vale": (118, 76, 89), "Sora": (39, 35, 44),
            "Uncle Ren": (80, 64, 48), "Kestrel": (43, 58, 62),
            "Mira": (66, 42, 77), "Operator": (24, 43, 43)}.get(name, (42, 39, 48))

    pygame.draw.ellipse(sprite, (6, 9, 15, 150), (1, 13, 10, 3))
    step = int(motion) % 2 if motion else 0
    pygame.draw.rect(sprite, (24, 26, 33), (3, 11 + step, 2, 4))
    pygame.draw.rect(sprite, (24, 26, 33), (7, 12 - step, 2, 4))
    pygame.draw.rect(sprite, (19, 24, 34), (2, 7, 8, 5))
    pygame.draw.rect(sprite, accent, (1, 7, 2, 4))
    pygame.draw.rect(sprite, accent, (9, 7, 2, 4))
    pygame.draw.rect(sprite, skin, (3, 2, 6, 5))
    pygame.draw.rect(sprite, hair, (2, 1, 8, 3))
    pygame.draw.rect(sprite, hair, (2, 3, 2, 3))
    pygame.draw.rect(sprite, (245, 206, 165), (4, 4, 1, 1))
    pygame.draw.rect(sprite, (30, 30, 37), (7, 4, 1, 1))
    shade = tuple(max(0, channel - 35) for channel in accent)
    pygame.draw.rect(sprite, shade, (3, 8, 6, 1))

    if facing == "up":
        pygame.draw.rect(sprite, hair, (3, 2, 6, 5))
    elif facing in ("left", "right"):
        side = 2 if facing == "left" else 8
        pygame.draw.rect(sprite, hair, (side, 2, 2, 4))

    target.blit(sprite, (x - 2, y - 2))
