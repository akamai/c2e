#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2016, Akamai Technologies
# Author: Daniel Garcia

"""
Usage:
 c2e [options]
 c2e -h | --help
 c2e --version

Options:
 -h, --help                     Print this help
 --version                      Show version number
 -v, --verbose                  Print verbose output
 -d, --dry                      Don't produce source code
 -C DIR, --codec-dir DIR        Directory of codecs [default: ./codecs]
 -T DIR, --template-dir DIR     Directory of templates [default: ./templates]
 -l LANG, --language LANG       Language to output in

c2e will search DIR for codec files ending in .c2e

CODECS:
The top object TARGET defines the targt of a codec (html, css, etc)

The main top object is RULES, it contains an ordered list of rules

A rule is an object with a left part (called a guard) and
a right part (called an emitter)

A character in a string that is being encoded is called a candidate
If a candidate matches a guard then the candidate is passed to the
corresponding to emitter which produces characters for the output string

GUARDS can be specified in two ways:
- a single character which will match that character
- or a range of characters which will match any character within the range
  inclusively. Ranges have the form (a-z) where a and z are characters

Characters (codepoints really) can be specified in three ways:
- by literal character
- by codepoint in the form U+HHHH if the codepoint is in the
  basic multilingual plane
- or by codepoint in the form U+HHHHHH
where H are hex digits

for example:
   "a", "U+0061", and "U+000061" are equivalent

EMITTERS can be specified in two ways:
- a string literal which will produce that string
- a named emitter (in the form {emitter: "EMITTER-NAME"})

c2e provides four builtin named emitters:
- DEC: which emits the decimal representation of a codepoint
- HEX: which emits the hexadecimal representation of a codepoint
- IDENTITY: which emits its input
- NOP: which emits nothing

New emitters can be defined as an ordered list of other emitters
where the candidate will be passed to each emitter and the
results concatenated

All top objects besides TARGET, RULES, and DEFAULT-EMITTER
are assumed to be emitter definitions

DEFAULT-EMITTER is a special emitter that will be used when
a candidate does not match a guard

If not defined DEFAULT-EMITTER defaults to the NOP emitter
"""

import os
import time
import re
import unicodedata

from docopt import docopt
from clint.textui import progress, colored, indent, puts, columns, STDOUT, STDERR

from c2e_cog import C2Ecog
from c2e_codec import *
from codec2ast import AstFormatter


class ast2str(ast.NodeVisitor):

    def __init__(self, node):
        self.out = ''
        self.indent = 0
        self.visit(node)

    def visit_If(self, node):
        if len(self.out) > 0:
            self.out += '\n'
        self.out += ' '*(self.indent-1) + colored.cyan('⤷ ') if self.indent != 0 else ''
        self.indent += 1
        self.out += colored.blue('IF (')
        self.visit(node.condition)
        self.out += colored.blue(') THEN ')
        self.visit(node.iftrue)
        self.out += colored.blue(' ELSE ')
        self.visit(node.iffalse)

    def visit_Candidate(self, node):
        self.out += '{}'.format(colored.red('α'))

    def visit_Codepoint(self, node):
        cp = node.codepoint
        if re.match(r'\s', cp):
            if unicodedata.name(cp, False):
                self.out += '\'{}\''.format(colored.white(unicodedata.name(cp)))
            else:
                self.out += CODEPOINT_FORMAT.format(ord(cp))

        elif ord(cp) > 255:
            self.out += CODEPOINT_FORMAT.format(ord(cp))
        else:
            self.out += '"{}"'.format(colored.white(cp))

    def visit_Bool(self, node):
        if node.value:
            self.out += colored.green('True')
        else:
            self.out += colored.red('False')

    def visit_Nop(self, node):
        self.out += colored.red('nop')

    def visit_Builtin(self, node):
        self.out += '{}({})'.format(colored.yellow(node.builtin), colored.red('α'))

    def visit_ConstantEmitter(self, node):
        self.out += '{}({} {} \"{}\")'.format(colored.yellow('λ'), colored.red('α'), colored.yellow('↦'), colored.white(node.string))

    def visit_EmitterList(self, node):
        self.out += '['
        for index, e in enumerate(node.emitters):
            if index != 0:
                self.out += colored.yellow(' ∙ ')
            self.visit(e)
        self.out += ']'

    def visit_BinOp(self, node):
        self.visit(node.operand1)

        if node.operation is ast.BinOp.OPS.land:
            self.out += ' {} '.format(colored.yellow('∧'))
        elif node.operation is ast.BinOp.OPS.lor:
            self.out += ' {} '.format(colored.yellow('∨'))
        elif node.operation is ast.BinOp.OPS.eq:
            self.out += ' {} '.format(colored.yellow('=='))
        elif node.operation is ast.BinOp.OPS.lt:
            self.out += ' {} '.format(colored.yellow('<'))
        elif node.operation is ast.BinOp.OPS.gt:
            self.out += ' {} '.format(colored.yellow('>'))
        elif node.operation is ast.BinOp.OPS.lte:
            self.out += ' {} '.format(colored.yellow('≤'))
        elif node.operation is ast.BinOp.OPS.gte:
                self.out += ' {} '.format(colored.yellow('≥'))

        self.visit(node.operand2)

    def __str__(self):
        return self.out


