"""Provides function for using a SpeechBrain model."""

import gc
import os

import speechbrain as sb
import torch
from flwr.common import ndarrays_to_parameters
from hyperpyyaml import load_hyperpyyaml

from flwr_baselines.publications.wav2vec2.tedlium.model.sb_w2v2 import ASR, get_weights
from flwr_baselines.publications.wav2vec2.tedlium.preprocessing.data_loader import (
    dataio_prepare,
)


def int_model(  # pylint: disable=too-many-arguments,too-many-locals
    cid,
    config_path,
    save_path,
    data_path,
    label_path=None,
    device="cpu",
    parallel=True,
    evaluate=False,
):
    """Setting up the experiment.

    Loading the hyperparameters from config files and
    command-line overrides, setting the correct path for the
    corresponding clients, and creating the model.
    """
    # Load hyperparameters file with command-line overrides
    save_path = save_path + "client_" + str(cid)
    # Override with FLOWER PARAMS
    if evaluate:
        overrides = {
            "output_folder": save_path,
            "number_of_epochs": 1,
            "test_batch_size": 4,
            "device": device,
        }

    else:
        overrides = {"output_folder": save_path}

    if label_path is None:
        label_path = os.path.join(save_path, "label_encoder.txt")

    _, run_opts, _ = sb.parse_arguments(config_path)
    run_opts["device"] = device
    run_opts["data_parallel_backend"] = parallel

    with open(config_path) as fin:
        params = load_hyperpyyaml(fin, overrides)

    # This logic follow the data_path is a path to csv folder file
    # All train/dev/test csv files are in the same name format for server and client
    # Example:
    # server: /users/server/train.csv
    # client: /users/client_1/train.csv
    # Modify (if needed) the if else logic to fit with path format

    if int(cid) != 19999:
        params["data_folder"] = os.path.join(data_path, "client_" + str(cid))
    else:
        params["data_folder"] = os.path.join(data_path, "client_" + str(1300))

    params["train_csv"] = params["data_folder"] + "/ted_test.csv"
    params["valid_csv"] = params["data_folder"] + "/ted_test.csv"
    params["test_csv"] = params["data_folder"] + "/ted_test.csv"

    params["label_encoder"] = label_path

    # Create experiment directory
    sb.create_experiment_directory(
        experiment_directory=params["output_folder"],
        hyperparams_to_save=config_path,
        overrides=overrides,
    )

    # Create the datasets objects as well as tokenization and encoding :-D
    train_data, valid_data, test_data, label_encoder = dataio_prepare(params)
    # Trainer initialization

    asr_brain = ASR(
        modules=params["modules"],
        hparams=params,
        run_opts=run_opts,
        checkpointer=params["checkpointer"],
    )
    asr_brain.label_encoder = label_encoder
    asr_brain.label_encoder.add_unk()

    # Adding objects to trainer.
    gc.collect()
    return asr_brain, [train_data, valid_data, test_data]


def pre_trained_point(path, save, hparams, device, parallel):
    """Returns a pre-trained model from a path and hyperparameters."""
    state_dict = torch.load(path)

    overrides = {"output_folder": save}

    _, run_opts, _ = sb.parse_arguments(hparams)
    with open(hparams) as fin:
        params = load_hyperpyyaml(fin, overrides)

    run_opts["device"] = device
    run_opts["data_parallel_backend"] = parallel

    asr_brain = ASR(
        modules=params["modules"],
        hparams=params,
        run_opts=run_opts,
        checkpointer=params["checkpointer"],
    )

    asr_brain.modules.load_state_dict(state_dict)
    weights = get_weights(asr_brain.modules)
    pre_trained = ndarrays_to_parameters(weights)

    # Free up space after initialized
    del asr_brain, weights
    gc.collect()
    torch.cuda.empty_cache()
    return pre_trained