#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codec2ast as ast
import re
import json


class Codec():
    """
    Parses codec and constructs AST
    """

    _builtin_emitters = ['DEC', 'HEX', 'NOP', 'IDENTITY']
    _keywords = ['TARGET', 'RULES', 'DEFAULT-EMITTER']
    _single_char_regex = r'^.$'
    _unicode_form_regex = r'^(?:u|U)\+([0-9a-fA-F]{6}|[0-9a-fA-F]{4})$'
    _range_regex = r'\(((?:u|U)\+(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{4})|.)-((?:u|U)\+(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{4})|.)\)'

    class Builtin(ast.BuiltinEmitter):
        """ extends BuiltinEmitter to check that emitters are actually builtin """

        def isBuiltin(self, name):
            return (name in Codec._builtin_emitters)

    def __init__(self, codec):
        self.codec = codec

    @property
    def codec(self):
        """ the codec object constructed from .c2e file """
        return self._codec

    @codec.setter
    def codec(self, codec):
        self._codec = codec

        self._default_emitter = self.codec['DEFAULT-EMITTER'] if 'DEFAULT-EMITTER' in codec else None
        self._rules = self.codec['RULES']
        self._target = self.codec['TARGET']

        self._userdefined_emitters = []
        for emitter in (emitter for emitter in self.codec if emitter not in self._keywords):
            self._userdefined_emitters.append(emitter)

        def parseGuard(guard):
            rm = re.match(self._single_char_regex, guard, re.DOTALL)
            if rm:
                return ast.BinOp(ast.BinOp.OPS.eq, ast.Candidate(), ast.Codepoint(guard))

            rm = re.match(self._unicode_form_regex, guard)
            if rm:
                return ast.BinOp(ast.BinOp.OPS.eq, ast.Candidate(), ast.Codepoint(chr(int(rm.group(1), 16))))

            rm = re.match(self._range_regex, guard, re.DOTALL)
            if rm:
                min = rm.group(1)
                max = rm.group(2)

                rmu = re.match(self._unicode_form_regex, min)
                if rmu:
                    min = chr(int(rmu.group(1), 16))

                rmu = re.match(self._unicode_form_regex, max)
                if rmu:
                    max = chr(int(rmu.group(1), 16))

                # sanity check
                assert min <= max, "the codepoint on the left of a range must be less-than-or-equal-to the codepoint on the right"
                cond1 = ast.BinOp(ast.BinOp.OPS.gte, ast.Candidate(), ast.Codepoint(min))
                cond2 = ast.BinOp(ast.BinOp.OPS.lte, ast.Candidate(), ast.Codepoint(max))
                return ast.BinOp(ast.BinOp.OPS.land, cond1, cond2)

        def parseEmitter(emitter):

            if type(emitter) is dict:
                if "emitter" in emitter:
                    em = emitter["emitter"]
                    if em in self._userdefined_emitters:

                        emitter_list = [parseEmitter(x) for x in self.codec[em]]
                        return ast.EmitterList(*emitter_list)
                    else:
                        return Codec.Builtin(em)
                else:
                    raise ValueError("the key \"emitter\" is not in dict")
            elif type(emitter) is str:
                return ast.ConstantEmitter(emitter)
            else:
                raise ValueError("that is not an emitter")

        def parseRule(rule):
            for guard, emitter in iter(rule.items()):
                return parseGuard(guard), parseEmitter(emitter)

        # build AST
        self._root = current = ast.If()
        for rule in self._rules:
            current.condition, current.iftrue = parseRule(rule)
            current.iffalse = ast.If()
            current = current.iffalse

        current.condition = ast.Bool.true
        if self._default_emitter:
            current.iftrue = parseEmitter(self._default_emitter)

    @property
    def emitters(self):
        """ returns list of containing builtin emitters and user-defined emitters"""
        return self._builtin_emitters + self._userdefined_emitters

    @property
    def target(self):
        """ returns string with the target of the codec"""
        return self._target

    @property
    def ast(self):
        """ returns the abstract syntax tree generated after parsing codec"""
        return self._root

    def __str__(self):
        return str(self.codec)


class Encoder:

    def __init__(self):
        self._codecs = []
        self._targets = []

    @property
    def codecs(self):
        return self._codecs

    def add(self, codec):
        if isinstance(codec, Codec):
            if codec.target not in self._targets:
                self._targets.append(codec.target)
                self._codecs.append(codec)
            else:
                raise ValueError('a codec with target={} already exists in this encoder'.format(codec.target))
        else:
            raise AttributeError


def parseCodec(codec_filename):
    """ Parse codec files to object """
    # TODO: add schema validation
    with open(codec_filename, 'r') as f:
        codec = json.loads(f.read())
    return Codec(codec)
