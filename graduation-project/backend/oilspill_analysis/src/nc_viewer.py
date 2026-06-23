"""
NetCDF File Viewer Utility
View and inspect .nc files with comprehensive reporting
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Optional

try:
    import xarray as xr
    import netCDF4
    import numpy as np
except ImportError:
    print("ERROR: Required packages not found.")
    print("Install with: pip install xarray netCDF4 numpy")
    sys.exit(1)


def view_nc_file(filepath: str, detailed: bool = False) -> dict:
    """
    View and display information about a NetCDF file.
    
    Parameters:
    -----------
    filepath : str
        Path to .nc file
    detailed : bool
        If True, show all dimensions and detailed statistics
    
    Returns:
    --------
    dict
        Summary of file contents
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        return {}
    
    if not filepath.suffix == '.nc':
        print(f"❌ Not a NetCDF file: {filepath}")
        return {}
    
    print(f"\n{'='*70}")
    print(f"NetCDF File: {filepath.name}")
    print(f"{'='*70}\n")
    
    try:
        # Open with xarray for easier inspection
        ds = xr.open_dataset(filepath)
        
        # Basic info
        print(f"📊 DIMENSIONS:")
        for dim, size in ds.dims.items():
            print(f"  {dim:20s}: {size:10d}")
        
        print(f"\n📈 DATA VARIABLES:")
        for var_name, var_data in ds.data_vars.items():
            dtype = var_data.dtype
            shape = var_data.shape
            dims = var_data.dims
            print(f"  {var_name:20s} | Shape: {str(shape):30s} | Type: {dtype}")
            
            # Show statistics for numeric variables
            if np.issubdtype(dtype, np.number):
                try:
                    valid_data = var_data.values[~np.isnan(var_data.values)]
                    if len(valid_data) > 0:
                        print(f"    {'Min:':15s} {np.nanmin(valid_data):12.6f}")
                        print(f"    {'Max:':15s} {np.nanmax(valid_data):12.6f}")
                        print(f"    {'Mean:':15s} {np.nanmean(valid_data):12.6f}")
                        print(f"    {'Std Dev:':15s} {np.nanstd(valid_data):12.6f}")
                except:
                    pass
        
        # Coordinates
        if ds.coords:
            print(f"\n🗺️  COORDINATES:")
            for coord_name, coord_data in ds.coords.items():
                dtype = coord_data.dtype
                shape = coord_data.shape
                print(f"  {coord_name:20s} | Shape: {str(shape):30s} | Type: {dtype}")
        
        # Global attributes
        if ds.attrs:
            print(f"\n📋 GLOBAL ATTRIBUTES:")
            for key, value in list(ds.attrs.items())[:20]:
                val_str = str(value)[:60]
                print(f"  {key:30s}: {val_str}")
            
            if len(ds.attrs) > 20:
                print(f"  ... and {len(ds.attrs) - 20} more attributes")
        
        # Variable-specific attributes (sampled)
        has_var_attrs = any(var.attrs for var in ds.data_vars.values())
        if has_var_attrs:
            print(f"\n🏷️  VARIABLE ATTRIBUTES (Sample):")
            for var_name in list(ds.data_vars.keys())[:3]:
                if ds[var_name].attrs:
                    print(f"  {var_name}:")
                    for key, value in list(ds[var_name].attrs.items())[:3]:
                        val_str = str(value)[:50]
                        print(f"    {key}: {val_str}")
        
        ds.close()
        
        # Summary
        summary = {
            "file": str(filepath),
            "dimensions": dict(ds.dims),
            "variables": list(ds.data_vars.keys()),
            "coordinates": list(ds.coords.keys()),
            "attributes_count": len(ds.attrs),
        }
        
        print(f"\n{'='*70}\n")
        return summary
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return {}


