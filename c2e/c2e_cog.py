#!/usr/bin/env python
# -*- coding: utf-8 -*-

from cogapp import Cog
import io
import imp
import sys

from codec2ast import AstFormatter


class C2Ecog(Cog):
    ''' Cog wrapper that capture output '''

    def __init__(self, encoder=None, codec=None, codec_template=None, class_name=None, suffix=None):
        super().__init__()

        self.MARKERS = '[[[C2E ]]] [[[END]]]'
        self.SUFFIX = '  // C2E'

        self.installC2eModule()
        self.C2Emodule.fmt = AstFormatter()
        self.C2Emodule.C2Ecog = C2Ecog
        if encoder:
            self.C2Emodule.encoder = encoder
        if codec:
            self.C2Emodule.codec = codec
        if codec_template:
            self.C2Emodule.codec_template = codec_template
        if class_name:
            self.C2Emodule.class_name = class_name
        self.cogmodule.codec_cog = C2Ecog
        if suffix is not None:
            self.SUFFIX = suffix

    def installC2eModule(self):
        self.C2Emodule = imp.new_module('c2e')
        self.C2Emodule.path = []
        sys.modules['c2e'] = self.C2Emodule

    def __call__(self, template_path):
        self.stdout = io.StringIO()
        cog_args = ['', '--markers', self.MARKERS, '-s', self.SUFFIX, template_path]
        self.main(cog_args)
        return self.stdout.getvalue()

    # def __str__(self):
    #     return self.stdout.getvalue()
