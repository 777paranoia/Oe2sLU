#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
e2s_chop.py - chop sliced WAVs into one file per slice (CLI).

Reads the slice markers a tool like e2s_autoslice already wrote (cue points or
the Korg esli slice table) and exports each slice as its own WAV.

Examples:
  python e2s_chop.py sliced/ -o chops/
  python e2s_chop.py loop.wav -o chops/ --suffix _hit --fade-ms 3
"""

import argparse
import os
import sys

import slice_export as sx


def gather_inputs(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.lower().endswith('.wav'):
                    files.append(os.path.join(p, name))
        elif p.lower().endswith('.wav'):
            files.append(p)
        else:
            print('skipping (not a wav): %s' % p, file=sys.stderr)
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('inputs', nargs='+', help='sliced wav files and/or folders')
    ap.add_argument('-o', '--output', required=True, help='output folder')
    ap.add_argument('--suffix', default='',
                    help='text appended to each chopped file name')
    ap.add_argument('--fade-ms', type=float, default=0.0,
                    help='click-free fade in/out per slice, in ms (default 0)')
    args = ap.parse_args(argv)

    files = gather_inputs(args.inputs)
    if not files:
        print('no wav files found', file=sys.stderr)
        return 1
    os.makedirs(args.output, exist_ok=True)

    total = sx.chop_many(files, args.output, suffix=args.suffix,
                         fade_ms=args.fade_ms, log=print)
    print('%d slice(s) written from %d file(s) -> %s'
          % (total, len(files), args.output))
    return 0 if total else 1


if __name__ == '__main__':
    sys.exit(main())
