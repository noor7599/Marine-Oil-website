# heatmap_generator.py
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde

def create_heatmap(lat, lon, grid_size=100):
    xy = np.vstack([lon, lat])
    kde = gaussian_kde(xy)

    x_min, x_max = lon.min(), lon.max()
    y_min, y_max = lat.min(), lat.max()

    x_grid, y_grid = np.mgrid[
        x_min:x_max:grid_size*1j,
        y_min:y_max:grid_size*1j
    ]

    positions = np.vstack([x_grid.ravel(), y_grid.ravel()])
    density = kde(positions).reshape(grid_size, grid_size)

    return density