import copy
import os

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import sparse
import scipy.sparse

from . import util, helpers


def display_toggle_image_stack(images, image_size=None, clim=None, interpolation='nearest'):
    """
    Display images in a slider using Jupyter Notebook.
    RH 2023

    Args:
        images (list of numpy arrays or PyTorch tensors):
            List of images as numpy arrays or PyTorch tensors
        image_size (tuple of ints, optional):
            Tuple of (width, height) for resizing images.
            If None (default), images are not resized.
        clim (tuple of floats, optional):
            Tuple of (min, max) values for scaling pixel intensities.
            If None (default), min and max values are computed from the images
             and used as bounds for scaling.
        interpolation (string, optional):
            String specifying the interpolation method for resizing.
            Options: 'nearest', 'box', 'bilinear', 'hamming', 'bicubic', 'lanczos'.
            Uses the Image.Resampling.* methods from PIL.
    """
    from IPython.display import display, HTML
    import numpy as np
    import base64
    from PIL import Image
    from io import BytesIO
    import torch
    import datetime
    import hashlib
    import sys
    
    def normalize_image(image, clim=None):
        """Normalize the input image using the min-max scaling method. Optionally, use the given clim values for scaling."""
        if isinstance(image, torch.Tensor):
            image = image.detach().cpu().numpy()

        if clim is None:
            clim = (np.min(image), np.max(image))

        norm_image = (image - clim[0]) / (clim[1] - clim[0])
        norm_image = np.clip(norm_image, 0, 1)
        return (norm_image * 255).astype(np.uint8)
    def resize_image(image, new_size, interpolation):
        """Resize the given image to the specified new size using the specified interpolation method."""
        if isinstance(image, torch.Tensor):
            image = image.detach().cpu().numpy()

        pil_image = Image.fromarray(image.astype(np.uint8))
        resized_image = pil_image.resize(new_size, resample=interpolation)
        return np.array(resized_image)
    def numpy_to_base64(numpy_array):
        """Convert a numpy array to a base64 encoded string."""
        img = Image.fromarray(numpy_array.astype('uint8'))
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("ascii")
    def process_image(image):
        """Normalize, resize, and convert image to base64."""
        # Normalize image
        norm_image = normalize_image(image, clim)

        # Resize image if requested
        if image_size is not None:
            norm_image = resize_image(norm_image, image_size, interpolation_method)

        # Convert image to base64
        return numpy_to_base64(norm_image)


    # Check if being called from a Jupyter notebook
    if 'ipykernel' not in sys.modules:
        raise RuntimeError("This function must be called from a Jupyter notebook.")

    # Create a dictionary to map interpolation string inputs to Image objects
    interpolation_methods = {
        'nearest': Image.Resampling.NEAREST,
        'box': Image.Resampling.BOX,
        'bilinear': Image.Resampling.BILINEAR,
        'hamming': Image.Resampling.HAMMING,
        'bicubic': Image.Resampling.BICUBIC,
        'lanczos': Image.Resampling.LANCZOS,
    }

    # Check if provided interpolation method is valid
    if interpolation not in interpolation_methods:
        raise ValueError("Invalid interpolation method. Choose from 'nearest', 'box', 'bilinear', 'hamming', 'bicubic', or 'lanczos'.")

    # Get the actual Image object for the specified interpolation method
    interpolation_method = interpolation_methods[interpolation]

    # Generate a unique identifier for the slider
    slider_id = hashlib.sha256(str(datetime.datetime.now()).encode()).hexdigest()

    # Process all images in the input list
    base64_images = [process_image(img) for img in images]

    # Get the image size for display
    image_size = images[0].shape[:2] if image_size is None else image_size

    # Generate the HTML code for the slider
    html_code = f"""
    <div>
        <input type="range" id="imageSlider_{slider_id}" min="0" max="{len(base64_images) - 1}" value="0">
        <img id="displayedImage_{slider_id}" src="data:image/png;base64,{base64_images[0]}" style="width: {image_size[1]}px; height: {image_size[0]}px;">
        <span id="imageNumber_{slider_id}">Image 0/{len(base64_images) - 1}</span>
    </div>

    <script>
        (function() {{
            let base64_images = {base64_images};
            let current_image = 0;
    
            function updateImage() {{
                let slider = document.getElementById("imageSlider_{slider_id}");
                current_image = parseInt(slider.value);
                let displayedImage = document.getElementById("displayedImage_{slider_id}");
                displayedImage.src = "data:image/png;base64," + base64_images[current_image];
                let imageNumber = document.getElementById("imageNumber_{slider_id}");
                imageNumber.innerHTML = "Image " + current_image + "/{len(base64_images) - 1}";
            }}
            
            document.getElementById("imageSlider_{slider_id}").addEventListener("input", updateImage);
        }})();
    </script>
    """

    display(HTML(html_code))


