from pathlib import Path

import warnings
import pytest
import tempfile
import multiprocessing as mp

import numpy as np
import scipy.sparse
import roicat
from roicat import helpers, ROInet, pipelines, util


def test_pipeline_tracking_simple(dir_data_test, array_hasher):
    defaults = util.get_default_parameters(pipeline='tracking')
    seed = 0
    params_partial = {
        'general': {
            'random_seed': seed,
        },
        'data_loading': {
            'dir_outer': dir_data_test,
            'data_kind': 'roicat',
            'data_roicat': {'filename_search': r'data_roicat_obj.pkl'},
        },
        'clustering': {
            'automatic_mixing': {
                'kwargs_findParameters': {
                    'n_patience': 30,  ## Reduced number to speed up
                    'max_trials': 100,  ## Reduced number to speed up
                },
                'n_jobs_findParameters': 1,  ## THIS IS CRITICAL TO ENSURE REPORDUCIBILITY. Parallelization prevents reproducibility.
            },
        },
    }
    params = util.prepare_params(params_partial, defaults)
    results, run_data, params = pipelines.pipeline_tracking(params)

    #check that results fields are not empty
    assert results['clusters'] != 0, "Error: clusters field is empty"
    assert results['ROIs'] != 0, "Error: ROIs field is empty"
    assert results['input_data'] != 0, "Error: input_data field is empty"
    assert results['quality_metrics'] != 0, "Error: quality_metrics field is empty"
    
    assert len(results['clusters']['labels_dict']) == len(results['quality_metrics']['cluster_intra_means']), "Error: Cluster data is mismatched"
    assert len(results['clusters']['labels_dict']) == results['clusters']['labels_bool_bySession'][0].shape[1], "Error: Cluster data is mismatched"

    ## Check similarity graph hashes
    hashes_true = {
        'sim': {
            'sf_cat': ('sparse_mat', 'add32bf95fec7ce6'), 
            's_SWT': ('sparse_mat', '87ff259eec323755'), 
            's_sf': ('sparse_mat', 'ed3b409516e8da90'), 
            's_NN': ('sparse_mat', 'cb70ba51b350794d'), 
            's_sesh': ('sparse_mat', '0e078943d80b5745'), 
            's_NN_z': ('sparse_mat', '252aca63859c6576'), 
            's_SWT_z': ('sparse_mat', '41e8316a3d2cb59b'),
        },
        'clusterer': {
            'dConj': ('sparse_mat', '922a766c4dcfefc0'), 
            'sConj': ('sparse_mat', '549d7182ba719012'), 
            'graph_pruned': ('sparse_mat', 'd91248bdde3eae60'), 
            's_sf_pruned': ('sparse_mat', '57d31e13b6426a63'), 
            's_NN_pruned': ('sparse_mat', '6c2e686b954334f2'),
            's_SWT_pruned': ('sparse_mat', '94f457912ac62490'),
            's_sesh_pruned': ('sparse_mat', 'aca4101e2f28bf6a'),
            'dConj_pruned': ('sparse_mat', 'c00763b7e1bd9a3f'),
            'labels': ('array', '57be86439cf8dc69'),
            'violations_labels': ('array', 'ef46db3751d8e999'),
        },
    }
    for key_module, hashes_module in hashes_true.items():
        for key_obj, (datatype, hash_val) in hashes_module.items():
            if datatype == 'sparse_mat':
                hash_val_run = array_hasher(run_data[key_module][key_obj]['data'])
            elif datatype == 'array':
                hash_val_run = array_hasher(run_data[key_module][key_obj])
            print(f'Object hashed -- Module: {key_module.ljust(9)}, Object: {key_obj.ljust(17)}, Hash: {hash_val_run}')
            assert hash_val_run == hashes_true[key_module][key_obj][1], f"Hash value mismatch for rundata['{key_module}']['{key_obj}']"

            
def test_ROInet(make_ROIs, array_hasher):
    ROI_images = make_ROIs
    size_im=(36,36)
    data_custom = roicat.data_importing.Data_roicat()
    data_custom.set_ROI_images(ROI_images, um_per_pixel=1.5)
    
    DEVICE = helpers.set_device(use_GPU=True, verbose=True)
    dir_temp = tempfile.gettempdir()

    roinet = ROInet.ROInet_embedder(
        device=DEVICE,  ## Which torch device to use ('cpu', 'cuda', etc.)
        dir_networkFiles=dir_temp,  ## Directory to download the pretrained network to
        download_method='check_local_first',  ## Check to see if a model has already been downloaded to the location (will skip if hash matches)
        download_url='https://osf.io/x3fd2/download',  ## URL of the model
        download_hash='7a5fb8ad94b110037785a46b9463ea94',  ## Hash of the model file
        forward_pass_version='latent',  ## How the data is passed through the network
        verbose=True,  ## Whether to print updates
    )
    dataloader = roinet.generate_dataloader(
        ROI_images=data_custom.ROI_images,  ## Input images of ROIs
        um_per_pixel=data_custom.um_per_pixel,  ## Resolution of FOV
        pref_plot=False,  ## Whether or not to plot the ROI sizes
        
        jit_script_transforms=False,  ## (advanced) Whether or not to use torch.jit.script to speed things up
        
        batchSize_dataloader=8,  ## (advanced) PyTorch dataloader batch_size
        pinMemory_dataloader=True,  ## (advanced) PyTorch dataloader pin_memory
        numWorkers_dataloader=mp.cpu_count(),  ## (advanced) PyTorch dataloader num_workers
        persistentWorkers_dataloader=True,  ## (advanced) PyTorch dataloader persistent_workers
        prefetchFactor_dataloader=2,  ## (advanced) PyTorch dataloader prefetch_factor
    );
    latents = roinet.generate_latents();

    ## Check shapes
    assert dataloader.shape[0] == data_custom.n_roi_total, "Error: dataloader shape is mismatched"
    assert dataloader.shape[1] == size_im[0], "Error: dataloader shape does not match input image size"
    assert dataloader.shape[2] == size_im[1], "Error: dataloader shape does not match input image size"
    assert latents.shape[0] == data_custom.n_roi_total, "Error: latents shape does not match n_roi_total"
    


    