def view_nc_data(filepath: str, variable: str, head: int = 10) -> None:
    """
    View actual data from a NetCDF variable.
    
    Parameters:
    -----------
    filepath : str
        Path to .nc file
    variable : str
        Variable name to display
    head : int
        Number of rows to display
    """
    filepath = Path(filepath)
    
    try:
        ds = xr.open_dataset(filepath)
        
        if variable not in ds.data_vars and variable not in ds.coords:
            print(f"❌ Variable '{variable}' not found in file")
            print(f"Available variables: {list(ds.data_vars.keys()) + list(ds.coords.keys())}")
            ds.close()
            return
        
        data = ds[variable]
        
        print(f"\n📊 Variable: {variable}")
        print(f"Shape: {data.shape}")
        print(f"Type: {data.dtype}")
        print(f"Dimensions: {data.dims}\n")
        
        # Display data
        if data.ndim == 1:
            print("Data (first 20 values):")
            print(data.values[:min(20, len(data.values))])
        elif data.ndim == 2:
            print("Data (first 5 rows, 5 cols):")
            print(data.values[:min(5, data.shape[0]), :min(5, data.shape[1])])
        else:
            print(f"Data shape: {data.shape}")
            print("(too many dimensions to display)")
        
        ds.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")


def export_nc_to_json(filepath: str, output_path: Optional[str] = None) -> None:
    """
    Export NetCDF metadata and structure to JSON.
    
    Parameters:
    -----------
    filepath : str
        Path to .nc file
    output_path : str, optional
        Output JSON path (default: same name with .json extension)
    """
    filepath = Path(filepath)
    
    if output_path is None:
        output_path = filepath.with_suffix('.json')
    
    try:
        ds = xr.open_dataset(filepath)
        
        summary = {
            "file": str(filepath),
            "dimensions": dict(ds.dims),
            "variables": {
                name: {
                    "shape": list(var.shape),
                    "dtype": str(var.dtype),
                    "dims": var.dims,
                    "attributes": dict(var.attrs)
                }
                for name, var in ds.data_vars.items()
            },
            "coordinates": {
                name: {
                    "shape": list(coord.shape),
                    "dtype": str(coord.dtype),
                    "attributes": dict(coord.attrs)
                }
                for name, coord in ds.coords.items()
            },
            "global_attributes": dict(ds.attrs)
        }
        
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"✓ Exported to: {output_path}")
        ds.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Command-line interface for NC viewer"""
    parser = argparse.ArgumentParser(
        description='NetCDF File Viewer - View and inspect .nc files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python nc_viewer.py data/processed/simulation_20230318.nc
  python nc_viewer.py data/processed/era5_wind_20230318.nc --detailed
  python nc_viewer.py data/processed/cmems_current_20230318.nc --variable lon --head 20
  python nc_viewer.py data/processed/simulation.nc --export
        """
    )
    
    parser.add_argument('file', help='Path to .nc file')
    parser.add_argument('--detailed', action='store_true', help='Show detailed information')
    parser.add_argument('--variable', type=str, help='View specific variable data')
    parser.add_argument('--head', type=int, default=10, help='Number of rows to display')
    parser.add_argument('--export', action='store_true', help='Export metadata to JSON')
    
    args = parser.parse_args()
    
    # View file
    view_nc_file(args.file, detailed=args.detailed)
    
    # View specific variable if requested
    if args.variable:
        view_nc_data(args.file, args.variable, head=args.head)
    
    # Export to JSON if requested
    if args.export:
        export_nc_to_json(args.file)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print("NetCDF File Viewer")
        print("==================")
        print("\nUsage: python nc_viewer.py <filename.nc> [options]")
        print("\nExamples:")
        print("  python nc_viewer.py data/processed/era5_wind_20230318.nc")
        print("  python nc_viewer.py data/processed/simulation_20230318.nc --variable lon")
        print("  python nc_viewer.py data/processed/cmems_current_20230318.nc --export")
        sys.exit(0)
    
    main()