def compute_colored_FOV(
    spatialFootprints,
    FOV_height,
    FOV_width,
    labels,
    cmap='random',
    alphas_labels=None,
    alphas_sf=None,
):
    """
    Computes a set of images of FOVs of spatial footprints, colored
     by the predicted class.

    Args:
        spatialFootprints (list of scipy.sparse.csr_matrix):
            Each element is all the spatial footprints for a given session.
        FOV_height (int):
            Height of the field of view
        FOV_width (int):
            Width of the field of view
        labels (list of arrays or array):
            Label (will be a unique color) for each spatial footprint.
            Each element is all the labels for a given session.
            Can either be a list of integer labels for each session,
             or a single array with all the labels concatenated.
        cmap (str or matplotlib.colors.ListedColormap):
            Colormap to use for the labels.
            If 'random', then a random colormap is generated.
            Else, this is passed to matplotlib.colors.ListedColormap.
        alphas_labels (np.ndarray):
            Alpha value for each label.
            shape (n_labels,) which is the same as the number of unique
             labels len(np.unique(labels))
        alphas_sf (list of np.ndarray):
            Alpha value for each spatial footprint.
            Can either be a list of alphas for each session, or a single array
             with all the alphas concatenated.
    """
    spatialFootprints = [spatialFootprints] if isinstance(spatialFootprints, np.ndarray) else spatialFootprints

    ## Check inputs
    assert all([scipy.sparse.issparse(sf) for sf in spatialFootprints]), "spatialFootprints must be a list of scipy.sparse.csr_matrix"

    n_roi = np.array([sf.shape[0] for sf in spatialFootprints], dtype=np.int64)
    n_roi_cumsum = np.concatenate([[0], np.cumsum(n_roi)]).astype(np.int64)
    n_roi_total = sum(n_roi)

    def _fix_list_of_arrays(v):
        if isinstance(v, np.ndarray) or (isinstance(v, list) and isinstance(v[0], (np.ndarray, list)) is False):
            v = [v[b_l: b_u] for b_l, b_u in zip(n_roi_cumsum[:-1], n_roi_cumsum[1:])]
        assert (isinstance(v, list) and isinstance(v[0], (np.ndarray, list))), "input must be a list of arrays or a single array of integers"
        return v
    
    labels = _fix_list_of_arrays(labels)
    alphas_sf = _fix_list_of_arrays(alphas_sf) if alphas_sf is not None else None

    labels_cat = np.concatenate(labels)
    u = np.unique(labels_cat)
    n_c = len(u)

    if alphas_labels is None:
        alphas_labels = np.ones(n_c)
    alphas_labels = np.clip(alphas_labels, a_min=0, a_max=1)
    assert len(alphas_labels) == n_c, f"len(alphas_labels)={len(alphas_labels)} != n_c={n_c}"

    if alphas_sf is None:
        alphas_sf = np.ones(len(labels_cat))
    if isinstance(alphas_sf, list):
        alphas_sf = np.concatenate(alphas_sf)
    alphas_sf = np.clip(alphas_sf, a_min=0, a_max=1)
    assert len(alphas_sf) == len(labels_cat), f"len(alphas_sf)={len(alphas_sf)} != len(labels_cat)={len(labels_cat)}"
    
    h, w = FOV_height, FOV_width

    rois = scipy.sparse.vstack(spatialFootprints)
    rois = rois.multiply(1.0/rois.max(1).A).power(1)

    if n_c > 1:
        colors = helpers.rand_cmap(nlabels=n_c, verbose=False)(np.linspace(0.,1.,n_c, endpoint=True)) if cmap=='random' else cmap(np.linspace(0.,1.,n_c, endpoint=True))
        colors = colors / colors.max(1, keepdims=True)
    else:
        colors = np.array([[0,0,0,0]])

    if np.isin(-1, labels_cat):
        colors[0] = [0,0,0,0]

    labels_squeezed = helpers.squeeze_integers(labels_cat)
    labels_squeezed -= labels_squeezed.min()

    rois_c = scipy.sparse.hstack([rois.multiply(colors[labels_squeezed, ii][:,None]) for ii in range(4)]).tocsr()
    rois_c.data = np.minimum(rois_c.data, 1)

    ## apply alpha
    rois_c = rois_c.multiply(alphas_labels[labels_squeezed][:,None] * alphas_sf[:,None]).tocsr()

    ## make session_bool
    session_bool = util.make_session_bool(n_roi)

    rois_c_bySessions = [rois_c[idx] for idx in session_bool.T]

    rois_c_bySessions_FOV = [r.max(0).toarray().reshape(4, h, w).transpose(1,2,0)[:,:,:3] for r in rois_c_bySessions]

    return rois_c_bySessions_FOV


