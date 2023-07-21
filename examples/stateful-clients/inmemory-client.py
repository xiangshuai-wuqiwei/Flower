
from time import time
from collections import OrderedDict

import flwr as fl
import torch

from model_and_dataset import Net, load_data, train, test

DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


# #############################################################################
# Run Federated Learning with Flower using an In-memory stateful client
# #############################################################################

# Load model and data (simple CNN, CIFAR-10)
net = Net().to(DEVICE)
trainloader, testloader = load_data()


# Define Flower client using In-memory state.
class FlowerClient(fl.client.NumPyClient):

    state = fl.client.InMemoryClientState()

    def get_parameters(self, config):
        return [val.cpu().numpy() for _, val in net.state_dict().items()]

    def set_parameters(self, parameters):
        params_dict = zip(net.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        net.load_state_dict(state_dict, strict=True)

    def fit(self, parameters, config):
        state = self.state.fetch()
        print(f"Current state: {state}")
        t_start = time()
        self.set_parameters(parameters)
        train(net, trainloader, epochs=1)
        t_end = time() - t_start
        self.state.update({'fit_time': t_end})
        return self.get_parameters(config={}), len(trainloader.dataset), {}

    def evaluate(self, parameters, config):
        self.set_parameters(parameters)
        loss, accuracy = test(net, testloader)
        return loss, len(testloader.dataset), {"accuracy": accuracy}


# Start Flower client
fl.client.start_numpy_client(
    server_address="127.0.0.1:8080",
    client=FlowerClient(),
)