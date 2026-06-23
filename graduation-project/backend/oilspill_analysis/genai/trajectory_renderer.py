import numpy as np
from scipy.stats import gaussian_kde
from scipy.ndimage import gaussian_filter


# =========================================================
# 1. Convert lat/lon trajectories → density map
# =========================================================
def trajectories_to_density(lat, lon, grid_size=256):
    """
    Convert particle trajectories into smooth oil density map
    """

    if len(lat) == 0 or len(lon) == 0:
        return np.zeros((grid_size, grid_size))

    # normalize coordinates
    x = (lon - np.min(lon)) / (np.ptp(lon) + 1e-8)
    y = (lat - np.min(lat)) / (np.ptp(lat) + 1e-8)

    # KDE smoothing (realistic oil spread shape)
    xi, yi = np.mgrid[0:1:complex(grid_size), 0:1:complex(grid_size)]

    coords = np.vstack([x, y])
    kde = gaussian_kde(coords)

    zi = kde(np.vstack([xi.ravel(), yi.ravel()]))
    density = zi.reshape(xi.shape)

    return density


# =========================================================
# 2. Make oil look realistic (physics + smoothing)
# =========================================================
def enhance_oil_texture(density, sigma=2.0):
    """
    Add natural oil spill appearance (thick center, thin edges)
    """

    # smooth spread
    smoothed = gaussian_filter(density, sigma=sigma)

    # normalize
    smoothed = smoothed / (smoothed.max() + 1e-8)

    # add nonlinear contrast (oil thickness effect)
    smoothed = smoothed ** 1.5

    return smoothed


# =========================================================
# 3. Convert full trajectory sequence → frames
# =========================================================
def build_frames_from_trajectories(trajectory_list):
    """
    trajectory_list = [
        (lat_t0, lon_t0),
        (lat_t1, lon_t1),
        ...
    ]
    """

    frames = []

    for lat, lon in trajectory_list:
        density = trajectories_to_density(lat, lon)
        realistic = enhance_oil_texture(density)

        frames.append(realistic)

    return frames