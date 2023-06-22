from pathlib import Path

import warnings
import pytest

import numpy as np
import scipy.sparse

from roicat import helpers, util

def test_pipeline_tracking_simple(dir_data_test, array_hasher):
    options = util.Options(options={})
    outputs = roicat.pipeline.tracking(options)

    util.compare_testing_outputs(output)

def test_ROInet(dir_data_test, array_hasher):
    ROI_images = make_ROIs(
        n_sessions=10,
        max_rois_per_session=100,
        size_im=(36,36),
    )
    data_custom.set_ROI_images(ROI_images, um_per_pixel=1.5)

    DEVICE = roicat.helpers.set_device(use_GPU=True, verbose=True)
    dir_temp = tempfile.gettempdir()

    roinet = roicat.ROInet.ROInet_embedder(
        device=DEVICE,  ## Which torch device to use ('cpu', 'cuda', etc.)
        dir_networkFiles=dir_temp,  ## Directory to download the pretrained network to
        download_method='check_local_first',  ## Check to see if a model has already been downloaded to the location (will skip if hash matches)
        download_url='https://osf.io/x3fd2/download',  ## URL of the model
        download_hash='7a5fb8ad94b110037785a46b9463ea94',  ## Hash of the model file
        forward_pass_version='latent',  ## How the data is passed through the network
        verbose=True,  ## Whether to print updates
    )
    roinet.generate_dataloader(
        ROI_images=data.ROI_images,  ## Input images of ROIs
        um_per_pixel=data.um_per_pixel,  ## Resolution of FOV
        pref_plot=False,  ## Whether or not to plot the ROI sizes
        
        jit_script_transforms=False,  ## (advanced) Whether or not to use torch.jit.script to speed things up
        
        batchSize_dataloader=8,  ## (advanced) PyTorch dataloader batch_size
        pinMemory_dataloader=True,  ## (advanced) PyTorch dataloader pin_memory
        numWorkers_dataloader=mp.cpu_count(),  ## (advanced) PyTorch dataloader num_workers
        persistentWorkers_dataloader=True,  ## (advanced) PyTorch dataloader persistent_workers
        prefetchFactor_dataloader=2,  ## (advanced) PyTorch dataloader prefetch_factor
    );
    roinet.generate_latents();

    ## Check shapes
    