# Copyright (c) 2015, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

from __future__ import print_function
import io as StringIO  # should work with 2 and 3

from casing import title
from license import C_LICENSE_COMMENT

class Printer(object):
  def __init__(self):
    self._type_name = None
    # Map concrete type to base class
    self._bases = {}
    # HACK: Defer everything we print so that forward declarations for
    # all classes come first. Avoids having to do 2 passes over the
    # input file.
    self._deferredOutput = StringIO.StringIO()

    self._fields = []

  def start_file(self):
    print(C_LICENSE_COMMENT + '''/** @generated */
#pragma once

#include "AstNode.h"

#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace facebook {
namespace graphql {
namespace ast {

// The parser uses strdup to move from yytext to the heap, so we need
// to use free instead of delete.
struct CDeleter {
  void operator()(const char *p) const { free((void *)p); }
};
''')

  def end_file(self):
    print()
    print(self._deferredOutput.getvalue())
    print('}')
    print('}')
    print('}')

  def _base_class(self, type):
    return self._bases.get(type, 'Node')

  def start_type(self, name):
    self._type_name = name
    base = self._base_class(name)
    # non-deferred!
    print('class {};'.format(name))
    print('class {} : public {} {{'.format(name, base),
          file=self._deferredOutput)
    self._fields = []

  def field(self, type, name, nullable, plural):
    if type == 'OperationKind':
      type = 'string'
    self._fields.append((type, name, nullable, plural))

  def end_type(self, name):
    self._print_fields()
    print(' public:', file=self._deferredOutput)
    self._print_constructor()
    print(file=self._deferredOutput)
    self._print_destructor_prototype()
    print(file=self._deferredOutput)
    self._print_noncopyable()
    print(file=self._deferredOutput)
    self._print_getters()
    print('  void accept(visitor::AstVisitor *visitor) override;',
          file=self._deferredOutput)
    print('};', file=self._deferredOutput)
    print(file=self._deferredOutput)
    print(file=self._deferredOutput)
    self._type_name = None
    self._fields = []

  def _storage_type(self, type):
    if type == 'string':
      return 'std::unique_ptr<const char, CDeleter>'
    elif type == 'boolean':
      return 'bool'
    else:
      return 'std::unique_ptr<{}>'.format(type)

  def _print_fields(self):
    for (type, name, nullable, plural) in self._fields:
      storage_type = self._storage_type(type)
      if plural:
        storage_type = 'std::unique_ptr<std::vector<{}>>'.format(storage_type)
      print('  {} {}_;'.format(storage_type, name),
            file=self._deferredOutput)

  def _ctor_singular_type(self, type):
    if type == 'string':
      return 'const char *'
    elif type == 'boolean':
      return 'bool'
    else:
      return '{} *'.format(type)

  def _ctor_plural_type(self, type):
    return 'std::vector<{}> *'.format(self._storage_type(type))

  def _print_constructor(self):
    print('  explicit {}('.format(self._type_name), file=self._deferredOutput)
    print('      const yy::location &location{}'.format(',' if self._fields else ''),
          file=self._deferredOutput)
    def ctor_arg(type, name, plural):
      if plural:
        ctor_type = self._ctor_plural_type(type)
      else:
        ctor_type = self._ctor_singular_type(type)
      return '      {} {}'.format(ctor_type, name)
    print(',\n'.join(ctor_arg(type, name, plural)
                     for (type, name, nullable, plural) in self._fields),
        file=self._deferredOutput)
    print('  )', file=self._deferredOutput)
    def ctor_init(type, name, plural):
      # Strings are const char *, just pass.
      # Vectors are passed by pointer and we take ownership.
      # Node types are passed in by pointer and we take ownership.
      value = name
      return '    {}_({})'.format(name, value)
    print('  : {}(location){}'.format(self._base_class(self._type_name), ',' if self._fields else ''),
          file=self._deferredOutput)
    print(',\n'.join(ctor_init(type, name, plural)
          for (type, name, nullable, plural) in self._fields),
          file=self._deferredOutput)
    print('  {}', file=self._deferredOutput)

  def _getter_type(self, type, nullable, plural):
    if plural and nullable:
      return 'const std::vector<{}>*'.format(self._storage_type(type))
    elif plural:
      return 'const std::vector<{}>&'.format(self._storage_type(type))

    if type == 'string':
      assert not nullable
      return 'const char *'
    elif type == 'boolean':
      assert not nullable
      return 'bool'
    elif nullable:
      return 'const {}*'.format(type)
    else:
      return 'const {}&'.format(type)

  def _getter_value_to_return(self, raw_value, type, nullable, plural):
    if plural and nullable:
      return raw_value + '.get()'
    elif plural:
      return '*{}'.format(raw_value)
    elif type == 'boolean':
      return raw_value
    elif nullable or type == 'string':
      return '{}.get()'.format(raw_value)
    else:
      return '*{}'.format(raw_value)

  def _print_getters(self):
    for (type, name, nullable, plural) in self._fields:
      print('  {} get{}() const'.format(
          self._getter_type(type, nullable, plural), title(name)),
          file=self._deferredOutput)
      print('  {{ return {}; }}'.format(
          self._getter_value_to_return(
              name + '_', type, nullable, plural)),
          file=self._deferredOutput)
      print(file=self._deferredOutput)

  def _print_destructor_prototype(self):
    print('  ~{}() {{}}'.format(self._type_name), file=self._deferredOutput)

  def _print_noncopyable(self):
    print('  {}(const {}&) = delete;'.format(
        self._type_name, self._type_name), file=self._deferredOutput)
    print('  {}& operator=(const {}&) = delete;'.format(
        self._type_name, self._type_name), file=self._deferredOutput)

  def start_union(self, name):
    self._type_name = name
    # non-deferred!
    print('class {};'.format(name))
    print('class {} : public Node {{'.format(name),
          file=self._deferredOutput)
    print(' public:', file=self._deferredOutput)
    self._print_constructor()
    print('};', file=self._deferredOutput)
    print(file=self._deferredOutput)

  def union_option(self, type):
    assert type not in self._bases, '{} cannot appear in more than one union!'.format(type)
    self._bases[type] = self._type_name

  def end_union(self, name):
    pass
