import typing as tp
from dataclasses import dataclass
import itertools
import numpy as np
import xarray as xr
from tqdm import tqdm

from oceanbench._src.utils.exceptions import IncompleteScanConfiguration, DangerousDimOrdering
from oceanbench._src.geoprocessing.select import select_bounds, select_bounds_multiple
from oceanbench._src.utils.custom_dtypes import Bounds
from oceanbench._src.datasets.utils import (
    get_dims_xrda,
    check_lists_equal,
    update_dict_xdims,
    check_lists_subset,
    get_patches_size,
    get_slices,
    list_product
)


@dataclass
class XRDABatcher:
    """
    A dataclass for xarray.DataArray with on the fly slicing.
    ### Usage: ####
    If you want to be able to reconstruct the input
    the input xr.DataArray should:
        - have coordinates
        - have for each dim of patch_dim (size(dim) - patch_dim(dim)) divisible by stride(dim)
    the batches passed to self.reconstruct should:
    """
    da: xr.DataArray
    patches: tp.Dict[str, int]
    strides: tp.Dict[str, int]
    da_dims: tp.Dict[str, int]
    da_size: tp.Dict[str, int]
    return_coords: bool = False
    
    def __init__(
            self, 
            da: xr.DataArray,
            patches: tp.Optional[tp.Dict[str, int]]=None,
            strides: tp.Optional[tp.Dict[str, int]]=None,
            domain_limits: tp.Optional[tp.Dict]=None,
            check_full_scan: bool=False,
        ):
        """
        Args:
            da (xr.DataArray): xarray datarray to be referenced during the iterations
            patches (Optional[Dict]): dict of da dimension to size of a patch
                (defaults to one stride per dimension)
            strides (Optional[Dict]): dict of dims to stride size
                (defaults to one stride per dimension)
            domain_limits (Optional[Dict]): dict of da dimension to slices of domain
                to select for patch extractions
            check_full_scan bool: if True raise an error if the whole domain is
                not scanned by the patch size stride combination
                
        Attributes:
            return_coords (bool): Option to return coords during the iterations

            da (xr.DataArray): xarray datarray to be referenced during the iterations
            patch_dims (OrderedDict): dict of da dimension to size of a patch
                (defaults to the same dimension as dataset stride per dimension)
            strides (OrderedDict): dict of dims to stride size
                (defaults to one stride per dimension)
            domain_limits (OrderedDict): dict of da dimension to slices of domain
                to select for patch extractions
            ds_size (OrderedDict): the dictionary of dimensions for the slicing
            da_dims (OrderedDict): the dictionary of the original dimensions
        """
        if domain_limits is not None:
            da_dims = get_dims_xrda(da)
            check_lists_subset(list(domain_limits.keys()), list(da_dims.keys()))
            da = da.sel(**domain_limits)
        
        self.da = da
        self.da_dims = get_dims_xrda(da)
        
        self.da_size, self.patches, self.strides = get_patches_size(
            dims=self.da_dims,
            patches=patches if patches is not None else {},
            strides=strides if strides is not None else {},
        )
        if check_full_scan:
            for dim in self.patches:
                if (self.da_dims[dim] - self.patches[dim]) % self.strides[dim] != 0:
                    msg = f"\nIncomplete scan in dimension dim {dim}:"
                    msg += f"\nDataArray shape on this dim {self.da_dims[dim]} "
                    msg += f"\nPatch_size along this dim {self.patches[dim]} "
                    msg += f"\nStride along this dim {self.strides[dim]} "
                    msg += f"\n[shape - patch_size] should be divisible by stride: "
                    msg += f"{(self.da_dims[dim] - self.patches[dim]) % self.strides[dim]}"
                    raise IncompleteScanConfiguration(msg)
        
    def __repr__(self) -> str:
        msg = "XArray Patcher"
        msg += "\n=============="
        msg += f"\nDataArray Size: {self.da_dims}"
        msg += f"\nPatches:        {self.patches}"
        msg += f"\nStrides:        {self.strides}"
        msg += f"\nNum Batches:    {self.da_size}"
        return msg
    
    def __str__(self) -> str:
        msg = "XArray Patcher"
        msg += "\n=============="
        msg += f"\nDataArray size: {self.da_dims}"
        msg += f"\nPatches:        {self.patches}"
        msg += f"\nStrides:        {self.strides}"
        msg += f"\nNum Batches:    {self.da_size}"
        return msg
    
    @property
    def coord_names(self) -> tp.List[str]:
        return list(self.da_dims.keys())
    
    def __len__(self):
        return list_product(list(self.da_size.values()))
    
    def __iter__(self):
        for i in range(len(self)):
            yield self[i]
    
    def __getitem__(self, item):

        slices = get_slices(
            idx=item, 
            da_size=self.da_size, 
            patches=self.patches, 
            strides=self.strides
        )
        
        item = self.da.isel(**slices)
        
        item = item.transpose(*self.coord_names)
        
        if self.return_coords:
            return item.coords.to_dataset()
                    
        return item.data.astype(np.float32)
    
    def reconstruct(
        self, 
        batches: tp.List[np.ndarray], 
        dims_labels: tp.Optional[tp.List[str]]=None, 
        weight: tp.Optional[np.ndarray]=None
    ) -> xr.DataArray:
        """
        takes as input a list of np.ndarray of dimensions (b, *, *patch_dims)
        return a stitched xarray.DataArray with the coords of patch_dims
    batches: list of torch tensor correspondin to batches without shuffle
        weight: tensor of size patch_dims corresponding to the weight of a prediction depending on the position on the patch (default to ones everywhere)
        overlapping patches will be averaged with weighting
        """

        items = list(itertools.chain(*batches))
        rec_da = self.reconstruct_from_items(
            items=items,
            dims_labels=dims_labels,
            weight=weight
        ) 
        
        rec_da.attrs = self.da.attrs
        
        return rec_da
    
    def reconstruct_from_items(
        self,
        items: tp.Iterable, 
        dims_labels: tp.Optional[tp.Iterable[str]]=None, 
        weight=None
    ):
        
        item_shape = items[0].shape
        num_items = len(item_shape)
        
        # get coordinate labels
        coords = self.get_coords()
        coords_labels = list(coords[0].dims.keys())
        
        # assume the items are the same as the coordinates
        if dims_labels is None:
            dims_labels = [coords_labels[i] for i in range(len(coords_labels))]
        
        num_dim_labels = len(dims_labels)

        # add any extra dimensions not specified
        if num_dim_labels < num_items:
            new_dims  = [f"v{i+1}" for i in range(num_items - num_dim_labels)]
            dims_labels = dims_labels + new_dims
            num_dim_labels = len(dims_labels)

        # check user specified dimensions
        msg = f"Length of dim labels does not match length of dims."
        msg += f"\nDims Label: {dims_labels} \nShape: {item_shape}"
        msg += f"\nNum Labels: {num_dim_labels} \nNum Items: {num_items}"
        assert num_dim_labels == num_items, msg

        
        # check for subset of coordinate arrays
        coords_labels = set(dims_labels).intersection(coords_labels)


        # check_lists_subset(coords_labels, dims_labels)
        all_items_shape = dict(zip(dims_labels, item_shape))

        patches = {ikey: ivalue for ikey, ivalue in self.patches.items() if ikey in dims_labels}
        patch_values = list(patches.values())
        patch_names = list(patches.keys())
        
        msg = "No Coordinates to merge..."
        msg += f"\nDims: {dims_labels}"
        msg += f"\nCoords: {list(coords[0].dims.keys())}"
        msg += f"\nPatches: {self.patches.keys()}"
        assert len(coords_labels) > 0, msg

        msg = "Mismatch between coords and patches..."
        msg += f"\nDims: {dims_labels}"
        msg += f"\nCoords: {list(coords[0].dims.keys())}"
        msg += f"\nPatches: {self.patches.keys()}"

        assert len(coords_labels) == len(patch_names), msg


        # (maybe) update weight matrix
        if weight is None:
            
            weight = np.ones(patch_values)
        else:
            msg = "Weight array is not the same size as total dims "
            msg += "or not the same value"
            msg += f"\nWeight: {list(weight.shape)} | Patches: {patch_values} | Dims: {items[0].shape}"
            
            assert len(weight.shape) ==  len(patch_values), msg

        w = xr.DataArray(weight, dims=patch_names)


        # create data arrays from coords
        das = [
            xr.DataArray(it, dims=dims_labels, coords=co[coords_labels].coords)
            for it, co in zip(items, coords)
                ]

        msg = "New Data Array is not the same size as items"
        msg += "or not the same value"
        msg += f"\n{das[0].shape} | Items: {all_items_shape}"
        assert len(das[0].shape) == len(all_items_shape), msg
        assert set(das[0].shape) == set(all_items_shape.values()), msg

        # get new shape from 
        new_shape = {
            idim: self.da[idim].shape[0] if idim in coords_labels
            else item_shape[i]
            for i, idim in enumerate(dims_labels) 
        }
        coords = {d: self.da[d] for d in patch_names if d in dims_labels}
        rec_da = xr.DataArray(
            np.zeros([*new_shape.values()]),
            dims=dims_labels,
            coords=coords
        )

        count_da = xr.zeros_like(rec_da)

        for ida in tqdm(das):
            rec_da.loc[ida.coords] = rec_da.sel(ida.coords) + ida * w
            count_da.loc[ida.coords] = count_da.sel(ida.coords) + w

        return rec_da / count_da
    
    def get_coords(self) -> tp.List[xr.DataArray]:
        self.return_coords = True
        coords = []
        try:
            for i in range(len(self)):
                coords.append(self[i])
        finally:
            self.return_coords = False
            return coords