def crop_cluster_ims(ims):
    """
    Crops the images to the smallest rectangle containing all non-zero pixels.
    RH 2022

    Args:
        ims (np.ndarray):
            Images to crop.

    Returns:
        np.ndarray:
            Cropped images.
    """
    ims_max = np.max(ims, axis=0)
    z_im = ims_max > 0
    z_where = np.where(z_im)
    z_top = z_where[0].max()
    z_bottom = z_where[0].min()
    z_left = z_where[1].min()
    z_right = z_where[1].max()
    
    ims_copy = copy.deepcopy(ims)
    im_out = ims_copy[:, max(z_bottom-1, 0):min(z_top+1, ims.shape[1]), max(z_left-1, 0):min(z_right+1, ims.shape[2])]
    im_out[:,(0,-1),:] = 1
    im_out[:,:,(0,-1)] = 1
    return im_out

def display_cropped_cluster_ims(
    spatialFootprints, 
    labels, 
    FOV_height=512, 
    FOV_width=1024,
    n_labels_to_display=100,
):
    """
    Displays the cropped cluster images.
    RH 2023

    Args:
        spatialFootprints (list):
            List of spatial footprints.
        labels (np.ndarray):
            Labels for each ROI.
        FOV_height (int, optional):
            Height of the field of view.
        FOV_width (int, optional):
            Width of the field of view.
        n_labels_to_display (int, optional):
            Number of labels to display.
    """
    import scipy.sparse

    labels_unique = np.unique(labels[labels>-1])

    ROI_ims_sparse = scipy.sparse.vstack(spatialFootprints)
    ROI_ims_sparse = ROI_ims_sparse.multiply( ROI_ims_sparse.max(1).power(-1) ).tocsr()

    labels_bool_t = scipy.sparse.vstack([scipy.sparse.csr_matrix(labels==u) for u in np.sort(np.unique(labels_unique))]).tocsr()
    labels_bool_t = labels_bool_t[:n_labels_to_display]

    def helper_crop_cluster_ims(ii):
        idx = labels_bool_t[ii].indices
        return np.concatenate(list(crop_cluster_ims(ROI_ims_sparse[idx].toarray().reshape(len(idx), FOV_height, FOV_width))), axis=1)

    labels_sfCat = [helper_crop_cluster_ims(ii) for ii in range(labels_bool_t.shape[0])]

    for sf in labels_sfCat[:n_labels_to_display]:
        plt.figure(figsize=(40,1))
        plt.imshow(sf, cmap='gray')
        plt.axis('off')


