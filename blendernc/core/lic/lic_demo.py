import lic_internal
import numpy as np
import pylab as plt

dpi = 100
size_x = 1400
size_y = 1000
video = False

vortex_spacing = 0.5
extra_factor = 1.0

a = np.array([1, 0]) * vortex_spacing
b = np.array([np.cos(np.pi / 3), np.sin(np.pi / 3)]) * vortex_spacing
rnv = int(2 * extra_factor / vortex_spacing)
vortices = [n * a + m * b for n in range(-rnv, rnv) for m in range(-rnv, rnv)]
vortices = [
    (x, y)
    for (x, y) in vortices
    if -extra_factor < x < extra_factor and -extra_factor < y < extra_factor
]


xs = np.linspace(-1, 1, size_x).astype(np.float32)[None, :]
ys = np.linspace(-1, 1, size_y).astype(np.float32)[:, None]

vectors = np.zeros((size_y, size_x, 2), dtype=np.float32)
for (x, y) in vortices:
    rsq = (xs - x) ** 2 + (ys - y) ** 2
    vectors[..., 0] += (ys - y) / rsq
    vectors[..., 1] += -(xs - x) / rsq

# texture = np.ones((size_x,size_y)).astype(np.float32)
texture = np.random.rand(size_x, size_y).astype(np.float32) * 0.5

plt.bone()
frame = 0

kernellen = int(0.06 * (size_x))
print(kernellen)
if (kernellen % 2) == 0:
    kernellen += 1


kernel = np.sin(np.arange(kernellen) * np.pi / float(kernellen)) * (
    np.sin((0.5 * np.arange(kernellen) / float(kernellen) + frame))
)

kernel = kernel.astype(np.float32)

image = lic_internal.line_integral_convolution(vectors, texture, kernel)

plt.clf()
plt.axis("off")
plt.figimage(image)
plt.gcf().set_size_inches((size_x / float(dpi), size_y / float(dpi)))
plt.savefig("flow-image.png", dpi=dpi)
