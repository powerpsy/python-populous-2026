; Fichier      : type
; Taille       : 2176 octets
; Nom interne  : ''
; Hunks        : 2 (first=0, last=1)
;   hunk 0: code    316 octets  relocs=0
;   hunk 1: code   1808 octets  relocs=0
;
; Desassembly 68000 (capstone), adresses logiques
; 0x00010000 + i*0x00100000 par hunk.
==============================================================================

; --- chaines detectees --------------------------
;  0001006e : ' <GL'
;  000100d2 : 'g^(j'
;  00110009 : 'TYPE             '
;  0011001d : 'start  r'
;  0011004f : '`v2$'
;  001102d5 : 'FROM/A,TO,OPT/K'
;  001102f1 : "Can't open %S"
;  00110301 : "Can't open %S"
;  00110311 : "Option '%C' ignored"
;  00110328 : '!Invalid option combination N & H'
;  0011034d : '**BREAK'
;  00110359 : 'typelinJ'
;  001103dd : '%I5  '
;  001103e5 : 'typehexB'
;  001104e9 : '***BREAK'
;  001104f5 : 'getbiteR'
;  00110551 : 'wrline J'
;  001105bc : 'p$(j'
;  001105f2 : 'p,(j'
;  0011060c : 'r p,(j'
;  00110632 : 'r p,(j'
;  00110680 : 'r.p0(j'
;  00110692 : 'p$(j'
;  0011069d : '%X4: '
;  001106a9 : 'tidyup J'

; ========== HUNK 0 (code, 316 octets) ==========

  00010000  movea.l  $164(a2), a4
  00010004  moveq    #$c, d0
  00010006  jsr      (a5)
  00010008  move.l   d1, d2
  0001000a  move.l   #$95, d1
  00010010  lea.l    $10000(pc), a4
  00010014  movea.l  -$4(a4), a4
  00010018  move.l   a4, -(a7)
  0001001a  move.l   d2, -(a7)
  0001001c  adda.l   a4, a4
  0001001e  adda.l   a4, a4
  00010020  move.l   a4, d0
  00010022  beq.b    $10038
  00010024  move.l   $4(a4), d0
  00010028  asl.l    #$2, d0
  0001002a  cmp.l    (a4, d0.l), d1
  0001002e  bge.b    $10034
  00010030  move.l   (a4, d0.l), d1
  00010034  movea.l  (a4), a4
  00010036  bra.b    $1001c
  00010038  move.l   d1, d6
  0001003a  addi.l   #$32, d1
  00010040  suba.l   a0, a0
  00010042  movea.l  $74(a2), a4
  00010046  moveq    #$c, d0
  00010048  jsr      (a5)
  0001004a  tst.l    d1
  0001004c  beq.w    $1012e
  00010050  addi.l   #$32, d1
  00010056  move.l   $70(a2), d5
  0001005a  movea.l  d1, a2
  0001005c  adda.l   a2, a2
  0001005e  adda.l   a2, a2
  00010060  move.l   d1, d7
  00010062  movea.l  a2, a0
  00010064  move.l   d6, (a0)+
  00010066  movea.l  d6, a4
  00010068  adda.l   d7, a4
  0001006a  adda.l   a4, a4
  0001006c  adda.l   a4, a4
  0001006e  move.l   #$474c0003, d0
  00010074  move.l   d0, (a0)+
  00010076  addq.l   #$2, d0
  00010078  cmpa.l   a4, a0
  0001007a  ble.b    $10074
  0001007c  suba.l   a0, a0
  0001007e  move.l   $c(a7), d0
  00010082  lea.l    $10(a7), a1
  00010086  suba.l   d0, a1
  00010088  move.l   #$ffffffff, $4(a1)
  00010090  move.l   a1, d1
  00010092  subi.l   #$a0, d0
  00010098  add.l    d1, d0
  0001009a  move.l   d0, $8(a1)
  0001009e  asr.l    #$2, d1
  000100a0  move.l   d1, $30(a2)
  000100a4  move.l   (a7)+, d7
  000100a6  move.l   d7, d6
  000100a8  asl.l    #$2, d6
  000100aa  add.l    (a0, d6.l), d7
  000100ae  asl.l    #$2, d7
  000100b0  addq.l   #$4, d6
  000100b2  cmp.l    d6, d7
  000100b4  blt.b    $100c8
  000100b6  move.l   (a0, d6.l), d1
  000100ba  movea.l  d5, a4
  000100bc  moveq    #$c, d0
  000100be  jsr      (a5)
  000100c0  tst.l    d1
  000100c2  beq.w    $10130
  000100c6  bra.b    $100b0
  000100c8  move.l   (a7)+, d1
  000100ca  movea.l  d5, a4
  000100cc  moveq    #$c, d0
  000100ce  jsr      (a5)
  000100d0  tst.l    d1
  000100d2  beq.b    $10132
  000100d4  movea.l  $218(a2), a4
  000100d8  moveq    #$c, d0
  000100da  jsr      (a5)
  000100dc  asl.l    #$2, d1
  000100de  movea.l  d1, a3
  000100e0  move.l   a3, -(a7)
  000100e2  beq.b    $100f0
  000100e4  lea.l    $218(a2), a4
  000100e8  moveq    #$f, d0
  000100ea  move.l   (a3)+, (a4)+
  000100ec  dbra     d0, $100ea
  000100f0  lea.l    $10136(pc), a4
  000100f4  move.l   a4, $8(a2)
  000100f8  movea.l  $4(a2), a4
  000100fc  moveq    #$20, d0
  000100fe  moveq    #$0, d1
  00010100  jsr      (a5)
  00010102  moveq    #$0, d0
  00010104  move.l   d0, d7
  00010106  move.l   (a7)+, d1
  00010108  beq.b    $10118
  0001010a  movea.l  d1, a3
  0001010c  lea.l    $218(a2), a4
  00010110  moveq    #$f, d0
  00010112  move.l   (a4)+, (a3)+
  00010114  dbra     d0, $10112
  00010118  move.l   a2, d1
  0001011a  asr.l    #$2, d1
  0001011c  subi.l   #$32, d1
  00010122  movea.l  $78(a2), a4
  00010126  moveq    #$c, d0
  00010128  jsr      (a5)
  0001012a  move.l   d7, d0
  0001012c  rts      
  0001012e  tst.l    (a7)+
  00010130  tst.l    (a7)+
  00010132  moveq    #$ff, d0
  00010134  rts      
  00010136  move.l   d1, d0
  00010138  bra.b    $10104
  0001013a  ori.b    #$aa, d0
