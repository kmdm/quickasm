# quickasm overview

Quickly assembly instructions for ARM at a given offset.

Branch instructions are dynamically rewritten so you can use absolute offsets.

# quickasm example

    $ ./quickasm.py -to 0x8011148C
    Using THUMB mode with offset: 0x8011148c
    Enter assembly instructions (Ctrl+D when finished):
    B 0x801114C8

    8011148c:   e01c        b.n 801114c8 <label0>
