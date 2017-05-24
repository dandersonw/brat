#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import sys
import os.path
import spacy
import itertools
import glob
import re
from sys import path as sys_path

# this seems to be necessary for annotations to find its config
sys_path.append(os.path.join(os.path.dirname(__file__), '..'))
try:
    import annotation
except ImportError:
    # Guessing that we might be in the brat tools/ directory ...
    sys_path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    import annotation

NLP = spacy.load("en")


class EnhancedAnnotatedDoc:
    def __init__(self, text_annotation):
        self.brat_annotation = text_annotation
        first_shot = NLP(text_annotation.get_document_text())
        required_boundaries = self._get_entity_boundaries_for_tokenization()
        self.spacy_doc = self._impose_token_boundaries(first_shot, required_boundaries)
        self.entities = [Entity(e, self) for e in text_annotation.get_entities()]

    def __getitem__(self, key):
        return self.spacy_doc[key]

    def __len__(self):
        return self.spacy_doc.__len__()

    def _impose_token_boundaries(self, spacy_doc, boundaries):
        b_idx = 0
        imposed_tokens = []
        for t in spacy_doc:
            start = t.idx
            end = start + len(t)
            splits = [0]
            while b_idx < len(boundaries) and boundaries[b_idx] < end:
                if boundaries[b_idx] > start:
                    splits.append(boundaries[b_idx] - start)
                b_idx += 1
            splits.append(end)
            result_tokens = []
            for i in xrange(len(splits) - 1):
                result_tokens.append([t.text[splits[i]: splits[i+1]], False])
            result_tokens[-1][1] = len(t.whitespace_) > 0
            imposed_tokens += [tuple(token) for token in result_tokens]
        return spacy.tokens.Doc(spacy_doc.vocab, orths_and_spaces=imposed_tokens)

    def _get_entity_boundaries_for_tokenization(self):
        spans = set(
            itertools.chain.from_iterable(
                [e.spans for e in self.brat_annotation.get_entities()]))
        return sorted(set(itertools.chain.from_iterable(spans)))


class Entity:
    """Wrapper for brat annotation. Spans are in tokens."""
    def __init__(self, entity_annotation, parent_doc):
        self.entity_annotation = entity_annotation
        self.parent_doc = parent_doc
        self.spans = []
        print entity_annotation
        for span in entity_annotation.spans:
            self.spans.append((get_token_starting_at_char_offset(parent_doc, span[0]).i,
                               get_token_ending_at_char_offset(parent_doc, span[1]).i + 1))


def get_docs(*paths):
    found_paths = []
    extensions = re.compile(r"\.(txt|ann)$")
    for path in paths:
        if os.path.isdir(path):
            # Don't recur, just check one level down
            children = [f for f in glob.glob(os.path.join(path, "*")) if extensions.search(f)]
            if not children:
                sys.stderr.write("No annotation files found in {}\n".format(path))
            identifiers = [child[:-4] for child in children]
            found_paths += identifiers
        else:
            if extensions.search(path):
                found_paths.append(path[:-4])
            else:
                found_paths.append(path)

    result = []
    for path in found_paths:
        print path
        text_annotation = annotation.TextAnnotations(path)
        result.append(EnhancedAnnotatedDoc(text_annotation))
    return result


def get_token_starting_at_char_offset(doc, offset):
    l = 0
    r = len(doc)
    while r - l > 1:
        mid = (l + r) / 2
        if doc[mid].idx > offset:
            r = mid
        else:
            l = mid

    if doc[l].idx == offset:
        return doc[l]
    else:
        return None


def get_token_ending_at_char_offset(doc, offset):
    l = 0
    r = len(doc)
    while r - l > 1:
        mid = (l + r) / 2
        if doc[mid].idx + len(doc[mid]) > offset:
            r = mid
        else:
            l = mid

    if doc[l].idx + len(doc[l]) == offset:
        return doc[l]
    else:
        return None