import functools

import torch
import torch.nn.functional as F
import pytorch_lightning as pl

import penne
import argparse
import os
import matplotlib.pyplot as plt

# import pathlib


###############################################################################
# Model definition
###############################################################################

# TODO - Convert the Crepe model (below) to this Pytorch lightning template and
#        complete the template TODOs. You only need to convert the "full"
#        model.

class Model(pl.LightningModule):
    """PyTorch Lightning model definition"""

    # TODO - add hyperparameters as input args
    def __init__(self, name='default'):
        super().__init__()

        self.epsilon = 0.0010000000474974513
        self.learning_rate = 1e-3
        self.momentum = 0.0
        self.name = name

        self.ex_batch = None

        self.best_loss = float('inf')

        # import pdb; pdb.set_trace()

        # Save hyperparameters with checkpoints
        # self.save_hyperparameters()

        in_channels = [1, 1024, 128, 128, 128, 256]
        out_channels = [1024, 128, 128, 128, 256, 512]
        self.in_features = 2048

        # Shared layer parameters
        kernel_sizes = [(512, 1)] + 5 * [(64, 1)]
        strides = [(4, 1)] + 5 * [(1, 1)]

        # Overload with eps and momentum conversion given by MMdnn
        batch_norm_fn = functools.partial(torch.nn.BatchNorm2d,
                                          eps=self.epsilon,
                                          momentum=self.momentum)

        # Layer definitions
        self.conv1 = torch.nn.Conv2d(
            in_channels=in_channels[0],
            out_channels=out_channels[0],
            kernel_size=kernel_sizes[0],
            stride=strides[0])
        self.conv1_BN = batch_norm_fn(
            num_features=out_channels[0])

        self.conv2 = torch.nn.Conv2d(
            in_channels=in_channels[1],
            out_channels=out_channels[1],
            kernel_size=kernel_sizes[1],
            stride=strides[1])
        self.conv2_BN = batch_norm_fn(
            num_features=out_channels[1])

        self.conv3 = torch.nn.Conv2d(
            in_channels=in_channels[2],
            out_channels=out_channels[2],
            kernel_size=kernel_sizes[2],
            stride=strides[2])
        self.conv3_BN = batch_norm_fn(
            num_features=out_channels[2])

        self.conv4 = torch.nn.Conv2d(
            in_channels=in_channels[3],
            out_channels=out_channels[3],
            kernel_size=kernel_sizes[3],
            stride=strides[3])
        self.conv4_BN = batch_norm_fn(
            num_features=out_channels[3])

        self.conv5 = torch.nn.Conv2d(
            in_channels=in_channels[4],
            out_channels=out_channels[4],
            kernel_size=kernel_sizes[4],
            stride=strides[4])
        self.conv5_BN = batch_norm_fn(
            num_features=out_channels[4])

        self.conv6 = torch.nn.Conv2d(
            in_channels=in_channels[5],
            out_channels=out_channels[5],
            kernel_size=kernel_sizes[5],
            stride=strides[5])
        self.conv6_BN = batch_norm_fn(
            num_features=out_channels[5])

        self.classifier = torch.nn.Linear(
            in_features=self.in_features,
            out_features=penne.PITCH_BINS)

    ###########################################################################
    # Forward pass
    ###########################################################################

    def forward(self, x, embed=False):
        """Perform model inference"""
        # TODO - define model arguments and implement forward pass
        x = self.embed(x)

        if embed:
            return x

        # Forward pass through layer six
        x = self.layer(x, self.conv6, self.conv6_BN)

        # shape=(batch, self.in_features)
        x = x.permute(0, 2, 1, 3).reshape(-1, self.in_features)

        # Compute logits
        return self.classifier(x)
        # return torch.sigmoid(self.classifier(x))

    ###########################################################################
    # PyTorch Lightning - model-specific argparse argument hook
    ###########################################################################

    @staticmethod
    def add_model_specific_args(parent_parser):
        """Add model hyperparameters as argparse arguments"""
        parser = argparse.ArgumentParser(
            parents=[parent_parser], add_help=False)
        # TODO - add hyperparameters as command-line args using
        #        parser.add_argument()
        return parser

    ###########################################################################
    # PyTorch Lightning - step model hooks
    ###########################################################################

    def my_loss(self, y_hat, y):
        # import pdb; pdb.set_trace()
        if penne.LOSS_FUNCTION == 'BCE':
            y = F.one_hot(y, penne.PITCH_BINS)
            # import pdb; pdb.set_trace()
            assert y_hat.shape == y.shape
            return F.binary_cross_entropy_with_logits(y_hat, y.float())
        return F.cross_entropy(y_hat, y)

    def my_acc(self, y_hat, y):
        return y_hat.eq(y).sum().item()/y.numel()

    def training_step(self, batch, index):
        """Performs one step of training"""
        # TODO - implement training step
        x, y = batch
        output = self(x)
        loss = self.my_loss(output, y)
        # y_hat = output.argmax(dim=1)
        # accuracy = self.my_acc(y_hat, y)
        return {"loss": loss}

    def validation_step(self, batch, index):
        """Performs one step of validation"""
        # TODO - implement validation step
        x, y = batch
        output = self(x)
        loss = self.my_loss(output, y)
        return {"loss": loss}

    def test_step(self, batch, index):
        """Performs one step of testing"""
        # OPTIONAL - only implement if you have meaningful objective metrics
        raise NotImplementedError

    def training_epoch_end(self, outputs):
        loss_sum = 0
        for x in outputs:
            loss_sum += x['loss']
        loss_mean = loss_sum / len(outputs)

        self.logger.experiment.add_scalar("Loss/Train", loss_mean, self.current_epoch)

    def validation_epoch_end(self, outputs):
        loss_sum = 0
        for x in outputs:
            loss_sum += x['loss']
        loss_mean = loss_sum / len(outputs)

        self.logger.experiment.add_scalar("Loss/Val", loss_mean, self.current_epoch)

        if loss_mean < self.best_loss and self.current_epoch > 5:
            self.best_loss = loss_mean
            checkpoint_path = penne.CHECKPOINT_DIR.joinpath(self.name, str(self.current_epoch)+'.ckpt')
            self.trainer.save_checkpoint(checkpoint_path)

        if self.current_epoch % 20 == 0:
            if self.ex_batch is None:
                ex_audio, ex_sr = penne.load.audio("/home/caedon/penne/data/MDB/audio_stems/MusicDelta_InTheHalloftheMountainKing_STEM_03.RESYN.wav")  
                self.ex_batch = next(penne.preprocess(ex_audio, ex_sr, penne.HOP_SIZE, device='cuda'))[:1500,:]
                # ex_audio, ex_sr = penne.load.audio("/home/caedon/penne/data/PTDB/MALE/MIC/M03/mic_M03_sa1.wav")
                # self.ex_batch = next(penne.preprocess(ex_audio, ex_sr, penne.HOP_SIZE, device='cuda'))[1000:,:]

            probabilities = penne.infer(self.ex_batch, model=self).cpu()
            probabilities = torch.nn.Softmax(dim=1)(probabilities)
            self.write_posterior_distribution(probabilities)

    def write_posterior_distribution(self, probabilities):
        checkpoint_label = str(self.current_epoch)+'.ckpt'
        fig = plt.figure(figsize=(12, 3))
        plt.imshow(probabilities.detach().numpy().T, origin='lower')
        plt.title(checkpoint_label)
        self.logger.experiment.add_figure(checkpoint_label, fig, global_step=self.current_epoch)

    ###########################################################################
    # PyTorch Lightning - optimizer
    ###########################################################################

    def configure_optimizers(self):
        """Configure optimizer for training"""
        return torch.optim.Adam(self.parameters(), lr=self.learning_rate)

    ###########################################################################
    # Forward pass utilities
    ###########################################################################

    def embed(self, x):
        """Map input audio to pitch embedding"""
        # shape=(batch, 1, 1024, 1)
        x = x[:, None, :, None]

        # Forward pass through first five layers
        x = self.layer(x, self.conv1, self.conv1_BN, (0, 0, 254, 254))
        x = self.layer(x, self.conv2, self.conv2_BN)
        x = self.layer(x, self.conv3, self.conv3_BN)
        x = self.layer(x, self.conv4, self.conv4_BN)
        x = self.layer(x, self.conv5, self.conv5_BN)

        return x

    def layer(self, x, conv, batch_norm, padding=(0, 0, 31, 32)):
        """Forward pass through one layer"""
        x = F.pad(x, padding)
        x = conv(x)
        x = F.relu(x)
        x = batch_norm(x)
        return F.max_pool2d(x, (2, 1), (2, 1))
