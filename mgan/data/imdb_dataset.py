import os
import torch
from torch.utils.data import Dataset
from torch.nn.utils.rnn import pad_sequence
from fairseq.data.dictionary import Dictionary
from tqdm import tqdm

class IMDbDataset(Dataset):
    def __init__(self, path):
        self.path = path
        self.precompute()

    def precompute(self):
        self.sample_files = []
        dirs = ['pos', 'neg', 'unsup']
        for _dir in dirs:
            path = os.path.join(self.path, _dir)
            for root, dirs, files in os.walk(path, topdown=False):
               for name in files:
                   fpath = os.path.join(root, name)
                   self.sample_files.append(fpath)

        self.length = len(self.sample_files)

    def __len__(self):
        return self.length

    def __getitem__(self, idx):
        fpath = self.sample_files[idx]
        contents = open(fpath).read()
        ignores = ['<br>', '<br/>', '<br />']
        for ignore in ignores:
            contents = contents.replace(ignore, '')
        return contents

class TensorIMDbDataset(IMDbDataset):
    def __init__(self, path, preprocess, truncate=40):
        super().__init__(path)
        self.preprocess = preprocess
        self.truncate = truncate
        self.build_vocab()

    def build_vocab(self, rebuild=False):
        vocab_path = os.path.join(self.path, 'vocab.pt')
        if os.path.exists(vocab_path) and not rebuild:
            self.vocab = Dictionary.load(vocab_path)
        else:
            self.rebuild_vocab()
    
    def rebuild_vocab(self):
        vocab_path = os.path.join(self.path, 'vocab.pt')
        self.vocab = Dictionary()
        self.vocab.add_symbol(self.preprocess.mask.mask_token)
        for i in tqdm(range(self.length), desc='build-vocab'):
            contents = super().__getitem__(i)
            tokens = self.preprocess(contents, mask=False)
            tokens, token_count = self._truncate(tokens)
            for token in tokens:
                self.vocab.add_symbol(token)

        self.vocab.save(vocab_path)

    def _truncate(self, tokens):
        truncate = min(len(tokens), self.truncate)
        tokens = tokens[:truncate]
        token_count = len(tokens)
        while len(tokens) < self.truncate:
            tokens.append(self.vocab.pad())
        return (tokens, token_count)


    def __getitem__(self, idx):
        contents = super().__getitem__(idx)
        tgt, tgt_length = self.Tensor_idxs(contents, masked=False)
        src, src_length  = self.Tensor_idxs(contents, masked=True)
        return (src, src_length, tgt, tgt_length)
    
    def Tensor_idxs(self, contents, masked=True):
        tokens = self.preprocess(contents, mask=masked)
        tokens, token_count = self._truncate(tokens)
        idxs = []
        for token in tokens:
            idxs.append(self.vocab.index(token))
        return (torch.LongTensor(idxs), token_count)

    @staticmethod
    def collate(samples):
        # TODO: Implement Collate
        srcs, src_lengths, tgts, tgt_lengths = list(zip(*samples))
        srcs = pad_sequence(srcs)
        tgts = pad_sequence(tgts)
        return (srcs, src_lengths, tgts, tgt_lengths)

