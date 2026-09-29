"""Conservative detection of vertically smeared frames, using decoded pixels."""

def check_pixels(pixels: bytes, width: int = 160, height: int = 90) -> None:
    if len(pixels) != width * height:
        raise ValueError("incomplete decoded snapshot")
    # A textured row repeated vertically is characteristic of decoder smearing.
    # Flat walls and dark night frames are deliberately excluded.
    run = 0
    for y in range(1, height):
        previous = pixels[(y - 1) * width:y * width]
        row = pixels[y * width:(y + 1) * width]
        difference = sum(abs(a - b) for a, b in zip(previous, row)) / width
        ordered = sorted(row)
        contrast = ordered[int(width * .9)] - ordered[int(width * .1)]
        run = run + 1 if difference < 1.5 and contrast > 25 else 0
        if run >= 18:
            raise ValueError("suspected vertical banding: textured rows repeat over 20% of image")