def select_region_scatterPlot(
    data, 
    images_overlay=None, 
    idx_images_overlay=None, 
    size_images_overlay=None,
    frac_overlap_allowed=0.5,
    image_overlay_raster_size=None,
    path=None, 
    figsize=(300,300),
    alpha_points=0.5,
    size_points=1,
    color_points='k',
):
    """Select a region of a scatter plot and return the indices 
     of the points in that region via a function call.

    Args:
        data (np.ndarray):
            Input data to draw a scatterplot.
            Shape must be (n_samples, 2).
        images_overlay (A 3D or 4D array):
            A 3D array of grayscale images or a 4D array of RGB images,
            where the first dimension is the number of images.
        idx_images_overlay (np.ndarray):
            A vector of the data indices corresponding to each images in images_overlay.
            Shape must be (n_images,).
        size_images_overlay (float, optional):
            Size of each overlay images. Unit is relative to each axis.
            This simply scales the resolution of the overlay raster.
        frac_overlap_allowed (float, optional):
            Fraction of overlap allowed between the selected region and the overlay images.
            Only used when size_images_overlay is None.
        image_overlay_raster_size (tuple of int or float, optional):
            Size of the rasterized image overlay. Units are pixels.
            If None, will be set to figsize.
        path (str, optional):
            Temporary file path that saves selected indices. 
        figsize (tuple, optional):
            Size of the figure. Unit in pixel. 
        alpha_points (float, optional):
            Alpha value of the scatter plot points. 
        size_points (float, optional):
            Size of the scatter plot points. 
        color_points (str or list, optional):
            Color of the scatter plot points. 
            If a list, must be the same length as data.shape[0] and values
             must be valid holoviews color names.
    """
    import holoviews as hv
    import numpy as np
    import xxhash

    import tempfile
    try:
        from IPython.display import display
    except:
        print('Warning: Could not import IPython.display. Cannot display plot.')
        return None, None

    hv.extension('bokeh')

    assert isinstance(data, np.ndarray), 'data must be a numpy array'
    assert data.ndim == 2, 'data must have 2 dimensions'
    assert data.shape[1] == 2, 'data must have 2 columns'

    ## Ingest inputs
    if images_overlay is not None:
        assert isinstance(images_overlay, np.ndarray), 'images_overlay must be a numpy array'
        assert (images_overlay.ndim == 3) or (images_overlay.ndim == 4), 'images_overlay must have 3 or 4 dimensions'
        assert images_overlay.shape[0] == idx_images_overlay.shape[0], 'images_overlay must have the same number of images as idx_images_overlay'

    if image_overlay_raster_size is None:
        image_overlay_raster_size = figsize

    # Declare some points, set alpha, size, color
    if isinstance(color_points, str):
        color_points = np.array([color_points] * data.shape[0])
    elif isinstance(color_points, list):
        color_points = np.array(color_points)
    else:
        assert isinstance(color_points, np.ndarray), 'color_points must be a string, list, or numpy array'
        assert color_points.shape[0] == data.shape[0], 'color_points must be the same length as data.shape[0]. If a numpy array, the first dimension must be the same length as data.shape[0]'
    _, idx_unique, inverse_unique = np.unique(np.array([xxhash.xxh64(x).hexdigest() for x in color_points]), return_index=True, return_inverse=True)
    color_points_unique = color_points[idx_unique]

    points = hv.Points([])
    for ii,c in enumerate(color_points_unique):
        p = hv.Points(data[inverse_unique==ii])
        p.opts(
            alpha=alpha_points,
            size=size_points,
            color=c if isinstance(c, str) else tuple(c),
            tools=['lasso_select', 'box_select'],
            width=figsize[0],
            height=figsize[1],
        )
        points *= p

    # if isinstance(color_points, str):
    #     points.opts(color=color_points)
    # elif isinstance(color_points, list):
    #     assert len(color_points) == data.shape[0], 'color_points must be the same length as data.shape[0]'
    #     points.opts(color=hv.Cycle(values=color_points))

    # Declare points as source of selection stream
    selection = hv.streams.Selection1D(source=points)

    path_tempFile = tempfile.gettempdir() + '/indices.csv' if path is None else path

    # Write function that uses the selection indices to slice points and compute stats
    def callback(index):
        ## Save the indices to a temporary file.
        ## First delete the file if it already exists.
        if os.path.exists(path_tempFile):
            os.remove(path_tempFile)
        ## Then save the indices to the file. Open in a protected way that blocks other threads from opening it
        with open(path_tempFile, 'w') as f:
            f.write(','.join([str(i) for i in index]))

        return points
        
    selection.param.watch_values(callback, 'index')
    layout = points.opts(
        tools=['lasso_select', 'box_select'],
        width=figsize[0],
        height=figsize[1],
    )

    # If images are provided, overlay them on the points
    def norm_img(image):
        """
        Normalize 2D grayscale image
        """        
        normalized_image = (image - np.min(image)) / np.max(image)
        return normalized_image

    if images_overlay is not None and idx_images_overlay is not None:
        min_emb = np.nanmin(data, axis=0)  ## shape (2,)
        max_emb = np.nanmax(data, axis=0)  ## shape (2,)
        range_emb = max_emb - min_emb  ## shape (2,)
        aspect_ratio_ims = (range_emb[1] / range_emb[0])  ## shape (1,)
        lims_canvas = ((min_emb - range_emb*0.05), (max_emb + range_emb*0.05))  ## ( shape (2,)(mins), shape (2,)(maxs) )
        range_canvas = lims_canvas[1] - lims_canvas[0]  ## shape (2,)

        n_ims = images_overlay.shape[0] if images_overlay is not None else 0

        if size_images_overlay is None:
            import sklearn
            min_image_distance = sklearn.neighbors.NearestNeighbors(
                n_neighbors=2, 
                algorithm='auto', 
                metric='euclidean'
            ).fit(
                data[idx_images_overlay]
            ).kneighbors_graph(
                data[idx_images_overlay], 
                n_neighbors=2,
                mode='distance'
            )
            min_image_distance.eliminate_zeros()
            min_image_distance = np.nanmin(min_image_distance.data)
            size_images_overlay = float(min_image_distance) * (1 + frac_overlap_allowed)
            print(f'Using size_images_overlay = {size_images_overlay}')

        assert isinstance(size_images_overlay, (int, float, np.ndarray)), 'size_images_overlay must be an int, float, or shape (2,) numpy array'
        if isinstance(size_images_overlay, (int, float)):
            size_images_overlay = np.array([size_images_overlay / aspect_ratio_ims, size_images_overlay])
        assert size_images_overlay.shape == (2,), 'size_images_overlay must be an int, float, or shape (2,) numpy array'
        
        # Create a large canvas to hold all the images
        iors = image_overlay_raster_size
        canvas = np.zeros((iors[0], iors[1],4))

        interp_0 = scipy.interpolate.interp1d(
            x=np.linspace(lims_canvas[0][0], lims_canvas[1][0], num=iors[0], endpoint=False),
            y=np.linspace(0,iors[0],num=iors[0], endpoint=False),
        )
        interp_1 = scipy.interpolate.interp1d(
            x=np.linspace(lims_canvas[0][1], lims_canvas[1][1], num=iors[1], endpoint=False),
            y=np.linspace(0,iors[1],num=iors[1], endpoint=False),
        )
           
        for image, idx in zip(images_overlay, idx_images_overlay):
            sz_im_0 = int((size_images_overlay[0] / range_canvas[0]) * iors[0])
            sz_im_1 = int((size_images_overlay[1] / range_canvas[1]) * iors[1])
            im_interp = scipy.interpolate.RegularGridInterpolator(
                points=(
                    np.linspace(0, images_overlay.shape[1], num=images_overlay.shape[1], endpoint=False),
                    np.linspace(0, images_overlay.shape[2], num=images_overlay.shape[2], endpoint=False),
                ),
                values=image,
                bounds_error=False,
                fill_value=0,
            )(np.stack(np.meshgrid(
                np.linspace(0, images_overlay.shape[1], num=sz_im_0, endpoint=False),
                np.linspace(0, images_overlay.shape[2], num=sz_im_1, endpoint=False),
            ), axis=-1))

            image_rgb = np.stack([norm_img(im_interp), norm_img(im_interp), norm_img(im_interp)], axis=-1) if im_interp.ndim == 2 else im_interp

            x1 = int(interp_0(data[idx,0]) - sz_im_0 / 2)
            y1 = int(interp_1(data[idx,1]) - sz_im_1 / 2)
            x2 = int(interp_0(data[idx,0]) + sz_im_0 / 2)
            y2 = int(interp_1(data[idx,1]) + sz_im_1 / 2)
            
            assert x1 >= 0 and x2 <= iors[0] and y1 >= 0 and y2 <= iors[1], f'Image is out of bounds of canvas: y1={y1}, y2={y2}, x1={x1}, x2={x2}, sz_im_0={sz_im_0}, sz_im_1={sz_im_1}, iors={iors}'
            
            canvas[y1:y2, x1:x2,:3] = image_rgb
            canvas[y1:y2, x1:x2,3] = 1
        
        canvas = np.flipud(canvas)

        # Now create a single hv.RGB object
        imo = hv.RGB(canvas, bounds=(lims_canvas[0][0], lims_canvas[0][1], lims_canvas[1][0], lims_canvas[1][1]))


        ## Set bounds of the plot
        layout = layout.redim.range(x=(lims_canvas[0][0], lims_canvas[1][0]), y=(lims_canvas[0][1], lims_canvas[1][1]))

        layout *= imo

    ## start layout with lasso tool active
    layout = layout.opts(
        active_tools=[
            'lasso_select', 
            'wheel_zoom',
        ]
    )

    # Display plot
    display(layout)

    def fn_get_indices():
        if os.path.exists(path_tempFile):
            with open(path_tempFile, 'r') as f:
                indices = f.read().split(',')
            indices = [int(i) for i in indices if i != ''] if len(indices) > 0 else None
            return indices
        else:
            return None

    return fn_get_indices, layout, path_tempFile


