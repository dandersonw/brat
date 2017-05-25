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
        first_shot_len = len(first_shot)
        required_boundaries = self._get_entity_boundaries_for_tokenization()
        self.spacy_doc = self._impose_token_boundaries(first_shot, required_boundaries)
        assert len(self.spacy_doc) >= first_shot_len
        self.entities = [Entity(e, self) for e in text_annotation.get_entities()]
        self.relations = [Relation(r, self) for r in text_annotation.get_relations()]
        self.document_id = os.path.basename(text_annotation.get_document())
        self.annotator_id = os.path.basename(os.path.dirname(text_annotation.get_document()))

    def __getitem__(self, key):
        return self.spacy_doc.__getitem__(key)

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

    def get_entity(self, id):
        return next((e for e in self.entities if e.id == id), None)

    def remove_entity(self, entity):
        self.entities = [e for e in self.entities if e != entity]
        self.brat_annotation.del_annotation(entity.brat_annotation)


class Entity:
    """Wrapper for brat annotation. Spans are in tokens."""
    def __init__(self, brat_annotation, parent_doc):
        self.brat_annotation = brat_annotation
        self.parent_doc = parent_doc
        self.id = brat_annotation.id
        self.type = brat_annotation.type
        self.character_spans = brat_annotation.spans
        self.spans = []
        for span in brat_annotation.spans:
            self.spans.append((get_token_starting_at_char_offset(parent_doc, span[0]).i,
                               get_token_ending_at_char_offset(parent_doc, span[1]).i + 1))

    def same_span(self, other):
        return set(self.character_spans) == set(other.character_spans)

    def overlaps(self, other):
        return any_overlapping_spans(self.brat_annotation, other.brat_annotation)


class Relation:
    def __init__(self, brat_annotation, parent_doc):
        self.brat_annotation = brat_annotation
        self.type = brat_annotation.type
        self.arg1 = parent_doc.get_entity(brat_annotation.arg1)
        self.arg2 = parent_doc.get_entity(brat_annotation.arg2)


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
            found_paths += list(set(identifiers))
        else:
            if extensions.search(path):
                found_paths.append(path[:-4])
            else:
                found_paths.append(path)

    result = [load_doc(p) for p in found_paths]
    return result


def load_doc(identifier):
    return EnhancedAnnotatedDoc(annotation.TextAnnotations(identifier))


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


def find_overlapping(doc):
    return filter(lambda c: any_overlapping_spans(c[0], c[1]),
                  itertools.combinations(doc.get_entities(), 2))


def any_overlapping_spans(a, b):
        for i in a.spans:
            for j in b.spans:
                if j[0] < i[1] and i[0] < j[1]:
                    return True
        return False


# Requires the spans be independent
def spans_to_biluo(spans, total_len):
    # o -> 0, b -> 1, i -> 2, l -> 3, u -> 4
    spans = sorted(spans)
    result = [0] * total_len
    i = 0
    j = 0
    while j < len(spans):
        if i >= total_len:
            print spans
        if i < spans[j][0]:  # o
            result[i] = 0
        elif i == spans[j][0] and (i + 1 < spans[j][1]):  # b
            result[i] = 1
        elif i == spans[j][0]:  # u
            result[i] = 4
            j += 1
        elif i + 1 == spans[j][1]:  # l
            result[i] = 3
            j += 1
        else:  # i
            result[i] = 2
        i += 1
    return result
