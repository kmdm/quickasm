#!/usr/bin/env python
# quickasm.py - Quickly assemble instructions at a given offset.
#
# If you don't know why you'd want this - you probably won't! ;)
#
# TODO:
#  - Generate correct output when jumping between ARM/THUMB instruction sets.
#  - Better error handling.
#  - Better branch detection (not so lazy).
#
# Copyright (C) 2012 Kenny Millington
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import getopt
import os
import re
import shutil
import subprocess
import sys
import tempfile

DEFAULT_TOOLCHAIN = 'arm-eabi-'

class QuickAsm:
    MODE_ARM = 0
    MODE_THUMB = 1

    def __init__(self, offset=0, mode=None, cleanup=False):
        self._offset = offset
        self._mode = mode
        self._cleanup = cleanup
        self._mode = self.MODE_THUMB if \
                        mode == self.MODE_THUMB else self.MODE_ARM

    def get_lds(self):
        lds = []
        lds.append('OUTPUT_FORMAT("elf32-littlearm", "elf32-bigarm", '\
                   '"elf32-littlearm")')
        lds.append('OUTPUT_ARCH(arm)')
        lds.append('SECTIONS')
        lds.append('{')
        lds.append('\t. = 0x%08x;' % self._offset)
        lds.append('\t.text : {')
        lds.append('\t\t*(.start);')
        lds.append('\t\t*(.text);')
        lds.append('\t\t*(SORT(.table.*));')
        lds.append('\t}')
        lds.append('\t.data : { *(.data); *(.data2); }')
        lds.append('\t.rodata : { *(.rodata); }')
        lds.append('\t_bss = .;')
        lds.append('\t.bss : { *(.bss); }')
        lds.append('\t_bssend = .;')
        lds.append('\t_end = .;')
        lds.append('}')
        return '\n'.join(lds)

    def get_asm(self, instructions):
        asm = []
        labels = {}

        asm.append('.section .start')

        if self._mode == self.MODE_THUMB:
            asm.append('.thumb')
        else:
            asm.append('.arm')

        # Rewrite B 0xXXXXXXXX style instructions so we can lazily enter those
        # into the scratchpad and have them work.
        for instruction in instructions:
            # FIXME: Lazy way to match branch instructions.
            if instruction.startswith('B') or instruction.startswith('CB'):
                tokens = instruction.split()

                # Only consider tokens we might understand.
                if len(tokens) == 2:
                    try:
                        offset = int(tokens[1], 16)
                    except:
                        pass
                    else:
                        label = 'label%d' % len(labels)
                        labels[label] = offset
                        instruction = '%s %s' % (tokens[0], label)

            asm.append(instruction)

        asm.append('')

        for label, offset in labels.iteritems():
            asm.append('.offset 0x%08x;%s:;.globl %s' % (offset, label, label))

        return '\n'.join(asm)

    def get_makefile(self):
        mk = []
        mk.append('#!/usr/bin/make -f')
        mk.append('TOOLCHAIN?=%s' % DEFAULT_TOOLCHAIN)
        mk.append('AS=$(TOOLCHAIN)as')
        mk.append('CC=$(TOOLCHAIN)gcc')
        mk.append('LD=$(TOOLCHAIN)ld')
        mk.append('OBJDUMP=$(TOOLCHAIN)objdump')
        #mk.append('OBJCOPY=$(TOOLCHAIN)objcopy')
        mk.append('TARGETS=quickasm.txt')
        mk.append('all: $(TARGETS)')
        mk.append('%.txt: %.elf')
        mk.append('\t$(OBJDUMP) -d $*.elf > $*.txt')
        #mk.append('%.bin: %.elf')
        #mk.append('\t$(OBJCOPY) -O binary -S $*.elf $@')
        mk.append('%.elf: %.lds %.o')
        mk.append('\t$(LD) $(LDFLAGS) -o $@ -T $*.lds $*.o')
        mk.append('%.o: %.S')
        mk.append('\t$(AS) $(ASFLAGS) -o $@ $<')
        mk.append('clean:')
        mk.append('\trm -f  $(TARGETS:.txt=.o) $(TARGETS:.txt=.elf) $(TARGETS)')
        mk.append('.PHONY: all clean')
        return '\n'.join(mk)

    def assemble(self, instructions):
        tdir = tempfile.mkdtemp(prefix='quickasm-')

        lds_file = os.path.join(tdir, 'quickasm.lds')
        asm_file = os.path.join(tdir, 'quickasm.S')
        mk_file  = os.path.join(tdir, 'Makefile')

        with open(lds_file, 'w') as f:
            f.write(self.get_lds())

        with open(asm_file, 'w') as f:
            f.write(self.get_asm(instructions))

        with open(mk_file, 'w') as f:
            f.write(self.get_makefile())

        os.chdir(tdir)

        try:
            with open(os.devnull, 'w') as f:
                subprocess.check_call(['make'], stdout=f, stderr=f)

            with open(os.path.join(tdir, 'quickasm.txt'), 'r') as f:
                return re.sub(
                    '.*<.text>[^\n]+', '', f.read(),
                    flags=re.S
                )
        finally:
            if self._cleanup:
                shutil.rmtree(tdir)
            else:
                print 'temporary directory: %s' % tdir

def usage():
    print 'Usage: %s [options]\n' % sys.argv[0]
    print 'options:-'
    print '\t-t\t\tuse the thumb instruction set (default: arm).'
    print '\t-o <addr>\tset the offset (default: 0x0).'
    print '-t-n\tdon\'t clean up temporary directory/files.'
    print '\t-h\t\tthis help information'
    sys.exit(-1)

def parse_opts():
    mode = None
    offset = 0
    cleanup = True

    optlist, args = getopt.getopt(sys.argv[1:], 'hno:t')

    for opt, arg in optlist:
        if opt == '-t':
            mode = QuickAsm.MODE_THUMB
        elif opt == '-o':
            offset = int(arg, 16)
        elif opt == '-n':
            cleanup = False
        elif opt == '-h':
            usage()

    return offset, mode, cleanup

def main():
    try:
        offset, mode, cleanup = parse_opts()
    except:
        usage()

    q = QuickAsm(offset, mode, cleanup)

    m = 'THUMB' if mode == QuickAsm.MODE_THUMB else 'ARM'
    print 'Using %s mode with offset: 0x%08x' % (m, offset)

    if sys.stdin.isatty():
        print 'Enter assembly instructions (Ctrl+D when finished):'

    try:
        print q.assemble(sys.stdin.readlines())
    except:
        print '\nError occurred during compilation, please run with -n to '\
              'preserve the temporary directory and run "make" manually '\
              'to diagnose the error(s).'

if __name__ == '__main__':
    main()