def get_spread_out_points(data, n_ims=1000, dist_im_to_point=0.3, border_frac=0.05, device='cpu'):
    """
    Given a set of points, return the indices of a subset of points that are spread out.
    Intended to be used to overlay images on a scatter plot of points.
    RH 2023

    Args:
        data (np.ndarray):
            Array of shape (N,2) containing the points to be spread out (i,j).
        n_ims (int):
            Number of indices to return corresponding to the number of images
             to be displayed.
        dist_im_to_point (float):
            Minimum distance between an image and it's nearest point.
            Images with a minimum distance to a point greater than this value
             will be discarded.
        border_frac (float):
            Fraction of the range of the data to add as a border around the
             points.
        device (str):
            Device to use for torch operations.

    Returns:
        idx_images_overlay (np.ndarray):
            Array of shape (n_ims,) containing the indices of the points to
             overlay images on.
    """
    import torch
    DEVICE = device

    min_data = np.nanmin(data, axis=0)  ## shape (2,)
    max_data = np.nanmax(data, axis=0)  ## shape (2,)
    range_data = max_data - min_data  ## shape (2,)
    lims_canvas = ((min_data - range_data*border_frac), (max_data + range_data*border_frac))  ## ([
    
    sz_im = (range_data / (n_ims**0.5))
    
    grid_canvas = np.meshgrid(
        np.linspace(lims_canvas[0][0], lims_canvas[1][0], int(n_ims**0.5)),
        np.linspace(lims_canvas[0][1], lims_canvas[1][1], int(n_ims**0.5)),
        indexing='xy',
    )
    grid_canvas_flat = np.vstack([g.reshape(-1) for g in grid_canvas]).T

    dist_grid_to_imIdx = torch.as_tensor(data, device=DEVICE, dtype=torch.float32)[:,None,:] - \
        torch.as_tensor(grid_canvas_flat, device=DEVICE, dtype=torch.float32)[None,:,:]
    distNorm_grid_to_imIdx = torch.linalg.norm(dist_grid_to_imIdx, dim=2)
    distMin_grid_to_imIdx = torch.min(distNorm_grid_to_imIdx, dim=0)
    max_dist = (np.min(sz_im))*dist_im_to_point
    idx_good = distMin_grid_to_imIdx.values < max_dist
    idx_images_overlay = distMin_grid_to_imIdx.indices[idx_good]

    return idx_images_overlay