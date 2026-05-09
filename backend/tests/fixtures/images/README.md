# Image fixtures

Per `specs/integrations.md` §3, this directory exists to hold image
fixtures for the `image_hash` integration tests.

We generate fixtures in-process via PIL inside `test_image_hash.py`
(see the `red_png_bytes` / `red_noise_png_bytes` / `blue_png_bytes`
fixtures) — no binary blobs are checked into git.

If you need a real on-disk PNG for ad-hoc debugging:

```python
from PIL import Image
Image.new("RGB", (100, 100), color=(255, 0, 0)).save("red-100x100.png")
```
