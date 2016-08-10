#!/usr/bin/env python
# -*- coding: utf-8 -*-


from abc import ABCMeta, abstractmethod
import unicodedata
from collections import deque

from enum import Enum, EnumMeta, unique
from functools import total_ordering


class AstNode(metaclass=ABCMeta):
    """ base class of all AST nodes """

    # @abstractmethod
    # def __init__(self):
    #     pass

    @property
    @abstractmethod
    def children(self):
        """ Subclasses must override this method and return a tuple of children """
        return ()               # return empty tuple (ie no children)


@total_ordering
class Codepoint(AstNode):
    """ AST Node for unicode codepoint """

    def __init__(self, cp):
        self.codepoint = cp

    @property
    def codepoint(self):
        return self._codepoint

    @codepoint.setter
    def codepoint(self, cp):

        if type(cp) is int:
            self._codepoint = chr(cp)
        elif type(cp) is str:
            if len(cp) == 1:
                self._codepoint = cp
            else:
                self._codepoint = unicodedata.lookup(cp)
        else:
            raise AttributeError('not an int, chr, unicode name')

    @property
    def children(self):
        return super().children

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        else:
            return self.codepoint == other.codepoint

    def __lt__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        else:
            return self.codepoint < other.codepoint


class Candidate(AstNode):

    def __init__(self):
        super().__init__()

    @property
    def children(self):
        return super().children


class Guard:
    """ a mixin used for checking if AstNode is a guard """
    pass


class BinOp(AstNode, Guard):
    """
    AST Node for Binary Operations

    contains enum of binary operations
    """

    OPS = Enum('OPS', 'land lor eq lt gt lte gte')  # land: logiacl and, lor: logical or

    def __init__(self, operation, operand1=None, operand2=None):
        self.operation = operation
        self.operand1 = operand1
        self.operand2 = operand2

    @property
    def operation(self):
        return self._operation

    @operation.setter
    def operation(self, op):
        if op in BinOp.OPS:
            self._operation = op
        else:
            raise AttributeError('operation must be in BinOP.OPS')

    @property
    def children(self):
        return (self.operand1, self.operand2)


class BoolMeta(ABCMeta, EnumMeta):
    """ metaclass for resolving metaclass conflict between ABCMeta and EnumMeta """
    pass


@unique
class Bool(AstNode, Guard, Enum, metaclass=BoolMeta):

    true = True
    false = False


class Emitter:
    """ a mixin used for checking if AstNode is an emitter """
    pass


class Nop(AstNode, Emitter):

    def __init__(self):
        super().__init__()

    @property
    def children(self):
        return super().children


class BuiltinEmitter(AstNode, Emitter, metaclass=ABCMeta):
    """ abstract AST node for representing a builtin emitter """

    def __init__(self, name):
        self.builtin = name

    @property
    def builtin(self):
        return self._builtin

    @builtin.setter
    def builtin(self, name):
        if type(name) is str:
            if self.isBuiltin(name):
                self._builtin = name
            else:
                raise ValueError('That is not a builtin')
        else:
            raise AttributeError('Builtin emitter name must be a string')

    @abstractmethod
    def isBuiltin(self, name):
        pass

    @property
    def children(self):
        return super().children


class ConstantEmitter(AstNode, Emitter):

    def __init__(self, s):
        self.string = s

    @property
    def string(self):
        return self._string

    @string.setter
    def string(self, s):
        if type(s) is str:
            self._string = s
        else:
            raise AttributeError('Constant emitters take a string')

    @property
    def children(self):
        return super().children


class EmitterList(AstNode, Emitter):

    def __init__(self, *emitters):
        self.emitters = emitters

    @property
    def emitters(self):
        return self._emitters

    @emitters.setter
    def emitters(self, emitters):
        for e in emitters:
            if not isinstance(e, Emitter):
                raise AttributeError('EmitterList can only contain Emitters')
        self._emitters = emitters

    @property
    def children(self):
        return tuple(self.emitters)


class If(AstNode):

    def __init__(self, condition=Bool.false, iftrue=Nop(), iffalse=Nop()):
        self.condition = condition
        self.iftrue = iftrue
        self.iffalse = iffalse

    @property
    def condition(self):
        return self._condition

    @condition.setter
    def condition(self, cond):
        if isinstance(cond, Guard):
            self._condition = cond
        else:
            raise AttributeError('condition must be instance of AstNode or enum in Bool')

    @property
    def iftrue(self):
        return self._iftrue

    @iftrue.setter
    def iftrue(self, ift):
        if isinstance(ift, AstNode):
            self._iftrue = ift
        else:
            raise AttributeError('iftrue must be instance of AstNode')

    @property
    def iffalse(self):
        return self._iffalse

    @iffalse.setter
    def iffalse(self, iff):
        if isinstance(iff, AstNode):
            self._iffalse = iff
        else:
            raise AttributeError('iffalse must be instance of AstNode or enum in Bool')

    @property
    def children(self):
        return (self.condition, self.iftrue, self.iffalse)


class NodeVisitor:
    """ This class adapted from python's ast.NodeVisitor class in the ast module """

    def visit(self, node):
        """ taken verbatim from python's ast.NodeVisitor.visit """
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        if isinstance(node, AstNode):
            for child in node.children:
                self.visit(child)


class AstFormatter(NodeVisitor):

    def __init__(self):
        # self._out = deque()
        self._format_strings = dict()
        self.escape_func = lambda c: c if c != '\\' else '\\\\'

    @property
    def out(self):
        return ''.join(self._out)

    def format(self, node):
        return self.visit(node)

    # def append(self, s):
    #     self._out.append(s)

    def getFstring(self, node):
        if isinstance(node, BinOp):
            return self._format_strings.get(node.operation.name, '')
        elif isinstance(node, Bool):
            return self._format_strings.get(str(node.value).lower(), '')
        else:
            return self._format_strings[node.__class__.__name__]

    def visit_If(self, node):
        format_string = self.getFstring(node)
        return format_string.format(condition=self.visit(node.condition), iftrue=self.visit(node.iftrue), iffalse=self.visit(node.iffalse))

    def visit_BinOp(self, node):
        format_string = self.getFstring(node)
        return format_string.format(operand1=self.visit(node.operand1), operand2=self.visit(node.operand2))

    def visit_Candidate(self, node):
        format_string = self.getFstring(node)
        return format_string

    def visit_Codepoint(self, node):
        # format_string = self.escape_func(self.getFstring(node))
        format_string = self.getFstring(node)
        return format_string.format(codepoint=ord(node.codepoint))

    def visit_Bool(self, node):
        format_string = self.getFstring(node)
        return format_string

    def visit_Nop(self, node):
        format_string = self.getFstring(node)
        return format_string

    def visit_Builtin(self, node):
        format_string = self.getFstring(node)
        return format_string.format(builtin=node.builtin)

    def visit_ConstantEmitter(self, node):
        format_string = self.getFstring(node)
        buff = []
        for c in node.string:
            buff.append(self.escape_func(c))
        return format_string.format(''.join(buff))

    def visit_EmitterList(self, node):
        s = []
        for emitter in node.emitters:
            s.append(self.visit(emitter))
        return ''.join(s)

    def __setattr__(self, name, value):
        if name == '_out' or name == '_format_strings' or name == 'escape_func':
            super(NodeVisitor, self).__setattr__(name, value)
        else:
            self._format_strings[name] = value

    def __str__(self):
        return str(self._format_strings)


def walk(an):

    if isinstance(an, AstNode):
        yield(an)
        for child in an.children:
            yield from walk(child)
    else:
        raise TypeError("must be instance of AstNode")
