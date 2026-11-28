import os
﻿from PIL import Image
p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch")
im = Image.open(p)
w, h = im.size
print(f"Image dimensions: {w}x{h}")
# The user image is 1024x576 (scaled from 1920x1080 or windowed)
# Let's find the position of the character select grid
# In the image, grid is near the center-right
# Let's inspect where 'Federer' card is
