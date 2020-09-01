import torch

from pytorch3dunet.embeddings.utils import MeanEmbeddingAnchor, RandomEmbeddingAnchor


class AbstractMaskExtractor:
    def __init__(self, dist_to_mask, combine_masks):
        """
        Base class for extracting the 'fake' masks given the embeddings.

        Args:
            dist_to_mask (Callable): function which converts the distance map to an instance map
            combine_masks (bool): if True combines the instance maps into a single image, otherwise stacks the instance
                maps across a new dimension. WARN: experiments shows that adversarial training works well only with
                when the instance maps are not combined, i.e. combine_masks=False
        """
        self.dist_to_mask = dist_to_mask
        self.combine_masks = combine_masks

    def __call__(self, embeddings, labels=None):
        """
        Computes the instance map given the embeddings tensor (no batch dim) and the optional labels (no batch dim)

        Args:

            embeddings: NxExSPATIAL embedding tensor
            labels: (optional) tensor containing the instance ground truth

        Returns:
            list of instance masks
        """

        fake_masks = []
        # iterate over the batch
        for i, emb in enumerate(embeddings):
            # extract the masks from a single batch instance
            fms = self.extract_masks(emb, labels[i] if labels is not None else None)

        if self.combine_masks and len(fms) > 0:
            fake_mask = torch.zeros_like(fms[0])
            for fm in fms:
                fake_mask += fm
            fake_masks.append(fake_mask)
        else:
            fake_masks.extend(fms)

        if len(fake_masks) == 0:
            return None

        fake_masks = torch.stack(fake_masks).to(embeddings.device)
        return fake_masks

    def extract_masks(self, embeddings, labels=None):
        raise NotImplementedError


class TargetBasedMaskExtractor(AbstractMaskExtractor):
    """
    Extracts the instance masks given the embeddings and the anchor_embeddings_extractor, which extracts the
    anchor embeddings given the target labeling.
    """

    def __init__(self, dist_to_mask, combine_masks, anchor_embeddings_extractor):
        super().__init__(dist_to_mask, combine_masks)
        self.anchor_embeddings_extractor = anchor_embeddings_extractor

    def extract_masks(self, emb, tar=None):
        assert tar is not None

        anchor_embeddings = self.anchor_embeddings_extractor(emb, tar)

        results = []
        for i, anchor_emb in enumerate(anchor_embeddings):
            if i == 0:
                # ignore 0-label
                continue

            # compute distance map; embeddings is ExSPATIAL, anchor_embeddings is ExSINGLETON_SPATIAL, so we can just broadcast
            dist_to_mean = torch.norm(emb - anchor_emb, 'fro', dim=0)
            # convert distance map to instance pmaps
            inst_pmap = self.dist_to_mask(dist_to_mean)
            # add channel dim and save fake masks
            results.append(inst_pmap.unsqueeze(0))

        return results


class TargetMeanMaskExtractor(TargetBasedMaskExtractor):
    def __init__(self, dist_to_mask, combine_masks):
        super().__init__(dist_to_mask, combine_masks, MeanEmbeddingAnchor())


class TargetRandomMaskExtractor(TargetBasedMaskExtractor):
    def __init__(self, dist_to_mask, combine_masks):
        super().__init__(dist_to_mask, combine_masks, RandomEmbeddingAnchor())