; ========== HUNK 1 (code, 1808 octets) ==========

  00110000  ori.b    #$c4, d0
  00110004  ori.b    #$39, d0
  00110008  move.b   (a4), $5950(a0)
  0011000c  dc.w     $4520
  0011000e  move.l   -(a0), d0
  00110010  move.l   -(a0), d0
  00110012  move.l   -(a0), d0
  00110014  move.l   -(a0), d0
  00110016  move.l   -(a0), d0
  00110018  move.l   -(a0), d0
  0011001a  ori.b    #$73, d0
  0011001e  moveq    #$61, d2
  00110020  moveq    #$74, d1
  00110022  move.l   -(a0), d0
  00110024  moveq    #$4, d1
  00110026  add.l    a1, d1
  00110028  lsr.l    #$2, d1
  0011002a  move.l   d1, (a1)
  0011002c  clr.l    $d0(a1)
  00110030  clr.l    $d4(a1)
  00110034  clr.l    $278(a2)
  00110038  move.l   #$e4, d0
  0011003e  movea.l  $108(a2), a4
  00110042  jsr      (a5)
  00110044  move.l   d1, $258(a2)
  00110048  clr.l    $25c(a2)
  0011004c  clr.l    $260(a2)
  00110050  moveq    #$32, d3
  00110052  move.l   (a1), d2
  00110054  lea.l    $2b0(a4), a3
  00110058  move.l   a3, d1
  0011005a  lsr.l    #$2, d1
  0011005c  move.l   #$e4, d0
  00110062  movea.l  $138(a2), a4
  00110066  jsr      (a5)
  00110068  tst.l    d1
  0011006a  bne.w    $110094
  0011006e  lea.l    $2c0(a4), a3
  00110072  move.l   a3, d1
  00110074  lsr.l    #$2, d1
  00110076  move.l   #$e4, d0
  0011007c  movea.l  $124(a2), a4
  00110080  jsr      (a5)
  00110082  moveq    #$14, d1
  00110084  move.l   d1, $278(a2)
  00110088  move.l   #$e4, d0
  0011008e  movea.l  $150(a2), a4
  00110092  jsr      (a5)
  00110094  move.l   (a1), d1
  00110096  lsl.l    #$2, d1
  00110098  move.l   (a0, d1.l), d1
  0011009c  move.l   #$e4, d0
  001100a2  movea.l  $ec(a2), a4
  001100a6  jsr      (a5)
  001100a8  move.l   d1, $25c(a2)
  001100ac  tst.l    d1
  001100ae  bne.w    $1100e0
  001100b2  move.l   (a1), d2
  001100b4  lsl.l    #$2, d2
  001100b6  lea.l    $2cc(a4), a3
  001100ba  move.l   a3, d1
  001100bc  lsr.l    #$2, d1
  001100be  move.l   (a0, d2.l), d2
  001100c2  move.l   #$e4, d0
  001100c8  movea.l  $128(a2), a4
  001100cc  jsr      (a5)
  001100ce  moveq    #$14, d1
  001100d0  move.l   d1, $278(a2)
  001100d4  move.l   #$e4, d0
  001100da  movea.l  $150(a2), a4
  001100de  jsr      (a5)
  001100e0  move.l   $25c(a2), d1
  001100e4  move.l   #$e4, d0
  001100ea  movea.l  $f4(a2), a4
  001100ee  jsr      (a5)
  001100f0  move.l   (a1), d1
  001100f2  lsl.l    #$2, d1
  001100f4  tst.l    $4(a0, d1.l)
  001100f8  beq.w    $110154
  001100fc  move.l   $4(a0, d1.l), d1
  00110100  move.l   #$e4, d0
  00110106  movea.l  $f0(a2), a4
  0011010a  jsr      (a5)
  0011010c  move.l   d1, $260(a2)
  00110110  tst.l    d1
  00110112  bne.w    $110144
  00110116  move.l   (a1), d2
  00110118  lsl.l    #$2, d2
  0011011a  lea.l    $2dc(a4), a3
  0011011e  move.l   a3, d1
  00110120  lsr.l    #$2, d1
  00110122  move.l   $4(a0, d2.l), d2
  00110126  move.l   #$e4, d0
  0011012c  movea.l  $128(a2), a4
  00110130  jsr      (a5)
  00110132  moveq    #$14, d1
  00110134  move.l   d1, $278(a2)
  00110138  move.l   #$e4, d0
  0011013e  movea.l  $150(a2), a4
  00110142  jsr      (a5)
  00110144  move.l   $260(a2), d1
  00110148  move.l   #$e4, d0
  0011014e  movea.l  $f8(a2), a4
  00110152  jsr      (a5)
  00110154  clr.l    $264(a2)
  00110158  move.l   (a1), d1
  0011015a  lsl.l    #$2, d1
  0011015c  tst.l    $8(a0, d1.l)
  00110160  beq.w    $1101f8
  00110164  move.l   $8(a0, d1.l), $d8(a1)
  0011016a  moveq    #$1, d2
  0011016c  move.l   d2, $dc(a1)
  00110170  bra.w    $1101e4
  00110174  bra.w    $1101b4
  00110178  moveq    #$ff, d1
  0011017a  move.l   d1, $264(a2)
  0011017e  bra.w    $1101e0
  00110182  moveq    #$ff, d1
  00110184  move.l   d1, $d4(a1)
  00110188  bra.w    $1101e0
  0011018c  move.l   $d8(a1), d1
  00110190  lsl.l    #$2, d1
  00110192  add.l    $dc(a1), d1
  00110196  moveq    #$0, d2
  00110198  move.b   (a0, d1.l), d2
  0011019c  lea.l    $2ec(a4), a3
  001101a0  move.l   a3, d1
  001101a2  lsr.l    #$2, d1
  001101a4  move.l   #$ec, d0
  001101aa  movea.l  $128(a2), a4
  001101ae  jsr      (a5)
  001101b0  bra.w    $1101e0
  001101b4  move.l   $d8(a1), d1
  001101b8  lsl.l    #$2, d1
  001101ba  add.l    $dc(a1), d1
  001101be  moveq    #$0, d2
  001101c0  move.b   (a0, d1.l), d2
  001101c4  move.l   d2, d1
  001101c6  move.l   #$ec, d0
  001101cc  movea.l  $12c(a2), a4
  001101d0  jsr      (a5)
  001101d2  moveq    #$48, d2
  001101d4  cmp.l    d2, d1
  001101d6  beq.b    $110182
  001101d8  moveq    #$4e, d3
  001101da  cmp.l    d3, d1
  001101dc  beq.b    $110178
  001101de  bra.b    $11018c
  001101e0  addq.l   #$1, $dc(a1)
  001101e4  move.l   $d8(a1), d1
  001101e8  lsl.l    #$2, d1
  001101ea  moveq    #$0, d2
  001101ec  move.b   (a0, d1.l), d2
  001101f0  cmp.l    $dc(a1), d2
  001101f4  bge.w    $110174
  001101f8  tst.l    $264(a2)
  001101fc  beq.w    $11022e
  00110200  tst.l    $d4(a1)
  00110204  beq.w    $11022e
  00110208  lea.l    $304(a4), a3
  0011020c  move.l   a3, d1
  0011020e  lsr.l    #$2, d1
  00110210  move.l   #$e4, d0
  00110216  movea.l  $124(a2), a4
  0011021a  jsr      (a5)
  0011021c  moveq    #$14, d1
  0011021e  move.l   d1, $278(a2)
  00110222  move.l   #$e4, d0
  00110228  movea.l  $150(a2), a4
  0011022c  jsr      (a5)
  0011022e  tst.l    $d4(a1)
  00110232  beq.w    $110246
  00110236  move.l   #$e4, d0
  0011023c  lea.l    $3c8(a4), a4
  00110240  jsr      (a5)
  00110242  bra.w    $1102c6
  00110246  moveq    #$1, d1
  00110248  move.l   d1, $268(a2)
  0011024c  move.l   #$e4, d0
  00110252  movea.l  $d8(a2), a4
  00110256  jsr      (a5)
  00110258  move.l   d1, $d0(a1)
  0011025c  moveq    #$ff, d2
  0011025e  cmp.l    d1, d2
  00110260  beq.w    $1102c6
  00110264  move.l   #$e4, d0
  0011026a  movea.l  $dc(a2), a4
  0011026e  jsr      (a5)
  00110270  move.l   #$e4, d0
  00110276  lea.l    $33c(a4), a4
  0011027a  jsr      (a5)
  0011027c  tst.l    d1
  0011027e  bne.w    $110296
  00110282  moveq    #$1, d1
  00110284  move.l   #$e4, d0
  0011028a  movea.l  $94(a2), a4
  0011028e  jsr      (a5)
  00110290  tst.l    d1
  00110292  beq.w    $1102c4
  00110296  move.l   $258(a2), d1
  0011029a  move.l   #$e4, d0
  001102a0  movea.l  $f8(a2), a4
  001102a4  jsr      (a5)
  001102a6  lea.l    $328(a4), a3
  001102aa  move.l   a3, d1
  001102ac  lsr.l    #$2, d1
  001102ae  move.l   #$e4, d0
  001102b4  movea.l  $124(a2), a4
  001102b8  jsr      (a5)
  001102ba  moveq    #$5, d1
  001102bc  move.l   d1, $278(a2)
  001102c0  bra.w    $1102c6
  001102c4  bra.b    $11024c
  001102c6  move.l   #$e4, d0
  001102cc  movea.l  $150(a2), a4
  001102d0  jsr      (a5)
  001102d2  jmp      (a6)
  001102d4  bchg.b   d7, d6
  001102d6  addq.w   #$1, a7
  001102d8  dc.w     $4d2f
  001102da  dc.w     $412c
  001102dc  addq.w   #$2, a7
  001102de  movea.l  a7, a6
  001102e0  addq.w   #$8, (a4)
  001102e2  move.l   a3, $942(a7)
  001102e6  bsr.b    $11034c
  001102e8  movea.l  -(a1), a0
  001102ea  moveq    #$67, d1
  * 001102ec  dc.w     0x730a
  001102ee  ori.b    #$43, d0
  001102f2  bsr.b    $110362
  001102f4  move.l   $6f(a4, d2.w), $7065(a3)
  001102fa  bgt.b    $11031c
  001102fc  move.l   (a3), $a00(a2)
  * 00110300  dc.w     0x0e43
  00110302  bsr.b    $110372
  00110304  move.l   $6f(a4, d2.w), $7065(a3)
  0011030a  bgt.b    $11032c
  0011030c  move.l   (a3), $a00(a2)
  * 00110310  dc.w     0x144f
  00110312  moveq    #$74, d0
  00110314  bvs.b    $110385
  00110316  bgt.b    $110338
  00110318  move.l   -(a5), -(a3)
  0011031a  dc.w     $4327
  0011031c  movea.l  $676e(a1), a0
  00110320  ble.b    $110394
  00110322  bcs.b    $110388
  00110324  eori.b   #$0, d0
  00110328  move.l   a1, $6e76(a0)
  0011032c  bsr.b    $11039a
  0011032e  bvs.b    $110394
  00110330  movea.l  $7074(a7), a0
  00110334  bvs.b    $1103a5
  00110336  bgt.b    $110358
  00110338  bls.b    $1103a9
  0011033a  blt.b    $11039e
  0011033c  bvs.b    $1103ac
  0011033e  bsr.b    $1103b4
  00110340  bvs.b    $1103b1
  00110342  bgt.b    $110364
  * 00110344  dc.w     0x4e20
  00110346  move.l   -(a0), d3
  00110348  dc.w     $480a
  0011034a  ori.b    #$2a, d0
  0011034e  movea.l  d2, a5
  00110350  addq.w   #$1, d5
  * 00110352  dc.w     0x414b
  00110354  eori.b   #$0, d0
  00110358  bchg.b   d3, $656c696e(a4, invalid.w)
  00110360  tst.l    $264(a2)
  00110364  beq.w    $11037c
  00110368  move.l   $268(a2), d2
  0011036c  lea.l    $7c(a4), a3
  00110370  move.l   a3, d1
  00110372  lsr.l    #$2, d1
  00110374  moveq    #$10, d0
  00110376  movea.l  $128(a2), a4
  0011037a  jsr      (a5)
  0011037c  moveq    #$10, d0
  0011037e  movea.l  $d8(a2), a4
  00110382  jsr      (a5)
  00110384  move.l   d1, (a1)
  00110386  moveq    #$ff, d2
  00110388  cmp.l    d1, d2
  0011038a  beq.w    $11039e
  0011038e  moveq    #$1, d1
  00110390  moveq    #$10, d0
  00110392  movea.l  $94(a2), a4
  00110396  jsr      (a5)
  00110398  tst.l    d1
  0011039a  beq.w    $1103b4
  0011039e  moveq    #$a, d1
  001103a0  moveq    #$10, d0
  001103a2  movea.l  $e0(a2), a4
  001103a6  jsr      (a5)
  001103a8  moveq    #$0, d1
  001103aa  moveq    #$ff, d2
  001103ac  cmp.l    (a1), d2
  001103ae  beq.b    $1103b2
  001103b0  not.l    d1
  001103b2  jmp      (a6)
  001103b4  move.l   (a1), d1
  001103b6  moveq    #$10, d0
  001103b8  movea.l  $e0(a2), a4
  001103bc  jsr      (a5)
  001103be  moveq    #$d, d1
  001103c0  cmp.l    (a1), d1
  001103c2  beq.w    $1103d4
  001103c6  moveq    #$a, d2
  001103c8  cmp.l    (a1), d2
  001103ca  beq.w    $1103d4
  001103ce  moveq    #$c, d3
  001103d0  cmp.l    (a1), d3
  001103d2  bne.b    $11037c
  001103d4  addq.l   #$1, $268(a2)
  001103d8  moveq    #$0, d1
  001103da  jmp      (a6)
  001103dc  btst.l   d2, -(a5)
  001103de  dc.w     $4935
  001103e0  move.l   -(a0), d0
  001103e2  ori.b    #$74, d0
  * 001103e6  dc.w     0x7970
  001103e8  bcs.b    $110452
  001103ea  bcs.b    $110464
  001103ec  clr.l    $4(a1)
  001103f0  moveq    #$c, d1
  001103f2  add.l    a1, d1
  001103f4  lsr.l    #$2, d1
  001103f6  move.l   d1, $8(a1)
  001103fa  move.l   #$268, d2
  00110400  add.l    a1, d2
  00110402  lsr.l    #$2, d2
  00110404  move.l   d2, $264(a1)
  00110408  lsl.l    #$2, d2
  0011040a  move.l   d2, $264(a1)
  0011040e  lsl.l    #$2, d1
  00110410  move.l   d1, $26c(a2)
  00110414  clr.l    $274(a2)
  00110418  moveq    #$ff, d3
  0011041a  move.l   d3, $270(a2)
  0011041e  moveq    #$0, d1
  00110420  move.l   d1, $27c(a1)
  00110424  moveq    #$f, d2
  00110426  cmp.l    d2, d1
  00110428  bgt.w    $110484
  0011042c  move.l   a1, d1
  0011042e  lsr.l    #$2, d1
  00110430  move.l   #$28c, d0
  00110436  lea.l    $110(a4), a4
  0011043a  jsr      (a5)
  0011043c  tst.l    d1
  0011043e  bne.w    $110466
  00110442  move.l   $4(a1), d3
  00110446  move.l   $27c(a1), d2
  0011044a  move.l   $264(a1), d1
  0011044e  move.l   #$28c, d0
  00110454  lea.l    $16c(a4), a4
  00110458  jsr      (a5)
  0011045a  move.l   #$28c, d0
  00110460  movea.l  $150(a2), a4
  00110464  jsr      (a5)
  00110466  addq.l   #$1, $4(a1)
  0011046a  move.l   $264(a1), d1
  0011046e  add.l    $27c(a1), d1
  00110472  moveq    #$0, d2
  00110474  add.l    d1, d2
  00110476  move.b   $3(a1), (a0, d2.l)
  0011047c  moveq    #$1, d1
  0011047e  add.l    $27c(a1), d1
  00110482  bra.b    $110420
  00110484  move.l   $4(a1), d3
  00110488  moveq    #$10, d2
  0011048a  move.l   $264(a1), d1
  0011048e  move.l   #$288, d0
  00110494  lea.l    $16c(a4), a4
  00110498  jsr      (a5)
  0011049a  moveq    #$1, d1
  0011049c  move.l   #$288, d0
  001104a2  movea.l  $94(a2), a4
  001104a6  jsr      (a5)
  001104a8  tst.l    d1
  001104aa  beq.w    $1104d6
  001104ae  move.l   $258(a2), d1
  001104b2  move.l   #$288, d0
  001104b8  movea.l  $f8(a2), a4
  001104bc  jsr      (a5)
  001104be  lea.l    $fc(a4), a3
  001104c2  move.l   a3, d1
  001104c4  lsr.l    #$2, d1
  001104c6  move.l   #$288, d0
  001104cc  movea.l  $124(a2), a4
  001104d0  jsr      (a5)
  001104d2  bra.w    $1104da
  001104d6  bra.w    $11041e
  001104da  move.l   #$288, d0
  001104e0  movea.l  $150(a2), a4
  001104e4  jsr      (a5)
  001104e6  jmp      (a6)
  001104e8  btst.l   d4, $2a2a(a2)
  001104ec  clr.w    (a2)
  * 001104ee  dc.w     0x4541
  * 001104f0  dc.w     0x4b0a
  001104f2  ori.b    #$67, d0
  001104f6  bcs.b    $11056c
  001104f8  bhi.b    $110563
  001104fa  moveq    #$65, d2
  001104fc  addq.l   #$1, $270(a2)
  00110500  move.l   $274(a2), d2
  00110504  cmp.l    $270(a2), d2
  00110508  bgt.w    $110530
  0011050c  move.l   #$258, d2
  00110512  move.l   $26c(a2), d1
  00110516  moveq    #$10, d0
  00110518  movea.l  $a0(a2), a4
  0011051c  jsr      (a5)
  0011051e  move.l   d1, $274(a2)
  00110522  tst.l    d1
  00110524  bne.w    $11052c
  00110528  moveq    #$0, d1
  0011052a  jmp      (a6)
  0011052c  clr.l    $270(a2)
  00110530  move.l   $26c(a2), d1
  00110534  add.l    $270(a2), d1
  00110538  moveq    #$0, d2
  0011053a  add.l    d1, d2
  0011053c  moveq    #$0, d1
  0011053e  move.b   (a0, d2.l), d1
  00110542  move.l   (a1), d2
  00110544  lsl.l    #$2, d2
  00110546  move.l   d1, (a0, d2.l)
  0011054a  moveq    #$ff, d1
  0011054c  jmp      (a6)
  0011054e  nop      
  00110550  bchg.b   d3, $6c(a7, d7.w)
  00110554  bvs.b    $1105c4
  00110556  bcs.b    $110578
  00110558  tst.l    d2
  0011055a  beq.w    $11069a
  0011055e  moveq    #$10, d4
  00110560  sub.l    d2, d4
  00110562  move.l   d4, $c(a1)
  00110566  moveq    #$4, d2
  00110568  move.l   d4, d1
  0011056a  jsr      $12(a5)
  0011056e  move.l   d1, $10(a1)
  00110572  move.l   $c(a1), d2
  00110576  moveq    #$2, d1
  00110578  jsr      $10(a5)
  0011057c  addq.l   #$3, d1
  0011057e  move.l   d1, $14(a1)
  00110582  moveq    #$4, d2
  00110584  move.l   $c(a1), d1
  00110588  jsr      $12(a5)
  0011058c  tst.l    d2
  0011058e  bne.w    $11059a
  00110592  move.l   $10(a1), d1
  00110596  bra.w    $1105a0
  0011059a  moveq    #$1, d1
  0011059c  add.l    $10(a1), d1
  001105a0  add.l    $14(a1), d1
  001105a4  move.l   d1, $14(a1)
  001105a8  move.l   $4(a1), d2
  001105ac  move.l   $8(a1), d3
  001105b0  sub.l    d2, d3
  001105b2  move.l   d3, d2
  001105b4  lea.l    $144(a4), a3
  001105b8  move.l   a3, d1
  001105ba  lsr.l    #$2, d1
  001105bc  moveq    #$24, d0
  001105be  movea.l  $128(a2), a4
  001105c2  jsr      (a5)
  001105c4  move.l   $4(a1), d1
  001105c8  subq.l   #$1, d1
  001105ca  move.l   d1, $18(a1)
  001105ce  moveq    #$0, d1
  001105d0  move.l   d1, $1c(a1)
  001105d4  cmp.l    $18(a1), d1
  001105d8  bgt.w    $11061e
  001105dc  add.l    (a1), d1
  001105de  moveq    #$0, d2
  001105e0  add.l    d1, d2
  001105e2  moveq    #$0, d1
  001105e4  move.b   (a0, d2.l), d1
  001105e8  move.l   d1, d2
  001105ea  lea.l    $14c(a4), a3
  001105ee  move.l   a3, d1
  001105f0  lsr.l    #$2, d1
  001105f2  moveq    #$2c, d0
  001105f4  movea.l  $128(a2), a4
  001105f8  jsr      (a5)
  001105fa  moveq    #$1, d1
  001105fc  add.l    $1c(a1), d1
  00110600  moveq    #$4, d2
  00110602  jsr      $12(a5)
  00110606  tst.l    d2
  00110608  bne.w    $110616
  0011060c  moveq    #$20, d1
  0011060e  moveq    #$2c, d0
  00110610  movea.l  $e0(a2), a4
  00110614  jsr      (a5)
  00110616  moveq    #$1, d1
  00110618  add.l    $1c(a1), d1
  0011061c  bra.b    $1105d0
  0011061e  move.l   $14(a1), $18(a1)
  00110624  moveq    #$1, d1
  00110626  move.l   d1, $1c(a1)
  0011062a  cmp.l    $18(a1), d1
  0011062e  bgt.w    $110644
  00110632  moveq    #$20, d1
  00110634  moveq    #$2c, d0
  00110636  movea.l  $e0(a2), a4
  0011063a  jsr      (a5)
  0011063c  moveq    #$1, d1
  0011063e  add.l    $1c(a1), d1
  00110642  bra.b    $110626
  00110644  move.l   $4(a1), d1
  00110648  subq.l   #$1, d1
  0011064a  move.l   d1, $18(a1)
  0011064e  moveq    #$0, d1
  00110650  move.l   d1, $1c(a1)
  00110654  cmp.l    $18(a1), d1
  00110658  bgt.w    $110692
  0011065c  add.l    (a1), d1
  0011065e  moveq    #$0, d2
  00110660  add.l    d1, d2
  00110662  moveq    #$0, d1
  00110664  move.b   (a0, d2.l), d1
  00110668  move.l   d1, $20(a1)
  0011066c  moveq    #$20, d2
  0011066e  cmp.l    d1, d2
  00110670  bgt.w    $110680
  00110674  moveq    #$7f, d3
  00110676  cmp.l    d3, d1
  00110678  bge.w    $110680
  0011067c  bra.w    $110682
  00110680  moveq    #$2e, d1
  00110682  moveq    #$30, d0
  00110684  movea.l  $e0(a2), a4
  00110688  jsr      (a5)
  0011068a  moveq    #$1, d1
  0011068c  add.l    $1c(a1), d1
  00110690  bra.b    $110650
  00110692  moveq    #$24, d0
  00110694  movea.l  $110(a2), a4
  00110698  jsr      (a5)
  0011069a  jmp      (a6)
  0011069c  btst.l   d2, -(a5)
  0011069e  addq.b   #$4, $20(a4, d3.l)
  001106a2  ori.b    #$25, d0
  001106a6  addq.b   #$4, $69647975(a2, invalid.w)
  001106ae  moveq    #$20, d0
  001106b0  tst.l    $25c(a2)
  001106b4  beq.w    $1106cc
  001106b8  move.l   $25c(a2), d1
  001106bc  moveq    #$c, d0
  001106be  movea.l  $f4(a2), a4
  001106c2  jsr      (a5)
  001106c4  moveq    #$c, d0
  001106c6  movea.l  $fc(a2), a4
  001106ca  jsr      (a5)
  001106cc  tst.l    $260(a2)
  001106d0  beq.w    $1106e8
  001106d4  move.l   $260(a2), d1
  001106d8  moveq    #$c, d0
  001106da  movea.l  $f8(a2), a4
  001106de  jsr      (a5)
  001106e0  moveq    #$c, d0
  001106e2  movea.l  $100(a2), a4
  001106e6  jsr      (a5)
  001106e8  move.l   $278(a2), d1
  001106ec  moveq    #$c, d0
  001106ee  movea.l  $8(a2), a4
  001106f2  jsr      (a5)
  001106f4  jmp      (a6)
  001106f6  nop      
  001106f8  ori.b    #$0, d0
  001106fc  ori.b    #$1, d0
  00110700  ori.b    #$24, d0
  00110704  ori.b    #$54, d0
  00110708  ori.b    #$b0, d0
  0011070c  ori.b    #$9e, d0
