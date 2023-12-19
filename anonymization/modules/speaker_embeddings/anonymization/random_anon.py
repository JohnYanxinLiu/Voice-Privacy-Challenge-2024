import json
from pathlib import Path
import torch
from os import PathLike
from typing import Union
import numpy as np

from .base_anon import BaseAnonymizer
from ..speaker_embeddings import SpeakerEmbeddings


class RandomAnonymizer(BaseAnonymizer):
    """
        An anonymizer module that generates random vectors for each speaker or
        utterance. The vectors are generated by sampling from a uniform
        distribution for each dimension. The range of the uniform distribution
        is determined by the minimum and maximum values of the original
        speaker/utterance vectors.
    """
    def __init__(
        self,
        device: Union[str, torch.device, int, None],
        vec_type: str = "xvector",
        model_name: str = None,
        in_scale: bool = False,
        stats_per_dim_path: Union[str, PathLike] =None,
        **kwargs,
    ):
        """
        Args:
            device: The computation device to use for the anonymization.
            vec_type: The type of the speaker embedding to anonymize. Valid
                values are 'xvector', 'style-embed', 'ecapa'
            model_name: The name of the model used for the anonymization.
                Defaults to 'random_{vec_type}'.
            in_scale: If True, the anonymized vectors will be in the same
                scale as the original vectors. Otherwise, the vectors will be
                sampled from a uniform distribution with the same range for
                each dimension.
            stats_per_dim_path: The path to the json file containing the
                minimum and maximum values for each dimension of the original
                vectors. If None, the stats will be loaded from the file
                'stats_per_dim.json'.
        """
        super().__init__(vec_type=vec_type, device=device)

        self.model_name = model_name if model_name else f"random_{vec_type}"

        if in_scale:
            self.stats_per_dim_path = stats_per_dim_path
        else:
            self.stats_per_dim_path = None
            self._scaling_ranges = None

    @property
    def scaling_ranges(self):
        # defer loading of stats until they are first needed
        # required after anonymizer initialization is delegated to HyperPyYAML
        if self.stats_per_dim_path is not None:
            self._scaling_ranges = self._load_scaling_ranges(
                stats_per_dim_path=self.stats_per_dim_path
            )
            self.stats_per_dim_path = None
        return self._scaling_ranges

    def anonymize_embeddings(self, speaker_embeddings, emb_level="spk"):
        """
            Anonymize speaker embeddings using random vectors.
        Args:
            speaker_embeddings: [n_embeddings, n_channels] Speaker
                embeddings to be anonymized.
            emb_level: Embedding level ('spk' for speaker level or 'utt' for
                utterance level).
        """
        if self.scaling_ranges:
            print("Anonymize vectors in scale!")
            return self._anonymize_data_in_scale(speaker_embeddings)
        else:
            identifiers = []
            anon_vectors = []
            speakers = speaker_embeddings.original_speakers
            genders = speaker_embeddings.genders
            for identifier, vector in speaker_embeddings:
                mask = (
                    torch.zeros(vector.shape[0])
                    .float()
                    .random_(-40, 40)
                    .to(self.device)
                )
                anon_vec = vector * mask
                identifiers.append(identifier)
                anon_vectors.append(anon_vec)

            anon_embeddings = SpeakerEmbeddings(
                vec_type=self.vec_type, device=self.device, emb_level=emb_level
            )
            anon_embeddings.set_vectors(
                identifiers=identifiers,
                vectors=torch.stack(anon_vectors, dim=0),
                genders=genders,
                speakers=speakers,
            )

            return anon_embeddings

    def _load_scaling_ranges(self, stats_per_dim_path):
        if stats_per_dim_path is None:
            stats_per_dim_path = Path("stats_per_dim.json")

        with open(stats_per_dim_path) as f:
            dim_ranges = json.load(f)
            return [
                (v["min"], v["max"])
                for k, v in sorted(dim_ranges.items(), key=lambda x: int(x[0]))
            ]

    def _anonymize_data_in_scale(self, speaker_embeddings):
        identifiers = []
        anon_vectors = []
        speakers = speaker_embeddings.original_speakers
        genders = speaker_embeddings.genders

        for identifier, vector in speaker_embeddings:
            anon_vec = torch.tensor(
                [np.random.uniform(*dim_range) for dim_range in self.scaling_ranges]
            ).to(self.device)
            identifiers.append(identifier)
            anon_vectors.append(anon_vec)

        anon_embeddings = SpeakerEmbeddings(vec_type=self.vec_type, device=self.device)
        anon_embeddings.set_vectors(
            identifiers=identifiers,
            vectors=torch.stack(anon_vectors, dim=0),
            genders=genders,
            speakers=speakers,
        )

        return anon_embeddings