def main():

    CODEC_EXT = '.c2e'
    C2E_VERSION = 'C2E 0.1'

    # get command line arguements
    global args, verbose
    args = docopt(__doc__, version=C2E_VERSION, options_first=True)
    verbose = args['--verbose']

    # print(args)
    # print(); print()

    # verify --codec-dir and --template-dir exist
    if not os.path.isdir(args['--codec-dir']):
        puts('Error: {dir} is not a directory'.format(dir=colored.red(args['--codec-dir'])), stream=STDERR)
        exit(1)

    if not os.path.isdir(args['--template-dir']):
        puts('Error: {dir} is not a directory'.format(dir=colored.red(args['--template-dir'])), stream=STDERR)
        exit(1)

    # verify output language
    if args['--language']:
        path = '{}/{}'.format(args['--template-dir'], args['--language'])
        if not os.path.isdir(path):
            puts('Error: the template dir ({dir}) has no subdirectory named {lang}'.format(dir=colored.red(args['--template-dir']), lang=colored.red(args['--language']), stream=STDERR))
            exit(1)            

    # enumerate codecs
    codec_paths = []

    with progress.Bar(label=colored.green('traversing {}:  '.format(args['--codec-dir'])), expected_size=len(os.listdir(args['--codec-dir'])), hide=not verbose) as bar:
        for i, codec_file in enumerate(os.listdir(args['--codec-dir'])):
            if verbose: time.sleep(.1)
            bar.show(i+1)
            path = '{0}/{1}'.format(args['--codec-dir'], codec_file)
            if codec_file.endswith(CODEC_EXT) and os.path.isfile(path):
                codec_paths.append(path)

    if verbose:
        puts(colored.green('\nfound {} codec(s)'.format(len(codec_paths))), stream=STDERR)
        with indent(3, quote=colored.blue(' •')):
            for path in codec_paths:
                puts(path, stream=STDERR)

    # construct encoder
    encoder = Encoder()
    if verbose:
        puts(colored.green('\nparsing codecs:'), stream=STDERR)

    for path in codec_paths:
        c = parseCodec(path)
        if verbose:
            puts('{} {} {}'.format(colored.blue(' •'), path, colored.green('✔') if c else colored.red('✘')), stream=STDERR)
        if verbose and c:
            with indent(3):
                puts(colored.green('target: ') + c.target, stream=STDERR)
                puts(colored.green('emitters: '), stream=STDERR)
                with indent(3):
                    for e in c.emitters:
                        puts('{}({})'.format(colored.yellow(e), colored.red('α')), stream=STDERR)
                puts(colored.green('syntax tree: '), stream=STDERR)
                with indent(4, quote=colored.cyan(" ┆")):
                    puts(str(ast2str(c.ast)), stream=STDERR)
                puts('', stream=STDERR)
        encoder.add(c)

    # cog = C2Ecog(encoder, codec_template='templates/Java/codec.template')
    # puts(cog('templates/Java/Encode.java'))
    if not args['--dry']:
        cog = C2Ecog(encoder)
        puts(cog('templates/Java/Encode.java'))


if __name__ == '__main__':
    main()
