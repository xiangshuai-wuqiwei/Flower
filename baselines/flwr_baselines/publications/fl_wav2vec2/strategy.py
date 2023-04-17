import gc
from typing import Optional

import flwr as fl
import torch
from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays
from flwr.server.strategy.aggregate import aggregate


class CustomFedAvg(fl.server.strategy.FedAvg):
    def __init__(self, *args, weight_strategy, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.weight_strategy = weight_strategy

    def aggregate_fit(
        self,
        results,
        failures,
    ) -> Optional[fl.common.NDArrays]:
        if not results:
            return None
        # Do not aggregate if there are failures and failures are not accepted
        if not self.accept_failures and failures:
            return None
        # Convert results
        key_name = "train_loss" if self.weight_strategy == "loss" else "wer"
        weights = None

        # Define ratio merge
        if self.weight_strategy == "num":
            weights_results = [
                (parameters_to_ndarrays(fit_res.parameters), fit_res.num_examples)
                for client, fit_res in results
            ]
            weights = aggregate(weights_results)

        else:
            weights_results = [
                (parameters_to_ndarrays(fit_res.parameters), fit_res.metrics[key_name])
                for _, fit_res in results
            ]
            weights = aggregate(weights_results)

        # Free memory for next round
        del results, weights_results
        torch.cuda.empty_cache()
        gc.collect()
        return ndarrays_to_parameters(weights), {}