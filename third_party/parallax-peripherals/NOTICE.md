# Parallax peripheral reference

The SSD1331 initialization register sequence in `p2Displays.c` is adapted from
Matthew Matz's Parallax Simple-Libraries driver, Copyright (C) Parallax, Inc.
2016 (MIT license). Reference revision:
`1cc167c103756e5772b533c833a0f34e6050f459`,
`Learn/Simple Libraries/Display/libssd1331/ssd1331_init.c`.
Pin transport, validation, drawing and MicroBlocks integration are newly written.
The IL3820 initialization, full-update LUT and update command sequence adapt
Matthew Matz and Roy Eltham's driver, Copyright (C) Parallax, Inc. 2018,
`Learn/Simple Libraries/Display/libil3820/il3820_reset.c` and
`il3820_update.c` at the same revision, under the same MIT terms below.
No board-specific font EEPROM, Propeller 1 GPIO or precompiled objects are copied.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
