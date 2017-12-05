# Copyright 2016 The Bazel Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""This package manipulates v2.2 image configuration metadata."""

import argparse
import json
import sys

import six

from container import utils
from containerregistry.transform.v2_2 import metadata as v2_2_metadata

parser = argparse.ArgumentParser(
    description='Manipulate Docker image v2.2 metadata.')

parser.add_argument('--base', action='store',
                    help='The parent image.')

parser.add_argument('--output', action='store', required=True,
                    help='The output file to generate.')

parser.add_argument('--layer', action='append', default=[],
                    help='Layer sha256 hashes that make up this image')

parser.add_argument('--entrypoint', action='append', default=[],
                    help='Override the "Entrypoint" of the previous layer.')

parser.add_argument('--command', action='append', default=[],
                    help='Override the "Cmd" of the previous layer.')

parser.add_argument('--user', action='store',
                    help='The username to run commands under.')

parser.add_argument('--labels', action='append', default=[],
                    help='Augment the "Label" of the previous layer.')

parser.add_argument('--ports', action='append', default=[],
                    help='Augment the "ExposedPorts" of the previous layer.')

parser.add_argument('--volumes', action='append', default=[],
                    help='Augment the "Volumes" of the previous layer.')

parser.add_argument('--workdir', action='store',
                    help='Set the working directory of the layer.')

parser.add_argument('--env', action='append', default=[],
                    help='Augment the "Env" of the previous layer.')

parser.add_argument('--stamp-info-file', action='append', required=False,
                    help=('A list of files from which to read substitutions '
                          'to make in the provided fields, e.g. {BUILD_USER}'))

_PROCESSOR_ARCHITECTURE = 'amd64'

_OPERATING_SYSTEM = 'linux'


def KeyValueToDict(pair):
  """Converts an iterable object of key=value pairs to dictionary."""
  d = dict()
  for kv in pair:
    (k, v) = kv.split('=', 1)
    d[k] = v
  return d


# See: https://bugs.python.org/issue14364
def fix_dashdash(l):
  return [
    x if x != [] else '--'
    for x in l
  ]

def main():
  args = parser.parse_args()

  def Stamp(inp):
    """Perform substitutions in the provided value."""
    if not args.stamp_info_file or not inp:
      return inp
    format_args = {}
    for infofile in args.stamp_info_file:
      with open(infofile) as info:
        for line in info:
          line = line.strip('\n')
          key, value = line.split(' ', 1)
          if key in format_args:
            print ('WARNING: Duplicate value for key "%s": '
                   'using "%s"' % (key, value))
          format_args[key] = value

    return inp.format(**format_args)

  base_json = '{}'
  if args.base:
    with open(args.base, 'r') as r:
      base_json = r.read()
  data = json.loads(base_json)

  layers = []
  for layer in args.layer:
    layers.append(utils.ExtractValue(layer))

  labels = KeyValueToDict(args.labels)
  for label, value in six.iteritems(labels):
    if value.startswith('@'):
      with open(value[1:], 'r') as f:
        labels[label] = f.read()
    elif '{' in value:
      labels[label] = Stamp(value)

  output = v2_2_metadata.Override(data, v2_2_metadata.Overrides(
      author='Bazel', created_by='bazel build ...',
      layers=layers, entrypoint=list(map(Stamp, fix_dashdash(args.entrypoint))),
      cmd=list(map(Stamp, fix_dashdash(args.command))), user=Stamp(args.user),
      labels=labels, env={
        k: Stamp(v)
        for (k, v) in six.iteritems(KeyValueToDict(args.env))
      },
      ports=args.ports, volumes=args.volumes, workdir=Stamp(args.workdir)),
                                  architecture=_PROCESSOR_ARCHITECTURE,
                                  operating_system=_OPERATING_SYSTEM)

  with open(args.output, 'w') as fp:
    json.dump(output, fp, sort_keys=True)
    fp.write('\n')


if __name__ == '__main__':
  main()
