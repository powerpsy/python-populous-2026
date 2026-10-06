; fichier : S:\OpenCode\Populous\reference\original\extracted\populous.prg  (420 octets)
; hunk 0: code 360 octets
; hunk 1: bss 4 octets

; --- chaines ---
;  00010087 : 'BTB6'
;  000100c0 : 'Nu  '
;  000100cc : 'NuSABB'

; ===== HUNK 0 =====
  00010000  lea.l    $100e8(pc), a0
  00010004  lea.l    $7f000.l, a1
  0001000a  move.l   (a0)+, d0
  0001000c  move.l   (a0)+, d1
  0001000e  move.l   (a0)+, d5
  00010010  movea.l  a1, a2
  00010012  adda.l   d0, a0
  00010014  adda.l   d1, a2
  00010016  move.l   -(a0), d0
  00010018  eor.l    d0, d5
  0001001a  lsr.l    #$1, d0
  0001001c  bne.b    $10022
  0001001e  bsr.w    $100c2
  00010022  bcs.b    $10060
  00010024  moveq    #$8, d1
  00010026  moveq    #$1, d3
  00010028  lsr.l    #$1, d0
  0001002a  bne.b    $10030
  0001002c  bsr.w    $100c2
  00010030  bcs.b    $1008c
  00010032  moveq    #$3, d1
  00010034  clr.w    d4
  00010036  bsr.w    $100ce
  0001003a  move.w   d2, d3
  0001003c  add.w    d4, d3
  0001003e  moveq    #$7, d1
  00010040  lsr.l    #$1, d0
  00010042  bne.b    $10048
  00010044  bsr.w    $100c2
  00010048  roxl.l   #$1, d2
  0001004a  dbra     d1, $10040
  0001004e  move.b   d2, -(a2)
  00010050  dbra     d3, $1003e
  00010054  bra.w    $1009a
  00010058  moveq    #$8, d1
  0001005a  moveq    #$8, d4
  0001005c  bra.w    $10036
  00010060  moveq    #$2, d1
  00010062  bsr.w    $100ce
  00010066  cmpi.b   #$2, d2
  0001006a  blt.b    $10082
  0001006c  cmpi.b   #$3, d2
  00010070  beq.b    $10058
  00010072  moveq    #$8, d1
  00010074  bsr.w    $100ce
  00010078  move.w   d2, d3
  0001007a  move.w   #$c, d1
  0001007e  bra.w    $1008c
  00010082  move.w   #$9, d1
  00010086  add.w    d2, d1
  00010088  addq.w   #$2, d2
  0001008a  move.w   d2, d3
  0001008c  bsr.w    $100ce
  00010090  subq.w   #$1, a2
  00010092  move.b   (a2, d2.w), (a2)
  00010096  dbra     d3, $10090
  0001009a  move.l   a0, $dff180.l
  000100a0  cmpa.l   a2, a1
  000100a2  blt.w    $1001a
  000100a6  tst.l    d5
  000100a8  bne.b    $100b0
  000100aa  jmp      $7f000.l
  000100b0  move.w   #$ffff, d0
  000100b4  move.w   d0, $dff180.l
  000100ba  dbra     d0, $100b4
  000100be  moveq    #$ff, d0
  000100c0  rts      
  000100c2  move.l   -(a0), d0
  000100c4  eor.l    d0, d5
  000100c6  move.w   #$10, ccr
  000100ca  roxr.l   #$1, d0
  000100cc  rts      
  000100ce  subq.w   #$1, d1
  000100d0  clr.w    d2
  000100d2  lsr.l    #$1, d0
  000100d4  bne.b    $100e0
  000100d6  move.l   -(a0), d0
  000100d8  eor.l    d0, d5
  000100da  move.w   #$10, ccr
  000100de  roxr.l   #$1, d0
  000100e0  roxl.l   #$1, d2
  000100e2  dbra     d1, $100d2
  000100e6  rts      
  000100e8  ori.b    #$74, d0
  000100ec  ori.b    #$92, d0
  000100f0  bge.b    $100ee
  000100f2  tas.b    (a1)+
  000100f4  move.l   d6, d3
  * 000100f6  dc.w     0x067c
  000100f8  btst.l   d2, -(a2)
  000100fa  or.b     d1, d1
  000100fc  move.b   d0, (a1)
  * 000100fe  dc.w     0xae00
  00010100  negx.l   -(a0)
  00010102  sub.w    -(a1), d3
  00010104  lea.l    $897(a2), a0
  00010108  or.b     -(a4), d0
  * 0001010a  dc.w     0x140d
  0001010c  and.w    d5, d4
  0001010e  or.b     $d(a0, d0.w), d0
  00010112  move.w   (a0), ccr
  00010114  btst.l   d4, (a3)
  00010116  cmpi.b   #$e2, (a0)
  0001011a  bclr.b   d1, d1
  * 0001011c  dc.w     0x00c0
  0001011e  eor.w    d3, d1
  00010120  and.l    -(a3), d0
  00010122  asr.b    #$1, d1
  * 00010124  dc.w     0xa180
  * 00010126  dc.w     0xad01
  00010128  move.w   sr, (a1)+
  * 0001012a  dc.w     0x00c1
  0001012c  move.w   d0, d2
  0001012e  bhi.b    $10154
  00010130  move.w   d1, (a6)
  00010132  move.l   (a4), $5ad(a0)
  * 00010136  dc.w     0x1271
  00010138  btst.l   d0, d2
  0001013a  and.b    d0, d1
  0001013c  divs.w   #$ecd1, d5
  00010140  move.b   d5, -(a7)
  00010142  movea.l  d4, a0
  00010144  divu.w   d5, d2
  00010146  and.b    (a6)+, d0
  * 00010148  dc.w     0xa2e4
  * 0001014a  dc.w     0xeafe
  0001014c  divu.w   -(a5), d6
  0001014e  move.w   d1, d7
  * 00010150  dc.w     0x41ce
  * 00010152  dc.w     0x464d
  00010154  rol.l    #$6, d4
  00010156  lsr.w    d4, d5
  00010158  move.l   a4, (a6)
  0001015a  subx.b   -(a4), -(a6)
  * 0001015c  dc.w     0x9d3d
  0001015e  asl.w    -(a0)
  00010160  bclr.b   d1, d1
  00010162  or.b     (a3), d0
  00010164  st.b     d4
  00010166  and.b    d4, d0
