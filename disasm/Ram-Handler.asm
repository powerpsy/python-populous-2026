; Fichier      : l\Ram-Handler
; Taille       : 6464 octets
; Nom interne  : ''
; Hunks        : 2 (first=0, last=1)
;   hunk 0: code     48 octets  relocs=0
;   hunk 1: code   6364 octets  relocs=0
;
; Desassembly 68000 (capstone), adresses logiques
; 0x00010000 + i*0x00100000 par hunk.
==============================================================================

; --- chaines detectees --------------------------
;  00010007 : 'B A"B '
;  00110031 : 'Xr-p'
;  00110115 : ' %|DOS'
;  00110158 : 'p (j'
;  0011017a : 'p (j'
;  00110190 : 'p (j'
;  001101be : 'p (j'
;  001101ec : 'p (j'
;  00110204 : '(0H &08'
;  00110226 : 'p (j'
;  0011026a : 'p$(j'
;  00110280 : 'p$(j'
;  00110290 : 'p0(j'
;  001102a2 : 'p (j'
;  001102b3 : '\\p (j'
;  001102e4 : 'p (j'
;  00110318 : 'p (j'
;  0011034e : 'p (j'
;  00110384 : 'p (j'
;  001103b8 : 'p (j'
;  001103de : 'p (j'
;  00110429 : '$p$(j'
;  00110452 : 'p (j'
;  0011046a : 'p (j'
;  0011048c : 'p (j'
;  001104bc : 'p (j'
;  001104e0 : 'p (j'
;  00110500 : 'p (j'
;  00110518 : 'p (j'
;  00110631 : 'RAM DISK'
;  001106aa : 'tR#B'
;  00110795 : ' p I'
;  001107ec : '(t")'
;  001107fc : '(x")'
;  0011080c : '(|")'
;  0011099a : 'r- <'
;  00110aa4 : 't:")'
;  00110aca : 't/")'
;  00110ad0 : 'p (j'
;  00110c86 : 't:")'
;  00110c8c : 'pD(j'
;  00110d77 : '\\p (j'
;  00110eaf : 'Xr{pHI'
;  00110f9b : 'Dp@(j'
;  00110fbd : '0p@(j'
;  001111af : '4pdI'
;  001111eb : 'Xp|I'
;  001111fb : '4p|I'
;  0011121f : '\\p|I'
;  00111279 : '\\p|I'
;  001112b5 : 'dp|I'
;  001112e1 : 'hp|I'
;  001112fd : 'hp|I'
;  00111319 : 'Xp|I'
;  001113a3 : 'hp|I'
;  001113b1 : '\\p|(j'
;  0011149a : 'p@(j'
;  001114b8 : 'p@(j'
;  001114d1 : '\\p@(j'
;  00111516 : 'p$(j'
;  0011153c : 'p$(j'
;  0011154d : '(p$(j'
;  0011156e : 'p$(j'
;  0011157b : '\\p$(j'
;  001115a2 : '#p( '
;  00111654 : 'pH(j'
;  00111668 : 'pH(j'
;  001116b2 : 'pL(j'
;  001116d7 : '\\pH(j'
;  001117fc : 'p<(j'
;  001118b6 : 'pD(j'

; ========== HUNK 0 (code, 48 octets) ==========

  00010000  ori.b    #$c, d0
  00010004  movem.l  a1/a6, -(a7)
  00010008  movea.l  d1, a0
  0001000a  movea.l  d2, a1
  0001000c  move.l   d3, d0
  0001000e  movea.l  $4.w, a6
  00010012  jsr      -$270(a6)
  00010016  movem.l  (a7)+, a1/a6
  0001001a  suba.l   a0, a0
  0001001c  jmp      (a6)
  0001001e  ori.b    #$0, d0
  00010022  ori.b    #$0, d0
  00010026  ori.l    #$4, (a4)+
  0001002c  ori.b    #$9c, d0
; ========== HUNK 1 (code, 6364 octets) ==========

  00110000  ori.b    #$37, d0
  00110004  move.l   d1, d2
  00110006  lsl.l    #$2, d2
  00110008  move.l   $1c(a0, d2.l), $8(a1)
  0011000e  moveq    #$c, d1
  00110010  moveq    #$18, d0
  00110012  movea.l  $74(a2), a4
  00110016  jsr      (a5)
  00110018  move.l   d1, $c(a1)
  0011001c  move.l   d1, d2
  0011001e  lea.l    $62c(a4), a3
  00110022  move.l   a3, d1
  00110024  lsr.l    #$2, d1
  00110026  moveq    #$1c, d0
  00110028  movea.l  $1cc(a2), a4
  0011002c  jsr      (a5)
  0011002e  clr.l    $258(a2)
  00110032  moveq    #$2d, d1
  00110034  moveq    #$1c, d0
  00110036  movea.l  $74(a2), a4
  0011003a  jsr      (a5)
  0011003c  move.l   d1, $25c(a2)
  00110040  moveq    #$0, d1
  00110042  move.l   d1, $10(a1)
  00110046  moveq    #$2d, d2
  00110048  cmp.l    d2, d1
  0011004a  bgt.w    $110060
  0011004e  add.l    $25c(a2), d1
  00110052  lsl.l    #$2, d1
  00110054  clr.l    (a0, d1.l)
  00110058  moveq    #$1, d1
  0011005a  add.l    $10(a1), d1
  0011005e  bra.b    $110042
  00110060  move.l   $25c(a2), d1
  00110064  lsl.l    #$2, d1
  00110066  moveq    #$2, d2
  00110068  move.l   d2, $8(a0, d1.l)
  0011006c  moveq    #$1, d1
  0011006e  move.l   d1, $268(a2)
  00110072  moveq    #$9, d3
  00110074  add.l    $25c(a2), d3
  00110078  move.l   d3, d2
  0011007a  move.l   $c(a1), d1
  0011007e  moveq    #$1c, d0
  00110080  movea.l  $1cc(a2), a4
  00110084  jsr      (a5)
  00110086  moveq    #$6, d1
  00110088  add.l    $25c(a2), d1
  0011008c  moveq    #$1c, d0
  0011008e  movea.l  $158(a2), a4
  00110092  jsr      (a5)
  00110094  moveq    #$1c, d0
  00110096  movea.l  $38(a2), a4
  0011009a  jsr      (a5)
  0011009c  move.l   $8(a1), d2
  001100a0  lsl.l    #$2, d2
  001100a2  move.l   d1, $8(a0, d2.l)
  001100a6  moveq    #$4, d1
  001100a8  move.l   d1, $10(a1)
  001100ac  moveq    #$9, d2
  001100ae  cmp.l    d2, d1
  001100b0  bgt.w    $1100c6
  001100b4  add.l    $8(a1), d1
  001100b8  lsl.l    #$2, d1
  001100ba  clr.l    (a0, d1.l)
  001100be  moveq    #$1, d1
  001100c0  add.l    $10(a1), d1
  001100c4  bra.b    $1100a8
  001100c6  move.l   $c(a1), d1
  001100ca  moveq    #$1c, d0
  001100cc  movea.l  $154(a2), a4
  001100d0  jsr      (a5)
  001100d2  move.l   d1, $4(a1)
  001100d6  moveq    #$1c, d0
  001100d8  movea.l  $38(a2), a4
  001100dc  jsr      (a5)
  001100de  move.l   $4(a1), d2
  001100e2  lsl.l    #$2, d2
  001100e4  move.l   d1, $8(a0, d2.l)
  001100e8  move.l   $4(a1), d1
  001100ec  lsl.l    #$2, d1
  001100ee  moveq    #$2, d2
  001100f0  move.l   d2, $4(a0, d1.l)
  001100f4  move.l   $4(a1), d1
  001100f8  lsl.l    #$2, d1
  001100fa  clr.l    $c(a0, d1.l)
  001100fe  move.l   $4(a1), d1
  00110102  lsl.l    #$2, d1
  00110104  clr.l    $1c(a0, d1.l)
  00110108  move.l   $4(a1), d1
  0011010c  lsl.l    #$2, d1
  0011010e  move.l   #$444f5300, $20(a0, d1.l)
  00110116  move.l   #$444f5300, $278(a2)
  0011011e  move.l   $4(a1), $274(a2)
  00110124  moveq    #$0, d3
  00110126  moveq    #$ff, d2
  00110128  move.l   (a1), d1
  0011012a  moveq    #$1c, d0
  0011012c  movea.l  $c4(a2), a4
  00110130  jsr      (a5)
  00110132  moveq    #$1c, d0
  00110134  movea.l  $a4(a2), a4
  00110138  jsr      (a5)
  0011013a  move.l   d1, $10(a1)
  0011013e  bra.w    $110524
  00110142  move.l   $10(a1), d1
  00110146  moveq    #$30, d0
  00110148  lea.l    $6f0(a4), a4
  0011014c  jsr      (a5)
  0011014e  move.l   $26c(a2), d3
  00110152  move.l   d1, d2
  00110154  move.l   $10(a1), d1
  00110158  moveq    #$20, d0
  0011015a  movea.l  $c4(a2), a4
  0011015e  jsr      (a5)
  00110160  bra.w    $11062c
  00110164  move.l   $10(a1), d1
  00110168  moveq    #$30, d0
  0011016a  lea.l    $72c(a4), a4
  0011016e  jsr      (a5)
  00110170  move.l   $26c(a2), d3
  00110174  move.l   d1, d2
  00110176  move.l   $10(a1), d1
  0011017a  moveq    #$20, d0
  0011017c  movea.l  $c4(a2), a4
  00110180  jsr      (a5)
  00110182  bra.w    $11062c
  00110186  moveq    #$0, d3
  00110188  move.l   $274(a2), d2
  0011018c  move.l   $10(a1), d1
  00110190  moveq    #$20, d0
  00110192  movea.l  $c4(a2), a4
  00110196  jsr      (a5)
  00110198  bra.w    $11062c
  0011019c  move.l   $10(a1), d1
  001101a0  lsl.l    #$2, d1
  001101a2  move.l   d1, d2
  001101a4  move.l   $18(a0, d2.l), d2
  001101a8  move.l   $14(a0, d1.l), d1
  001101ac  moveq    #$30, d0
  001101ae  lea.l    $c5c(a4), a4
  001101b2  jsr      (a5)
  001101b4  move.l   $26c(a2), d3
  001101b8  move.l   d1, d2
  001101ba  move.l   $10(a1), d1
  001101be  moveq    #$20, d0
  001101c0  movea.l  $c4(a2), a4
  001101c4  jsr      (a5)
  001101c6  bra.w    $11062c
  001101ca  move.l   $10(a1), d1
  001101ce  lsl.l    #$2, d1
  001101d0  move.l   d1, d2
  001101d2  move.l   $18(a0, d2.l), d2
  001101d6  move.l   $14(a0, d1.l), d1
  001101da  moveq    #$30, d0
  001101dc  lea.l    $8c0(a4), a4
  001101e0  jsr      (a5)
  001101e2  move.l   $26c(a2), d3
  001101e6  move.l   d1, d2
  001101e8  move.l   $10(a1), d1
  001101ec  moveq    #$20, d0
  001101ee  movea.l  $c4(a2), a4
  001101f2  jsr      (a5)
  001101f4  bra.w    $11062c
  001101f8  move.l   $10(a1), d1
  001101fc  lsl.l    #$2, d1
  001101fe  move.l   d1, d2
  00110200  move.l   d1, d3
  00110202  move.l   d1, d4
  00110204  move.l   $20(a0, d4.l), d4
  00110208  move.l   $1c(a0, d3.l), d3
  0011020c  move.l   $18(a0, d2.l), d2
  00110210  move.l   $14(a0, d1.l), d1
  00110214  moveq    #$30, d0
  00110216  lea.l    $1198(a4), a4
  0011021a  jsr      (a5)
  0011021c  move.l   $26c(a2), d3
  00110220  move.l   d1, d2
  00110222  move.l   $10(a1), d1
  00110226  moveq    #$20, d0
  00110228  movea.l  $c4(a2), a4
  0011022c  jsr      (a5)
  0011022e  bra.w    $11062c
  00110232  move.l   $10(a1), d1
  00110236  lsl.l    #$2, d1
  00110238  move.l   $14(a0, d1.l), d1
  0011023c  moveq    #$20, d0
  0011023e  lea.l    $1734(a4), a4
  00110242  jsr      (a5)
  00110244  move.l   d1, $14(a1)
  00110248  tst.l    d1
  0011024a  beq.w    $110276
  0011024e  move.l   $10(a1), d2
  00110252  lsl.l    #$2, d2
  00110254  move.l   $18(a0, d2.l), d2
  00110258  moveq    #$34, d0
  0011025a  lea.l    $13bc(a4), a4
  0011025e  jsr      (a5)
  00110260  move.l   $26c(a2), d3
  00110264  move.l   d1, d2
  00110266  move.l   $10(a1), d1
  0011026a  moveq    #$24, d0
  0011026c  movea.l  $c4(a2), a4
  00110270  jsr      (a5)
  00110272  bra.w    $110288
  00110276  move.l   $26c(a2), d3
  0011027a  moveq    #$0, d2
  0011027c  move.l   $10(a1), d1
  00110280  moveq    #$24, d0
  00110282  movea.l  $c4(a2), a4
  00110286  jsr      (a5)
  00110288  bra.w    $11062c
  0011028c  move.l   $10(a1), d1
  00110290  moveq    #$30, d0
  00110292  movea.l  $8c(a2), a4
  00110296  jsr      (a5)
  00110298  move.l   $26c(a2), d3
  0011029c  move.l   d1, d2
  0011029e  move.l   $10(a1), d1
  001102a2  moveq    #$20, d0
  001102a4  movea.l  $c4(a2), a4
  001102a8  jsr      (a5)
  001102aa  bra.w    $11062c
  001102ae  moveq    #$6, d1
  001102b0  add.l    $25c(a2), d1
  001102b4  moveq    #$20, d0
  001102b6  movea.l  $158(a2), a4
  001102ba  jsr      (a5)
  001102bc  move.l   $10(a1), d1
  001102c0  lsl.l    #$2, d1
  001102c2  move.l   d1, d2
  001102c4  move.l   d1, d3
  001102c6  move.l   $1c(a0, d3.l), d3
  001102ca  move.l   $18(a0, d2.l), d2
  001102ce  move.l   $14(a0, d1.l), d1
  001102d2  moveq    #$30, d0
  001102d4  lea.l    $d80(a4), a4
  001102d8  jsr      (a5)
  001102da  move.l   $26c(a2), d3
  001102de  move.l   d1, d2
  001102e0  move.l   $10(a1), d1
  001102e4  moveq    #$20, d0
  001102e6  movea.l  $c4(a2), a4
  001102ea  jsr      (a5)
  001102ec  bra.w    $11062c
  001102f0  move.l   $10(a1), d1
  001102f4  lsl.l    #$2, d1
  001102f6  move.l   d1, d2
  001102f8  move.l   d1, d3
  001102fa  move.l   $1c(a0, d3.l), d3
  001102fe  move.l   $18(a0, d2.l), d2
  00110302  move.l   $14(a0, d1.l), d1
  00110306  moveq    #$30, d0
  00110308  lea.l    $d10(a4), a4
  0011030c  jsr      (a5)
  0011030e  move.l   $26c(a2), d3
  00110312  move.l   d1, d2
  00110314  move.l   $10(a1), d1
  00110318  moveq    #$20, d0
  0011031a  movea.l  $c4(a2), a4
  0011031e  jsr      (a5)
  00110320  bra.w    $11062c
  00110324  move.l   $10(a1), d1
  00110328  lsl.l    #$2, d1
  0011032a  move.l   d1, d2
  0011032c  move.l   d1, d3
  0011032e  moveq    #$0, d4
  00110330  move.l   $1c(a0, d3.l), d3
  00110334  move.l   $18(a0, d2.l), d2
  00110338  move.l   $14(a0, d1.l), d1
  0011033c  moveq    #$30, d0
  0011033e  lea.l    $e08(a4), a4
  00110342  jsr      (a5)
  00110344  move.l   $26c(a2), d3
  00110348  move.l   d1, d2
  0011034a  move.l   $10(a1), d1
  0011034e  moveq    #$20, d0
  00110350  movea.l  $c4(a2), a4
  00110354  jsr      (a5)
  00110356  bra.w    $11062c
  0011035a  move.l   $10(a1), d1
  0011035e  lsl.l    #$2, d1
  00110360  move.l   d1, d2
  00110362  move.l   d1, d3
  00110364  moveq    #$ff, d4
  00110366  move.l   $1c(a0, d3.l), d3
  0011036a  move.l   $18(a0, d2.l), d2
  0011036e  move.l   $14(a0, d1.l), d1
  00110372  moveq    #$30, d0
  00110374  lea.l    $e08(a4), a4
  00110378  jsr      (a5)
  0011037a  move.l   $26c(a2), d3
  0011037e  move.l   d1, d2
  00110380  move.l   $10(a1), d1
  00110384  moveq    #$20, d0
  00110386  movea.l  $c4(a2), a4
  0011038a  jsr      (a5)
  0011038c  bra.w    $11062c
  00110390  move.l   $10(a1), d1
  00110394  lsl.l    #$2, d1
  00110396  move.l   d1, d2
  00110398  move.l   d1, d3
  0011039a  move.l   $1c(a0, d3.l), d3
  0011039e  move.l   $18(a0, d2.l), d2
  001103a2  move.l   $14(a0, d1.l), d1
  001103a6  moveq    #$30, d0
  001103a8  lea.l    $1048(a4), a4
  001103ac  jsr      (a5)
  001103ae  move.l   $26c(a2), d3
  001103b2  move.l   d1, d2
  001103b4  move.l   $10(a1), d1
  001103b8  moveq    #$20, d0
  001103ba  movea.l  $c4(a2), a4
  001103be  jsr      (a5)
  001103c0  bra.w    $11062c
  001103c4  move.l   $10(a1), d1
  001103c8  lsl.l    #$2, d1
  001103ca  move.l   $14(a0, d1.l), d1
  001103ce  moveq    #$20, d0
  001103d0  lea.l    $182c(a4), a4
  001103d4  jsr      (a5)
  001103d6  moveq    #$0, d3
  001103d8  moveq    #$ff, d2
  001103da  move.l   $10(a1), d1
  001103de  moveq    #$20, d0
  001103e0  movea.l  $c4(a2), a4
  001103e4  jsr      (a5)
  001103e6  bra.w    $11062c
  001103ea  move.l   $10(a1), d1
  001103ee  lsl.l    #$2, d1
  001103f0  move.l   $14(a0, d1.l), d1
  001103f4  moveq    #$20, d0
  001103f6  lea.l    $1734(a4), a4
  001103fa  jsr      (a5)
  001103fc  move.l   d1, $14(a1)
  00110400  move.l   $10(a1), $24(a1)
  00110406  tst.l    d1
  00110408  bne.w    $110412
  0011040c  moveq    #$0, d1
  0011040e  bra.w    $110420
  00110412  moveq    #$fe, d2
  00110414  move.l   $14(a1), d1
  00110418  moveq    #$34, d0
  0011041a  lea.l    $1788(a4), a4
  0011041e  jsr      (a5)
  00110420  move.l   $26c(a2), d3
  00110424  move.l   d1, d2
  00110426  move.l   $24(a1), d1
  0011042a  moveq    #$24, d0
  0011042c  movea.l  $c4(a2), a4
  00110430  jsr      (a5)
  00110432  bra.w    $11062c
  00110436  move.l   $10(a1), d1
  0011043a  lsl.l    #$2, d1
  0011043c  move.l   $14(a0, d1.l), d1
  00110440  moveq    #$30, d0
  00110442  lea.l    $182c(a4), a4
  00110446  jsr      (a5)
  00110448  move.l   $26c(a2), d3
  0011044c  move.l   d1, d2
  0011044e  move.l   $10(a1), d1
  00110452  moveq    #$20, d0
  00110454  movea.l  $c4(a2), a4
  00110458  jsr      (a5)
  0011045a  bra.w    $11062c
  0011045e  move.l   #$ca, d3
  00110464  moveq    #$0, d2
  00110466  move.l   $10(a1), d1
  0011046a  moveq    #$20, d0
  0011046c  movea.l  $c4(a2), a4
  00110470  jsr      (a5)
  00110472  bra.w    $11062c
  00110476  move.l   $10(a1), d1
  0011047a  moveq    #$30, d0
  0011047c  lea.l    $1584(a4), a4
  00110480  jsr      (a5)
  00110482  move.l   $26c(a2), d3
  00110486  move.l   d1, d2
  00110488  move.l   $10(a1), d1
  0011048c  moveq    #$20, d0
  0011048e  movea.l  $c4(a2), a4
  00110492  jsr      (a5)
  00110494  bra.w    $11062c
  00110498  move.l   $10(a1), d1
  0011049c  lsl.l    #$2, d1
  0011049e  move.l   $14(a0, d1.l), d1
  001104a2  moveq    #$20, d0
  001104a4  lea.l    $1734(a4), a4
  001104a8  jsr      (a5)
  001104aa  tst.l    d1
  001104ac  bne.w    $1104c8
  001104b0  move.l   #$ca, d3
  001104b6  moveq    #$0, d2
  001104b8  move.l   $10(a1), d1
  001104bc  moveq    #$20, d0
  001104be  movea.l  $c4(a2), a4
  001104c2  jsr      (a5)
  001104c4  bra.w    $11062c
  001104c8  move.l   $10(a1), d1
  001104cc  moveq    #$20, d0
  001104ce  lea.l    $684(a4), a4
  001104d2  jsr      (a5)
  001104d4  bra.w    $11062c
  001104d8  moveq    #$0, d3
  001104da  moveq    #$ff, d2
  001104dc  move.l   $10(a1), d1
  001104e0  moveq    #$20, d0
  001104e2  movea.l  $c4(a2), a4
  001104e6  jsr      (a5)
  001104e8  bra.w    $11062c
  001104ec  move.l   $10(a1), d1
  001104f0  moveq    #$30, d0
  001104f2  lea.l    $14dc(a4), a4
  001104f6  jsr      (a5)
  001104f8  moveq    #$0, d3
  001104fa  move.l   d1, d2
  001104fc  move.l   $10(a1), d1
  00110500  moveq    #$20, d0
  00110502  movea.l  $c4(a2), a4
  00110506  jsr      (a5)
  00110508  bra.w    $11062c
  0011050c  move.l   #$d1, d3
  00110512  moveq    #$0, d2
  00110514  move.l   $10(a1), d1
  00110518  moveq    #$20, d0
  0011051a  movea.l  $c4(a2), a4
  0011051e  jsr      (a5)
  00110520  bra.w    $11062c
  00110524  move.l   $10(a1), d1
  00110528  lsl.l    #$2, d1
  0011052a  move.l   $8(a0, d1.l), d1
  0011052e  moveq    #$18, d2
  00110530  cmp.l    d2, d1
  00110532  bge.w    $1105a2
  00110536  moveq    #$10, d3
  00110538  cmp.l    d3, d1
  0011053a  bge.w    $11056c
  0011053e  moveq    #$2, d4
  00110540  cmp.l    d4, d1
  00110542  beq.b    $11050c
  00110544  moveq    #$5, d5
  00110546  cmp.l    d5, d1
  00110548  beq.w    $11045e
  0011054c  moveq    #$7, d6
  0011054e  cmp.l    d6, d1
  00110550  beq.w    $110186
  00110554  moveq    #$8, d7
  00110556  cmp.l    d7, d1
  00110558  beq.w    $11019c
  0011055c  moveq    #$9, d0
  0011055e  cmp.l    d0, d1
  00110560  beq.b    $1104ec
  00110562  moveq    #$f, d2
  00110564  cmp.l    d2, d1
  00110566  beq.w    $110436
  0011056a  bra.b    $11050c
  0011056c  beq.w    $110232
  00110570  moveq    #$11, d2
  00110572  cmp.l    d2, d1
  00110574  beq.w    $1101f8
  00110578  moveq    #$12, d3
  0011057a  cmp.l    d3, d1
  0011057c  beq.b    $11050c
  0011057e  moveq    #$13, d4
  00110580  cmp.l    d4, d1
  00110582  beq.w    $1103ea
  00110586  moveq    #$15, d5
  00110588  cmp.l    d5, d1
  0011058a  beq.w    $110476
  0011058e  moveq    #$16, d6
  00110590  cmp.l    d6, d1
  00110592  beq.w    $1101ca
  00110596  moveq    #$17, d7
  00110598  cmp.l    d7, d1
  0011059a  beq.w    $110142
  0011059e  bra.w    $11050c
  001105a2  beq.w    $110164
  001105a6  moveq    #$22, d2
  001105a8  cmp.l    d2, d1
  001105aa  bge.w    $1105e2
  001105ae  moveq    #$19, d3
  001105b0  cmp.l    d3, d1
  001105b2  beq.w    $1104c8
  001105b6  moveq    #$1a, d4
  001105b8  cmp.l    d4, d1
  001105ba  beq.w    $110498
  001105be  moveq    #$1b, d5
  001105c0  cmp.l    d5, d1
  001105c2  beq.w    $1104d8
  001105c6  moveq    #$1c, d6
  001105c8  cmp.l    d6, d1
  001105ca  beq.w    $110476
  001105ce  moveq    #$1d, d7
  001105d0  cmp.l    d7, d1
  001105d2  beq.w    $11028c
  001105d6  moveq    #$1f, d0
  001105d8  cmp.l    d0, d1
  001105da  beq.w    $11050c
  001105de  bra.w    $11050c
  001105e2  beq.w    $110476
  001105e6  moveq    #$52, d2
  001105e8  cmp.l    d2, d1
  001105ea  beq.w    $11035a
  001105ee  moveq    #$57, d3
  001105f0  cmp.l    d3, d1
  001105f2  beq.w    $110324
  001105f6  cmpi.l   #$3ec, d1
  001105fc  beq.w    $1102ae
  00110600  cmpi.l   #$3ed, d1
  00110606  beq.w    $1102bc
  0011060a  cmpi.l   #$3ee, d1
  00110610  beq.w    $1102f0
  00110614  cmpi.l   #$3ef, d1
  0011061a  beq.w    $1103c4
  0011061e  cmpi.l   #$3f0, d1
  00110624  beq.w    $110390
  00110628  bra.w    $11050c
  0011062c  bra.w    $110132
  * 00110630  dc.w     0x0852
  * 00110632  dc.w     0x414d
  00110634  movea.l  d4, a0
  * 00110636  dc.w     0x4953
  00110638  dc.w     $4b00
  0011063a  ori.b    #$0, d0
  0011063e  ori.w    #$2211, d4
  00110642  lsl.l    #$2, d1
  00110644  move.l   (a0, d1.l), $4(a1)
  0011064a  moveq    #$2, d2
  0011064c  cmp.l    $8(a0, d1.l), d2
  00110650  bne.w    $110664
  00110654  move.l   $c(a0, d1.l), d1
  00110658  moveq    #$14, d0
  0011065a  lea.l    $0(a4), a4
  0011065e  jsr      (a5)
  00110660  bra.w    $110674
  00110664  move.l   (a1), d1
  00110666  lsl.l    #$2, d1
  00110668  move.l   $c(a0, d1.l), d1
  0011066c  moveq    #$14, d0
  0011066e  movea.l  $148(a2), a4
  00110672  jsr      (a5)
  00110674  move.l   (a1), d1
  00110676  moveq    #$14, d0
  00110678  movea.l  $78(a2), a4
  0011067c  jsr      (a5)
  0011067e  move.l   $4(a1), (a1)
  00110682  tst.l    (a1)
  00110684  bne.b    $110640
  00110686  jmp      (a6)
  00110688  move.l   d1, d2
  0011068a  lsl.l    #$2, d2
  0011068c  moveq    #$19, d3
  0011068e  cmp.l    $8(a0, d2.l), d3
  00110692  bne.w    $11069e
  00110696  move.l   $14(a0, d2.l), d1
  0011069a  bra.w    $1106a6
  0011069e  move.l   (a1), d1
  001106a0  lsl.l    #$2, d1
  001106a2  move.l   $18(a0, d1.l), d1
  001106a6  move.l   d1, $4(a1)
  001106aa  moveq    #$52, d2
  001106ac  move.l   d2, $24(a1)
  001106b0  move.l   $268(a2), $28(a1)
  001106b6  move.l   $268(a2), $2c(a1)
  001106bc  move.l   #$1e8, $30(a1)
  001106c4  move.l   $278(a2), $34(a1)
  001106ca  move.l   $274(a2), $38(a1)
  001106d0  move.l   $258(a2), $3c(a1)
  001106d6  moveq    #$ff, d4
  001106d8  moveq    #$0, d3
  001106da  moveq    #$8, d2
  001106dc  moveq    #$14, d0
  001106de  lea.l    $1224(a4), a4
  001106e2  jsr      (a5)
  001106e4  moveq    #$0, d3
  001106e6  moveq    #$ff, d2
  001106e8  move.l   (a1), d1
  001106ea  moveq    #$14, d0
  001106ec  movea.l  $c4(a2), a4
  001106f0  jsr      (a5)
  001106f2  jmp      (a6)
  001106f4  move.l   d1, d2
  001106f6  lsl.l    #$2, d2
  001106f8  move.l   $14(a0, d2.l), $4(a1)
  001106fe  move.l   $4(a1), d1
  00110702  moveq    #$14, d0
  00110704  lea.l    $1044(a4), a4
  00110708  jsr      (a5)
  0011070a  move.l   d1, $8(a1)
  0011070e  tst.l    d1
  00110710  bne.w    $110718
  00110714  moveq    #$0, d1
  00110716  jmp      (a6)
  00110718  move.l   (a1), d1
  0011071a  lsl.l    #$2, d1
  0011071c  move.l   $8(a1), d2
  00110720  move.l   $18(a0, d1.l), d1
  00110724  moveq    #$18, d0
  00110726  lea.l    $ac(a4), a4
  0011072a  jsr      (a5)
  0011072c  jmp      (a6)
  0011072e  nop      
  00110730  move.l   d1, d2
  00110732  lsl.l    #$2, d2
  00110734  move.l   $14(a0, d2.l), $4(a1)
  0011073a  move.l   $18(a0, d2.l), $8(a1)
  00110740  move.l   $8(a1), d3
  00110744  lsl.l    #$2, d3
  00110746  move.l   (a0, d3.l), $c(a1)
  0011074c  move.l   $4(a1), d1
  00110750  moveq    #$1c, d0
  00110752  lea.l    $1008(a4), a4
  00110756  jsr      (a5)
  00110758  move.l   d1, $10(a1)
  0011075c  tst.l    d1
  0011075e  bne.w    $110766
  00110762  moveq    #$0, d1
  00110764  jmp      (a6)
  00110766  move.l   $8(a1), $20(a1)
  0011076c  move.l   $10(a1), d1
  00110770  cmp.l    $c(a1), d1
  00110774  bne.w    $110786
  00110778  move.l   $c(a1), d2
  0011077c  lsl.l    #$2, d2
  0011077e  move.l   $c(a0, d2.l), d1
  00110782  bra.w    $110790
  00110786  move.l   $c(a1), d1
  0011078a  lsl.l    #$2, d1
  0011078c  move.l   (a0, d1.l), d1
  00110790  move.l   d1, d2
  00110792  move.l   $20(a1), d1
  00110796  moveq    #$20, d0
  00110798  lea.l    $70(a4), a4
  0011079c  jsr      (a5)
  0011079e  jmp      (a6)
  001107a0  tst.l    d2
  001107a2  bne.w    $1107b2
  001107a6  move.l   #$e8, $26c(a2)
  001107ae  moveq    #$0, d1
  001107b0  jmp      (a6)
  001107b2  move.l   (a1), d1
  001107b4  lsl.l    #$2, d1
  001107b6  move.l   $4(a1), (a0, d1.l)
  001107bc  move.l   $4(a1), d1
  001107c0  lsl.l    #$2, d1
  001107c2  move.l   (a1), d2
  001107c4  lsl.l    #$2, d2
  001107c6  move.l   $8(a0, d1.l), $4(a0, d2.l)
  001107cc  moveq    #$9, d1
  001107ce  add.l    $4(a1), d1
  001107d2  moveq    #$2, d2
  001107d4  add.l    (a1), d2
  001107d6  moveq    #$14, d0
  001107d8  movea.l  $1cc(a2), a4
  001107dc  jsr      (a5)
  001107de  move.l   $4(a1), d1
  001107e2  lsl.l    #$2, d1
  001107e4  move.l   (a1), d2
  001107e6  lsl.l    #$2, d2
  001107e8  move.l   $14(a0, d1.l), $74(a0, d2.l)
  001107ee  move.l   $4(a1), d1
  001107f2  lsl.l    #$2, d1
  001107f4  move.l   (a1), d2
  001107f6  lsl.l    #$2, d2
  001107f8  move.l   $8(a0, d1.l), $78(a0, d2.l)
  001107fe  move.l   $4(a1), d1
  00110802  lsl.l    #$2, d1
  00110804  move.l   (a1), d2
  00110806  lsl.l    #$2, d2
  00110808  move.l   $10(a0, d1.l), $7c(a0, d2.l)
  0011080e  move.l   $4(a1), d1
  00110812  lsl.l    #$2, d1
  00110814  move.l   $10(a0, d1.l), d2
  00110818  moveq    #$9, d3
  0011081a  lsr.l    d3, d2
  0011081c  addq.l   #$1, d2
  0011081e  moveq    #$20, d4
  00110820  add.l    (a1), d4
  00110822  lsl.l    #$2, d4
  00110824  move.l   d2, (a0, d4.l)
  00110828  moveq    #$0, d1
  0011082a  move.l   d1, $8(a1)
  0011082e  moveq    #$2, d2
  00110830  cmp.l    d2, d1
  00110832  bgt.w    $110856
  00110836  moveq    #$6, d3
  00110838  add.l    $4(a1), d3
  0011083c  add.l    d1, d3
  0011083e  lsl.l    #$2, d3
  00110840  moveq    #$21, d4
  00110842  add.l    (a1), d4
  00110844  add.l    d1, d4
  00110846  lsl.l    #$2, d4
  00110848  move.l   (a0, d3.l), (a0, d4.l)
  0011084e  moveq    #$1, d1
  00110850  add.l    $8(a1), d1
  00110854  bra.b    $11082a
  00110856  moveq    #$19, d1
  00110858  add.l    $4(a1), d1
  0011085c  moveq    #$24, d2
  0011085e  add.l    (a1), d2
  00110860  moveq    #$14, d0
  00110862  movea.l  $1cc(a2), a4
  00110866  jsr      (a5)
  00110868  moveq    #$ff, d1
  0011086a  jmp      (a6)
  0011086c  moveq    #$7b, d2
  0011086e  cmp.l    d1, d2
  00110870  bne.w    $1108a2
  00110874  move.l   #$20001, d3
  0011087a  move.l   $18(a1), d2
  0011087e  move.l   #$ffffff28, d1
  00110884  moveq    #$14, d0
  00110886  movea.l  $160(a2), a4
  0011088a  jsr      (a5)
  0011088c  cmpi.l   #$7800, d1
  00110892  bge.w    $1108a2
  00110896  move.l   #$dd, $26c(a2)
  0011089e  moveq    #$0, d1
  001108a0  jmp      (a6)
  001108a2  move.l   (a1), d1
  001108a4  moveq    #$14, d0
  001108a6  movea.l  $74(a2), a4
  001108aa  jsr      (a5)
  001108ac  move.l   d1, $4(a1)
  001108b0  tst.l    d1
  001108b2  bne.w    $1108be
  001108b6  move.l   #$dd, $26c(a2)
  001108be  move.l   $4(a1), d1
  001108c2  jmp      (a6)
  001108c4  moveq    #$18, d3
  001108c6  add.l    a1, d3
  001108c8  lsr.l    #$2, d3
  001108ca  move.l   d3, $14(a1)
  001108ce  moveq    #$3c, d4
  001108d0  add.l    a1, d4
  001108d2  lsr.l    #$2, d4
  001108d4  move.l   d4, $38(a1)
  001108d8  moveq    #$ff, d5
  001108da  move.l   d5, $90(a1)
  001108de  move.l   #$a0, d0
  001108e4  lea.l    $e74(a4), a4
  001108e8  jsr      (a5)
  001108ea  move.l   d1, $8(a1)
  001108ee  tst.l    d1
  001108f0  bne.w    $1108f8
  001108f4  moveq    #$0, d1
  001108f6  jmp      (a6)
  001108f8  move.l   $14(a1), d3
  001108fc  move.l   $4(a1), d2
  00110900  move.l   $8(a1), d1
  00110904  move.l   #$a0, d0
  0011090a  lea.l    $1dc(a4), a4
  0011090e  jsr      (a5)
  00110910  move.l   d1, $8(a1)
  00110914  tst.l    d1
  00110916  bne.w    $11091e
  0011091a  moveq    #$0, d1
  0011091c  jmp      (a6)
  0011091e  move.l   $14(a1), d1
  00110922  move.l   #$a0, d0
  00110928  lea.l    $318(a4), a4
  0011092c  jsr      (a5)
  0011092e  tst.l    d1
  00110930  bne.w    $110938
  00110934  moveq    #$0, d1
  00110936  jmp      (a6)
  00110938  move.l   $14(a1), d2
  0011093c  move.l   $8(a1), d1
  00110940  move.l   #$a0, d0
  00110946  lea.l    $288(a4), a4
  0011094a  jsr      (a5)
  0011094c  tst.l    d1
  0011094e  beq.w    $11096c
  00110952  moveq    #$19, d1
  00110954  add.l    $260(a2), d1
  00110958  move.l   $38(a1), d2
  0011095c  move.l   #$a0, d0
  00110962  movea.l  $1cc(a2), a4
  00110966  jsr      (a5)
  00110968  bra.w    $110970
  0011096c  clr.l    $90(a1)
  00110970  move.l   $14(a1), d2
  00110974  move.l   $8(a1), d1
  00110978  move.l   #$a0, d0
  0011097e  lea.l    $afc(a4), a4
  00110982  jsr      (a5)
  00110984  tst.l    d1
  00110986  bne.w    $11099a
  0011098a  cmpi.l   #$cd, $26c(a2)
  00110992  beq.w    $11099a
  00110996  moveq    #$0, d1
  00110998  jmp      (a6)
  0011099a  moveq    #$2d, d1
  0011099c  move.l   #$a0, d0
  001109a2  lea.l    -$58(a4), a4
  001109a6  jsr      (a5)
  001109a8  move.l   d1, $c(a1)
  001109ac  tst.l    d1
  001109ae  bne.w    $1109b6
  001109b2  moveq    #$0, d1
  001109b4  jmp      (a6)
  001109b6  addq.l   #$1, $268(a2)
  001109ba  move.l   $8(a1), d1
  001109be  lsl.l    #$2, d1
  001109c0  moveq    #$2, d2
  001109c2  move.l   d2, $b0(a1)
  001109c6  clr.l    $b4(a1)
  001109ca  clr.l    $b8(a1)
  001109ce  clr.l    $bc(a1)
  001109d2  move.l   $8(a1), d4
  001109d6  move.l   $c(a0, d1.l), d3
  001109da  moveq    #$5, d2
  001109dc  move.l   $c(a1), d1
  001109e0  move.l   #$a0, d0
  001109e6  lea.l    $fe8(a4), a4
  001109ea  jsr      (a5)
  001109ec  move.l   $8(a1), d2
  001109f0  lsl.l    #$2, d2
  001109f2  move.l   d1, $c(a0, d2.l)
  001109f6  tst.l    $90(a1)
  001109fa  beq.w    $110a1a
  001109fe  moveq    #$19, d1
  00110a00  add.l    $c(a1), d1
  00110a04  move.l   d1, d2
  00110a06  move.l   $38(a1), d1
  00110a0a  move.l   #$a0, d0
  00110a10  movea.l  $1cc(a2), a4
  00110a14  jsr      (a5)
  00110a16  bra.w    $110a2e
  00110a1a  moveq    #$19, d1
  00110a1c  add.l    $c(a1), d1
  00110a20  moveq    #$14, d2
  00110a22  move.l   #$a0, d0
  00110a28  movea.l  -$50(a2), a4
  00110a2c  jsr      (a5)
  00110a2e  moveq    #$6, d1
  00110a30  add.l    $25c(a2), d1
  00110a34  move.l   #$a0, d0
  00110a3a  movea.l  $158(a2), a4
  00110a3e  jsr      (a5)
  00110a40  moveq    #$6, d1
  00110a42  add.l    $c(a1), d1
  00110a46  move.l   #$a0, d0
  00110a4c  movea.l  $158(a2), a4
  00110a50  jsr      (a5)
  00110a52  move.l   $c(a1), d1
  00110a56  lsl.l    #$2, d1
  00110a58  tst.l    $4(a0, d1.l)
  00110a5c  beq.w    $110a74
  00110a60  moveq    #$6, d2
  00110a62  add.l    $4(a0, d1.l), d2
  00110a66  move.l   d2, d1
  00110a68  move.l   #$a0, d0
  00110a6e  movea.l  $158(a2), a4
  00110a72  jsr      (a5)
  00110a74  moveq    #$9, d1
  00110a76  add.l    $c(a1), d1
  00110a7a  move.l   d1, d2
  00110a7c  move.l   $14(a1), d1
  00110a80  move.l   #$a0, d0
  00110a86  movea.l  $1cc(a2), a4
  00110a8a  jsr      (a5)
  00110a8c  moveq    #$ff, d2
  00110a8e  move.l   $c(a1), d1
  00110a92  move.l   #$a0, d0
  00110a98  lea.l    $ec8(a4), a4
  00110a9c  jsr      (a5)
  00110a9e  jmp      (a6)
  00110aa0  moveq    #$1, d4
  00110aa2  move.l   d2, d3
  00110aa4  moveq    #$3a, d2
  00110aa6  move.l   $8(a1), d1
  00110aaa  moveq    #$18, d0
  00110aac  movea.l  $1ac(a2), a4
  00110ab0  jsr      (a5)
  00110ab2  move.l   d1, $c(a1)
  00110ab6  tst.l    d1
  00110ab8  bne.w    $110ac2
  00110abc  moveq    #$1, d2
  00110abe  move.l   d2, $c(a1)
  00110ac2  move.l   $c(a1), d4
  00110ac6  move.l   $4(a1), d3
  00110aca  moveq    #$2f, d2
  00110acc  move.l   $8(a1), d1
  00110ad0  moveq    #$20, d0
  00110ad2  movea.l  $1ac(a2), a4
  00110ad6  jsr      (a5)
  00110ad8  move.l   d1, $10(a1)
  00110adc  tst.l    d1
  00110ade  bne.w    $110ae6
  00110ae2  move.l   (a1), d1
  00110ae4  jmp      (a6)
  00110ae6  moveq    #$1, d1
  00110ae8  add.l    $c(a1), d1
  00110aec  cmp.l    $10(a1), d1
  00110af0  bne.w    $110b26
  00110af4  move.l   (a1), d1
  00110af6  lsl.l    #$2, d1
  00110af8  move.l   $4(a0, d1.l), (a1)
  00110afc  tst.l    (a1)
  00110afe  bne.w    $110b06
  00110b02  moveq    #$0, d1
  00110b04  jmp      (a6)
  00110b06  move.l   $4(a1), d1
  00110b0a  lsl.l    #$2, d1
  00110b0c  moveq    #$0, d2
  00110b0e  move.b   (a0, d1.l), d2
  00110b12  cmp.l    $c(a1), d2
  00110b16  bne.w    $110b1e
  00110b1a  move.l   (a1), d1
  00110b1c  jmp      (a6)
  00110b1e  move.l   $10(a1), $c(a1)
  00110b24  bra.b    $110ac2
  00110b26  move.l   $10(a1), $c(a1)
  00110b2c  move.l   $8(a1), d2
  00110b30  move.l   (a1), d1
  00110b32  moveq    #$20, d0
  00110b34  lea.l    $ac(a4), a4
  00110b38  jsr      (a5)
  00110b3a  tst.l    d1
  00110b3c  bne.w    $110b44
  00110b40  moveq    #$0, d1
  00110b42  jmp      (a6)
  00110b44  move.l   $260(a2), (a1)
  00110b48  bra.w    $110ac2
  00110b4c  tst.l    d1
  00110b4e  beq.w    $110b60
  00110b52  move.l   d1, d3
  00110b54  lsl.l    #$2, d3
  00110b56  moveq    #$2, d4
  00110b58  cmp.l    $8(a0, d3.l), d4
  00110b5c  beq.w    $110b7e
  00110b60  tst.l    (a1)
  00110b62  bne.w    $110b70
  00110b66  move.l   #$cd, d1
  00110b6c  bra.w    $110b76
  00110b70  move.l   #$d4, d1
  00110b76  move.l   d1, $26c(a2)
  00110b7a  moveq    #$0, d1
  00110b7c  jmp      (a6)
  00110b7e  moveq    #$3, d1
  00110b80  add.l    (a1), d1
  00110b82  move.l   d1, $264(a2)
  00110b86  move.l   (a1), d2
  00110b88  lsl.l    #$2, d2
  00110b8a  move.l   $c(a0, d2.l), $260(a2)
  00110b90  bra.w    $110bc4
  00110b94  moveq    #$9, d1
  00110b96  add.l    $260(a2), d1
  00110b9a  move.l   d1, d2
  00110b9c  move.l   $4(a1), d1
  00110ba0  moveq    #$14, d0
  00110ba2  movea.l  $134(a2), a4
  00110ba6  jsr      (a5)
  00110ba8  tst.l    d1
  00110baa  bne.w    $110bb2
  00110bae  moveq    #$ff, d1
  00110bb0  jmp      (a6)
  00110bb2  move.l   $260(a2), $264(a2)
  00110bb8  move.l   $260(a2), d1
  00110bbc  lsl.l    #$2, d1
  00110bbe  move.l   (a0, d1.l), $260(a2)
  00110bc4  tst.l    $260(a2)
  00110bc8  bne.b    $110b94
  00110bca  clr.l    $260(a2)
  00110bce  move.l   #$cd, $26c(a2)
  00110bd6  moveq    #$0, d1
  00110bd8  jmp      (a6)
  00110bda  nop      
  00110bdc  move.l   d1, d2
  00110bde  lsl.l    #$2, d2
  00110be0  moveq    #$0, d3
  00110be2  move.b   (a0, d2.l), d3
  00110be6  move.l   d3, $4(a1)
  00110bea  move.l   #$d2, $26c(a2)
  00110bf2  moveq    #$1, d4
  00110bf4  cmp.l    d3, d4
  00110bf6  bgt.w    $110c02
  00110bfa  moveq    #$1e, d5
  00110bfc  cmp.l    d5, d3
  00110bfe  ble.w    $110c06
  00110c02  moveq    #$0, d1
  00110c04  jmp      (a6)
  00110c06  move.l   $4(a1), $8(a1)
  00110c0c  moveq    #$1, d1
  00110c0e  move.l   d1, $c(a1)
  00110c12  cmp.l    $8(a1), d1
  00110c16  bgt.w    $110c5c
  00110c1a  move.l   (a1), d2
  00110c1c  lsl.l    #$2, d2
  00110c1e  add.l    d1, d2
  00110c20  moveq    #$0, d3
  00110c22  move.b   (a0, d2.l), d3
  00110c26  move.l   d3, d1
  00110c28  moveq    #$1c, d0
  00110c2a  movea.l  $12c(a2), a4
  00110c2e  jsr      (a5)
  00110c30  moveq    #$7f, d2
  00110c32  and.l    d2, d1
  00110c34  move.l   d1, $10(a1)
  00110c38  moveq    #$20, d3
  00110c3a  cmp.l    d3, d1
  00110c3c  blt.w    $110c50
  00110c40  moveq    #$2f, d4
  00110c42  cmp.l    d1, d4
  00110c44  beq.w    $110c50
  00110c48  moveq    #$3a, d5
  00110c4a  cmp.l    d1, d5
  00110c4c  bne.w    $110c54
  00110c50  moveq    #$0, d1
  00110c52  jmp      (a6)
  00110c54  moveq    #$1, d1
  00110c56  add.l    $c(a1), d1
  00110c5a  bra.b    $110c0e
  00110c5c  moveq    #$ff, d1
  00110c5e  jmp      (a6)
  00110c60  moveq    #$14, d0
  00110c62  lea.l    $ad8(a4), a4
  00110c66  jsr      (a5)
  00110c68  move.l   d1, $8(a1)
  00110c6c  moveq    #$18, d2
  00110c6e  add.l    a1, d2
  00110c70  lsr.l    #$2, d2
  00110c72  move.l   d2, $14(a1)
  00110c76  tst.l    d1
  00110c78  bne.w    $110c80
  00110c7c  moveq    #$0, d1
  00110c7e  jmp      (a6)
  00110c80  moveq    #$1, d4
  00110c82  move.l   $4(a1), d3
  00110c86  moveq    #$3a, d2
  00110c88  move.l   $14(a1), d1
  00110c8c  moveq    #$44, d0
  00110c8e  movea.l  $1ac(a2), a4
  00110c92  jsr      (a5)
  00110c94  move.l   $4(a1), d2
  00110c98  lsl.l    #$2, d2
  00110c9a  moveq    #$0, d3
  00110c9c  move.b   (a0, d2.l), d3
  00110ca0  addq.l   #$1, d3
  00110ca2  cmp.l    d3, d1
  00110ca4  beq.w    $110d04
  00110ca8  move.l   $14(a1), d3
  00110cac  move.l   $4(a1), d2
  00110cb0  move.l   $8(a1), d1
  00110cb4  moveq    #$44, d0
  00110cb6  lea.l    -$1c0(a4), a4
  00110cba  jsr      (a5)
  00110cbc  move.l   d1, $8(a1)
  00110cc0  tst.l    d1
  00110cc2  bne.w    $110cd2
  00110cc6  move.l   #$cd, $26c(a2)
  00110cce  moveq    #$0, d1
  00110cd0  jmp      (a6)
  00110cd2  move.l   $14(a1), d1
  00110cd6  lsl.l    #$2, d1
  00110cd8  moveq    #$0, d2
  00110cda  move.b   (a0, d1.l), d2
  00110cde  tst.l    d2
  00110ce0  beq.w    $110d04
  00110ce4  move.l   $14(a1), d2
  00110ce8  move.l   $8(a1), d1
  00110cec  moveq    #$44, d0
  00110cee  lea.l    -$114(a4), a4
  00110cf2  jsr      (a5)
  00110cf4  tst.l    d1
  00110cf6  bne.w    $110cfe
  00110cfa  moveq    #$0, d1
  00110cfc  jmp      (a6)
  00110cfe  move.l   $260(a2), $8(a1)
  00110d04  moveq    #$fe, d2
  00110d06  move.l   $8(a1), d1
  00110d0a  moveq    #$44, d0
  00110d0c  lea.l    $b2c(a4), a4
  00110d10  jsr      (a5)
  00110d12  jmp      (a6)
  00110d14  move.l   d3, d2
  00110d16  move.l   $4(a1), d1
  00110d1a  moveq    #$20, d0
  00110d1c  lea.l    -$450(a4), a4
  00110d20  jsr      (a5)
  00110d22  move.l   d1, $c(a1)
  00110d26  tst.l    d1
  00110d28  bne.w    $110d30
  00110d2c  moveq    #$0, d1
  00110d2e  jmp      (a6)
  00110d30  move.l   $c(a1), d1
  00110d34  lsl.l    #$2, d1
  00110d36  move.l   $4(a0, d1.l), $10(a1)
  00110d3c  move.l   $10(a1), d2
  00110d40  lsl.l    #$2, d2
  00110d42  moveq    #$fd, d3
  00110d44  move.l   d3, $8(a0, d2.l)
  00110d48  move.l   $c(a1), d1
  00110d4c  lsl.l    #$2, d1
  00110d4e  clr.l    $14(a0, d1.l)
  00110d52  move.l   $c(a1), d1
  00110d56  lsl.l    #$2, d1
  00110d58  moveq    #$8, d2
  00110d5a  move.l   d2, $18(a0, d1.l)
  00110d5e  move.l   $c(a1), d1
  00110d62  lsl.l    #$2, d1
  00110d64  clr.l    $1c(a0, d1.l)
  00110d68  move.l   (a1), d1
  00110d6a  lsl.l    #$2, d1
  00110d6c  move.l   $c(a1), $24(a0, d1.l)
  00110d72  moveq    #$6, d1
  00110d74  add.l    $25c(a2), d1
  00110d78  moveq    #$20, d0
  00110d7a  movea.l  $158(a2), a4
  00110d7e  jsr      (a5)
  00110d80  moveq    #$ff, d1
  00110d82  jmp      (a6)
  00110d84  move.l   d3, d2
  00110d86  move.l   $4(a1), d1
  00110d8a  moveq    #$18, d0
  00110d8c  lea.l    -$124(a4), a4
  00110d90  jsr      (a5)
  00110d92  move.l   d1, $c(a1)
  00110d96  tst.l    d1
  00110d98  bne.w    $110da0
  00110d9c  moveq    #$0, d1
  00110d9e  jmp      (a6)
  00110da0  move.l   $c(a1), d1
  00110da4  lsl.l    #$2, d1
  00110da6  move.l   $4(a0, d1.l), $10(a1)
  00110dac  move.l   $10(a1), d2
  00110db0  lsl.l    #$2, d2
  00110db2  moveq    #$fd, d3
  00110db4  cmp.l    $8(a0, d2.l), d3
  00110db8  beq.w    $110dd4
  00110dbc  move.l   $c(a1), d1
  00110dc0  moveq    #$20, d0
  00110dc2  lea.l    $aac(a4), a4
  00110dc6  jsr      (a5)
  00110dc8  move.l   #$d4, $26c(a2)
  00110dd0  moveq    #$0, d1
  00110dd2  jmp      (a6)
  00110dd4  move.l   $10(a1), d1
  00110dd8  lsl.l    #$2, d1
  00110dda  move.l   $c(a1), d2
  00110dde  lsl.l    #$2, d2
  00110de0  move.l   $c(a0, d1.l), $14(a0, d2.l)
  00110de6  move.l   $c(a1), d1
  00110dea  lsl.l    #$2, d1
  00110dec  moveq    #$8, d2
  00110dee  move.l   d2, $18(a0, d1.l)
  00110df2  move.l   $c(a1), d1
  00110df6  lsl.l    #$2, d1
  00110df8  clr.l    $1c(a0, d1.l)
  00110dfc  move.l   (a1), d1
  00110dfe  lsl.l    #$2, d1
  00110e00  move.l   $c(a1), $24(a0, d1.l)
  00110e06  moveq    #$ff, d1
  00110e08  jmp      (a6)
  00110e0a  nop      
  00110e0c  move.l   d1, d5
  00110e0e  lsl.l    #$2, d5
  00110e10  move.l   $4(a0, d5.l), $10(a1)
  00110e16  move.l   $14(a0, d5.l), $14(a1)
  00110e1c  move.l   $18(a0, d5.l), $18(a1)
  00110e22  move.l   $1c(a0, d5.l), $1c(a1)
  00110e28  tst.l    $14(a1)
  00110e2c  bne.w    $110e36
  00110e30  moveq    #$0, d1
  00110e32  bra.w    $110e52
  00110e36  tst.l    $c(a1)
  00110e3a  beq.w    $110e4c
  00110e3e  move.l   $14(a1), d1
  00110e42  lsl.l    #$2, d1
  00110e44  move.l   $4(a0, d1.l), d1
  00110e48  bra.w    $110e52
  00110e4c  move.l   #$1ef, d1
  00110e52  move.l   d1, $20(a1)
  00110e56  clr.l    $24(a1)
  00110e5a  clr.l    $26c(a2)
  00110e5e  bra.w    $110ffa
  00110e62  move.l   $18(a1), d1
  00110e66  move.l   $20(a1), d2
  00110e6a  sub.l    d1, d2
  00110e6c  addq.l   #$1, d2
  00110e6e  move.l   d2, $28(a1)
  00110e72  move.l   $24(a1), d3
  00110e76  move.l   $8(a1), d4
  00110e7a  sub.l    d3, d4
  00110e7c  move.l   d4, $2c(a1)
  00110e80  tst.l    d2
  00110e82  bgt.w    $110f58
  00110e86  tst.l    $14(a1)
  00110e8a  bne.w    $110e94
  00110e8e  moveq    #$0, d1
  00110e90  bra.w    $110e9e
  00110e94  move.l   $14(a1), d1
  00110e98  lsl.l    #$2, d1
  00110e9a  move.l   (a0, d1.l), d1
  00110e9e  move.l   d1, $34(a1)
  00110ea2  tst.l    d1
  00110ea4  bne.w    $110f24
  00110ea8  tst.l    $c(a1)
  00110eac  bne.w    $111006
  00110eb0  moveq    #$7b, d1
  00110eb2  moveq    #$48, d0
  00110eb4  lea.l    -$5a0(a4), a4
  00110eb8  jsr      (a5)
  00110eba  move.l   d1, $34(a1)
  00110ebe  tst.l    d1
  00110ec0  bne.w    $110ec8
  00110ec4  moveq    #$ff, d1
  00110ec6  jmp      (a6)
  00110ec8  cmpi.l   #$1e8, $2c(a1)
  00110ed0  bge.w    $110edc
  00110ed4  move.l   $2c(a1), d1
  00110ed8  bra.w    $110ee2
  00110edc  move.l   #$1e8, d1
  00110ee2  move.l   d1, $38(a1)
  00110ee6  move.l   $34(a1), d2
  00110eea  lsl.l    #$2, d2
  00110eec  clr.l    (a0, d2.l)
  00110ef0  move.l   $34(a1), d1
  00110ef4  lsl.l    #$2, d1
  00110ef6  moveq    #$7, d2
  00110ef8  move.l   d2, $4(a0, d1.l)
  00110efc  tst.l    $14(a1)
  00110f00  bne.w    $110f14
  00110f04  move.l   $10(a1), d1
  00110f08  lsl.l    #$2, d1
  00110f0a  move.l   $34(a1), $c(a0, d1.l)
  00110f10  bra.w    $110f20
  00110f14  move.l   $14(a1), d1
  00110f18  lsl.l    #$2, d1
  00110f1a  move.l   $34(a1), (a0, d1.l)
  00110f20  addq.l   #$1, $268(a2)
  00110f24  move.l   $34(a1), $14(a1)
  00110f2a  tst.l    $c(a1)
  00110f2e  beq.w    $110f40
  00110f32  move.l   $14(a1), d1
  00110f36  lsl.l    #$2, d1
  00110f38  move.l   $4(a0, d1.l), d1
  00110f3c  bra.w    $110f46
  00110f40  move.l   #$1ef, d1
  00110f46  move.l   d1, $20(a1)
  00110f4a  moveq    #$8, d2
  00110f4c  move.l   d2, $18(a1)
  00110f50  sub.l    d2, d1
  00110f52  addq.l   #$1, d1
  00110f54  move.l   d1, $28(a1)
  00110f58  move.l   $2c(a1), d1
  00110f5c  cmp.l    $28(a1), d1
  00110f60  ble.w    $110f6c
  00110f64  move.l   $28(a1), d1
  00110f68  bra.w    $110f70
  00110f6c  move.l   $2c(a1), d1
  00110f70  move.l   d1, $30(a1)
  00110f74  tst.l    $c(a1)
  00110f78  beq.w    $110fa8
  00110f7c  move.l   $14(a1), d2
  00110f80  lsl.l    #$2, d2
  00110f82  add.l    $18(a1), d2
  00110f86  move.l   $4(a1), d3
  00110f8a  add.l    $24(a1), d3
  00110f8e  move.l   d2, d1
  00110f90  move.l   d3, $44(a1)
  00110f94  move.l   $30(a1), d3
  00110f98  move.l   $44(a1), d2
  00110f9c  moveq    #$40, d0
  00110f9e  movea.l  $270(a2), a4
  00110fa2  jsr      (a5)
  00110fa4  bra.w    $110fc6
  00110fa8  move.l   $4(a1), d1
  00110fac  add.l    $24(a1), d1
  00110fb0  move.l   $14(a1), d2
  00110fb4  lsl.l    #$2, d2
  00110fb6  add.l    $18(a1), d2
  00110fba  move.l   $30(a1), d3
  00110fbe  moveq    #$40, d0
  00110fc0  movea.l  $270(a2), a4
  00110fc4  jsr      (a5)
  00110fc6  move.l   $30(a1), d1
  00110fca  add.l    d1, $24(a1)
  00110fce  add.l    d1, $18(a1)
  00110fd2  add.l    d1, $1c(a1)
  00110fd6  tst.l    $c(a1)
  00110fda  bne.w    $110ffa
  00110fde  move.l   $14(a1), d2
  00110fe2  lsl.l    #$2, d2
  00110fe4  move.l   $4(a0, d2.l), d3
  00110fe8  cmp.l    $18(a1), d3
  00110fec  bge.w    $110ffa
  00110ff0  move.l   $18(a1), d3
  00110ff4  subq.l   #$1, d3
  00110ff6  move.l   d3, $4(a0, d2.l)
  00110ffa  move.l   $8(a1), d1
  00110ffe  cmp.l    $24(a1), d1
  00111002  bgt.w    $110e62
  00111006  move.l   (a1), d1
  00111008  lsl.l    #$2, d1
  0011100a  move.l   $14(a1), $14(a0, d1.l)
  00111010  move.l   (a1), d1
  00111012  lsl.l    #$2, d1
  00111014  move.l   $18(a1), $18(a0, d1.l)
  0011101a  move.l   (a1), d1
  0011101c  lsl.l    #$2, d1
  0011101e  move.l   $1c(a1), $1c(a0, d1.l)
  00111024  tst.l    $c(a1)
  00111028  bne.w    $111044
  0011102c  move.l   $10(a1), d1
  00111030  lsl.l    #$2, d1
  00111032  move.l   $10(a0, d1.l), d2
  00111036  cmp.l    $1c(a1), d2
  0011103a  bge.w    $111044
  0011103e  move.l   $1c(a1), $10(a0, d1.l)
  00111044  move.l   $24(a1), d1
  00111048  jmp      (a6)
  0011104a  nop      
  0011104c  move.l   d1, d4
  0011104e  lsl.l    #$2, d4
  00111050  move.l   $4(a0, d4.l), $c(a1)
  00111056  move.l   $14(a0, d4.l), $10(a1)
  0011105c  move.l   $18(a0, d4.l), $14(a1)
  00111062  move.l   $c(a1), d5
  00111066  lsl.l    #$2, d5
  00111068  move.l   $c(a0, d5.l), $18(a1)
  0011106e  clr.l    $1c(a1)
  00111072  clr.l    $20(a1)
  00111076  bra.w    $111096
  0011107a  move.l   $18(a1), d1
  0011107e  lsl.l    #$2, d1
  00111080  move.l   $1c(a1), d2
  00111084  add.l    $4(a0, d1.l), d2
  00111088  addq.l   #$1, d2
  0011108a  subq.l   #$8, d2
  0011108c  move.l   d2, $1c(a1)
  00111090  move.l   (a0, d1.l), $18(a1)
  00111096  move.l   $18(a1), d1
  0011109a  cmp.l    $10(a1), d1
  0011109e  bne.b    $11107a
  001110a0  move.l   $1c(a1), d2
  001110a4  add.l    $14(a1), d2
  001110a8  subq.l   #$8, d2
  001110aa  move.l   d2, $1c(a1)
  001110ae  tst.l    $8(a1)
  001110b2  bne.w    $1110ba
  001110b6  add.l    d2, $4(a1)
  001110ba  tst.l    $8(a1)
  001110be  ble.w    $1110d0
  001110c2  move.l   $c(a1), d1
  001110c6  lsl.l    #$2, d1
  001110c8  move.l   $10(a0, d1.l), d2
  001110cc  add.l    d2, $4(a1)
  001110d0  tst.l    $8(a1)
  001110d4  bge.w    $1110ec
  001110d8  tst.l    $4(a1)
  001110dc  bge.w    $1110ec
  001110e0  move.l   #$db, $26c(a2)
  001110e8  moveq    #$ff, d1
  001110ea  jmp      (a6)
  001110ec  move.l   $c(a1), d1
  001110f0  lsl.l    #$2, d1
  001110f2  move.l   $10(a0, d1.l), d2
  001110f6  cmp.l    $4(a1), d2
  001110fa  bge.w    $11110a
  001110fe  move.l   #$db, $26c(a2)
  00111106  moveq    #$ff, d1
  00111108  jmp      (a6)
  0011110a  tst.l    $4(a1)
  0011110e  bne.w    $111124
  00111112  move.l   $c(a1), d1
  00111116  lsl.l    #$2, d1
  00111118  tst.l    $10(a0, d1.l)
  0011111c  bne.w    $111124
  00111120  moveq    #$0, d1
  00111122  jmp      (a6)
  00111124  move.l   $c(a1), d1
  00111128  lsl.l    #$2, d1
  0011112a  move.l   $c(a0, d1.l), $18(a1)
  00111130  tst.l    $18(a1)
  00111134  bne.w    $111144
  00111138  move.l   #$db, $26c(a2)
  00111140  moveq    #$ff, d1
  00111142  jmp      (a6)
  00111144  move.l   $18(a1), d1
  00111148  lsl.l    #$2, d1
  0011114a  move.l   $20(a1), d2
  0011114e  add.l    $4(a0, d1.l), d2
  00111152  addq.l   #$1, d2
  00111154  subq.l   #$8, d2
  00111156  move.l   d2, $24(a1)
  0011115a  cmp.l    $4(a1), d2
  0011115e  bge.w    $11116e
  00111162  move.l   d2, $20(a1)
  00111166  move.l   (a0, d1.l), $18(a1)
  0011116c  bra.b    $111130
  0011116e  move.l   (a1), d1
  00111170  lsl.l    #$2, d1
  00111172  move.l   $18(a1), $14(a0, d1.l)
  00111178  move.l   $20(a1), d1
  0011117c  move.l   $4(a1), d2
  00111180  sub.l    d1, d2
  00111182  addq.l   #$8, d2
  00111184  move.l   (a1), d3
  00111186  lsl.l    #$2, d3
  00111188  move.l   d2, $18(a0, d3.l)
  0011118c  move.l   (a1), d1
  0011118e  lsl.l    #$2, d1
  00111190  move.l   $4(a1), $1c(a0, d1.l)
  00111196  move.l   $1c(a1), d1
  0011119a  jmp      (a6)
  0011119c  moveq    #$14, d5
  0011119e  add.l    a1, d5
  001111a0  lsr.l    #$2, d5
  001111a2  move.l   d5, $10(a1)
  001111a6  moveq    #$38, d6
  001111a8  add.l    a1, d6
  001111aa  lsr.l    #$2, d6
  001111ac  move.l   d6, $34(a1)
  001111b0  moveq    #$64, d0
  001111b2  lea.l    $59c(a4), a4
  001111b6  jsr      (a5)
  001111b8  move.l   d1, $58(a1)
  001111bc  tst.l    d1
  001111be  bne.w    $1111c6
  001111c2  moveq    #$0, d1
  001111c4  jmp      (a6)
  001111c6  move.l   $8(a1), d1
  001111ca  moveq    #$7c, d0
  001111cc  lea.l    $59c(a4), a4
  001111d0  jsr      (a5)
  001111d2  move.l   d1, $5c(a1)
  001111d6  tst.l    d1
  001111d8  bne.w    $1111e0
  001111dc  moveq    #$0, d1
  001111de  jmp      (a6)
  001111e0  move.l   $34(a1), d3
  001111e4  move.l   $4(a1), d2
  001111e8  move.l   $58(a1), d1
  001111ec  moveq    #$7c, d0
  001111ee  lea.l    -$6fc(a4), a4
  001111f2  jsr      (a5)
  001111f4  move.l   d1, $58(a1)
  001111f8  move.l   $34(a1), d2
  001111fc  moveq    #$7c, d0
  001111fe  lea.l    -$650(a4), a4
  00111202  jsr      (a5)
  00111204  tst.l    d1
  00111206  bne.w    $11120e
  0011120a  moveq    #$0, d1
  0011120c  jmp      (a6)
  0011120e  move.l   $260(a2), $64(a1)
  00111214  move.l   $10(a1), d3
  00111218  move.l   $c(a1), d2
  0011121c  move.l   $5c(a1), d1
  00111220  moveq    #$7c, d0
  00111222  lea.l    -$6fc(a4), a4
  00111226  jsr      (a5)
  00111228  move.l   d1, $5c(a1)
  0011122c  tst.l    d1
  0011122e  bne.w    $111236
  00111232  moveq    #$0, d1
  00111234  jmp      (a6)
  00111236  moveq    #$0, d1
  00111238  move.l   $58(a1), d2
  0011123c  cmp.l    $5c(a1), d2
  00111240  bne.b    $111244
  00111242  not.l    d1
  00111244  move.l   d1, $70(a1)
  00111248  move.l   $10(a1), d2
  0011124c  move.l   $34(a1), d1
  00111250  move.l   #$80, d0
  00111256  movea.l  $134(a2), a4
  0011125a  jsr      (a5)
  0011125c  moveq    #$0, d2
  0011125e  cmp.l    d2, d1
  00111260  bne.b    $111264
  00111262  not.l    d2
  00111264  and.l    $70(a1), d2
  00111268  move.l   d2, $6c(a1)
  0011126c  tst.l    d2
  0011126e  bne.w    $111294
  00111272  move.l   $10(a1), d2
  00111276  move.l   $5c(a1), d1
  0011127a  moveq    #$7c, d0
  0011127c  lea.l    -$650(a4), a4
  00111280  jsr      (a5)
  00111282  tst.l    d1
  00111284  beq.w    $111294
  00111288  move.l   #$cb, $26c(a2)
  00111290  moveq    #$0, d1
  00111292  jmp      (a6)
  00111294  move.l   $5c(a1), d1
  00111298  lsl.l    #$2, d1
  0011129a  moveq    #$fd, d2
  0011129c  cmp.l    $8(a0, d1.l), d2
  001112a0  bne.w    $1112b0
  001112a4  move.l   #$d4, $26c(a2)
  001112ac  moveq    #$0, d1
  001112ae  jmp      (a6)
  001112b0  moveq    #$fe, d2
  001112b2  move.l   $64(a1), d1
  001112b6  moveq    #$7c, d0
  001112b8  lea.l    $5f0(a4), a4
  001112bc  jsr      (a5)
  001112be  move.l   d1, $68(a1)
  001112c2  tst.l    d1
  001112c4  bne.w    $1112cc
  001112c8  moveq    #$0, d1
  001112ca  jmp      (a6)
  001112cc  move.l   $10(a1), d1
  001112d0  moveq    #$7c, d0
  001112d2  lea.l    -$5c0(a4), a4
  001112d6  jsr      (a5)
  001112d8  tst.l    d1
  001112da  bne.w    $1112ee
  001112de  move.l   $68(a1), d1
  001112e2  moveq    #$7c, d0
  001112e4  lea.l    $694(a4), a4
  001112e8  jsr      (a5)
  001112ea  moveq    #$0, d1
  001112ec  jmp      (a6)
  001112ee  move.l   $5c(a1), d1
  001112f2  cmp.l    $64(a1), d1
  001112f6  bne.w    $111312
  001112fa  move.l   $68(a1), d1
  001112fe  moveq    #$7c, d0
  00111300  lea.l    $694(a4), a4
  00111304  jsr      (a5)
  00111306  move.l   #$ca, $26c(a2)
  0011130e  moveq    #$0, d1
  00111310  jmp      (a6)
  00111312  move.l   $34(a1), d2
  00111316  move.l   $58(a1), d1
  0011131a  moveq    #$7c, d0
  0011131c  lea.l    -$650(a4), a4
  00111320  jsr      (a5)
  00111322  move.l   $64(a1), d1
  00111326  lsl.l    #$2, d1
  00111328  move.l   $264(a2), d2
  0011132c  lsl.l    #$2, d2
  0011132e  move.l   (a0, d1.l), (a0, d2.l)
  00111334  move.l   $5c(a1), d1
  00111338  lsl.l    #$2, d1
  0011133a  move.l   $64(a1), d2
  0011133e  lsl.l    #$2, d2
  00111340  move.l   $c(a0, d1.l), (a0, d2.l)
  00111346  move.l   $5c(a1), d1
  0011134a  lsl.l    #$2, d1
  0011134c  move.l   $64(a1), $c(a0, d1.l)
  00111352  move.l   $64(a1), d1
  00111356  lsl.l    #$2, d1
  00111358  move.l   $5c(a1), $4(a0, d1.l)
  0011135e  move.l   $10(a1), d1
  00111362  lsl.l    #$2, d1
  00111364  moveq    #$0, d2
  00111366  move.b   (a0, d1.l), d2
  0011136a  move.l   d2, $70(a1)
  0011136e  moveq    #$0, d1
  00111370  move.l   d1, $74(a1)
  00111374  cmp.l    $70(a1), d1
  00111378  bgt.w    $1113a0
  0011137c  move.l   $10(a1), d2
  00111380  lsl.l    #$2, d2
  00111382  add.l    d1, d2
  00111384  moveq    #$0, d3
  00111386  move.b   (a0, d2.l), d3
  0011138a  moveq    #$9, d2
  0011138c  add.l    $64(a1), d2
  00111390  lsl.l    #$2, d2
  00111392  add.l    d1, d2
  00111394  move.b   d3, (a0, d2.l)
  00111398  moveq    #$1, d1
  0011139a  add.l    $74(a1), d1
  0011139e  bra.b    $111370
  001113a0  move.l   $68(a1), d1
  001113a4  moveq    #$7c, d0
  001113a6  lea.l    $694(a4), a4
  001113aa  jsr      (a5)
  001113ac  moveq    #$6, d1
  001113ae  add.l    $25c(a2), d1
  001113b2  moveq    #$7c, d0
  001113b4  movea.l  $158(a2), a4
  001113b8  jsr      (a5)
  001113ba  moveq    #$ff, d1
  001113bc  jmp      (a6)
  001113be  nop      
  001113c0  moveq    #$14, d3
  001113c2  add.l    a1, d3
  001113c4  lsr.l    #$2, d3
  001113c6  move.l   d3, $10(a1)
  001113ca  moveq    #$40, d0
  001113cc  lea.l    -$920(a4), a4
  001113d0  jsr      (a5)
  001113d2  move.l   d1, (a1)
  001113d4  move.l   $10(a1), d2
  001113d8  moveq    #$40, d0
  001113da  lea.l    -$874(a4), a4
  001113de  jsr      (a5)
  001113e0  tst.l    d1
  001113e2  bne.w    $1113ea
  001113e6  moveq    #$0, d1
  001113e8  jmp      (a6)
  001113ea  move.l   $260(a2), $8(a1)
  001113f0  move.l   $8(a1), d1
  001113f4  lsl.l    #$2, d1
  001113f6  moveq    #$2, d2
  001113f8  cmp.l    $8(a0, d1.l), d2
  001113fc  bne.w    $111414
  00111400  tst.l    $c(a0, d1.l)
  00111404  beq.w    $111414
  00111408  move.l   #$d8, $26c(a2)
  00111410  moveq    #$0, d1
  00111412  jmp      (a6)
  00111414  move.l   $8(a1), d1
  00111418  lsl.l    #$2, d1
  0011141a  moveq    #$1, d2
  0011141c  and.l    $14(a0, d1.l), d2
  00111420  tst.l    d2
  00111422  beq.w    $111432
  00111426  move.l   #$de, $26c(a2)
  0011142e  moveq    #$0, d1
  00111430  jmp      (a6)
  00111432  moveq    #$ff, d2
  00111434  move.l   $8(a1), d1
  00111438  moveq    #$40, d0
  0011143a  lea.l    $3cc(a4), a4
  0011143e  jsr      (a5)
  00111440  move.l   d1, $c(a1)
  00111444  tst.l    d1
  00111446  bne.w    $11144e
  0011144a  moveq    #$0, d1
  0011144c  jmp      (a6)
  0011144e  move.l   $8(a1), d1
  00111452  lsl.l    #$2, d1
  00111454  move.l   $10(a0, d1.l), d2
  00111458  subq.l   #$1, d2
  0011145a  move.l   $268(a2), $34(a1)
  00111460  move.l   d2, $38(a1)
  00111464  move.l   #$1e8, d2
  0011146a  move.l   $38(a1), d1
  0011146e  jsr      $12(a5)
  00111472  addq.l   #$1, d1
  00111474  move.l   $34(a1), d2
  00111478  sub.l    d1, d2
  0011147a  move.l   d2, $268(a2)
  0011147e  move.l   $8(a1), d1
  00111482  lsl.l    #$2, d1
  00111484  tst.l    $10(a0, d1.l)
  00111488  beq.w    $111490
  0011148c  subq.l   #$1, $268(a2)
  00111490  move.l   $8(a1), d1
  00111494  lsl.l    #$2, d1
  00111496  move.l   $c(a0, d1.l), d1
  0011149a  moveq    #$40, d0
  0011149c  movea.l  $148(a2), a4
  001114a0  jsr      (a5)
  001114a2  move.l   $8(a1), d1
  001114a6  lsl.l    #$2, d1
  001114a8  move.l   $264(a2), d2
  001114ac  lsl.l    #$2, d2
  001114ae  move.l   (a0, d1.l), (a0, d2.l)
  001114b4  move.l   $8(a1), d1
  001114b8  moveq    #$40, d0
  001114ba  movea.l  $78(a2), a4
  001114be  jsr      (a5)
  001114c0  move.l   $c(a1), d1
  001114c4  moveq    #$40, d0
  001114c6  lea.l    $470(a4), a4
  001114ca  jsr      (a5)
  001114cc  moveq    #$6, d1
  001114ce  add.l    $25c(a2), d1
  001114d2  moveq    #$40, d0
  001114d4  movea.l  $158(a2), a4
  001114d8  jsr      (a5)
  001114da  moveq    #$ff, d1
  001114dc  jmp      (a6)
  001114de  nop      
  001114e0  move.l   d1, d2
  001114e2  lsl.l    #$2, d2
  001114e4  move.l   $14(a0, d2.l), $4(a1)
  001114ea  move.l   $4(a1), d3
  001114ee  lsl.l    #$2, d3
  001114f0  moveq    #$0, d4
  001114f2  move.b   (a0, d3.l), d4
  001114f6  move.l   d4, $8(a1)
  001114fa  move.l   #$d2, $26c(a2)
  00111502  tst.l    d4
  00111504  ble.w    $111510
  00111508  moveq    #$1e, d5
  0011150a  cmp.l    d5, d4
  0011150c  ble.w    $111514
  00111510  moveq    #$0, d1
  00111512  jmp      (a6)
  00111514  moveq    #$c, d1
  00111516  moveq    #$24, d0
  00111518  movea.l  $74(a2), a4
  0011151c  jsr      (a5)
  0011151e  move.l   d1, $10(a1)
  00111522  tst.l    d1
  00111524  bne.w    $111534
  00111528  move.l   #$dd, $26c(a2)
  00111530  moveq    #$0, d1
  00111532  jmp      (a6)
  00111534  move.l   $10(a1), d2
  00111538  move.l   $4(a1), d1
  0011153c  moveq    #$24, d0
  0011153e  movea.l  $1cc(a2), a4
  00111542  jsr      (a5)
  00111544  move.l   $274(a2), d1
  00111548  lsl.l    #$2, d1
  0011154a  move.l   $28(a0, d1.l), d1
  0011154e  moveq    #$24, d0
  00111550  movea.l  $78(a2), a4
  00111554  jsr      (a5)
  00111556  move.l   $274(a2), d1
  0011155a  lsl.l    #$2, d1
  0011155c  move.l   $10(a1), $28(a0, d1.l)
  00111562  moveq    #$9, d1
  00111564  add.l    $25c(a2), d1
  00111568  move.l   d1, d2
  0011156a  move.l   $4(a1), d1
  0011156e  moveq    #$24, d0
  00111570  movea.l  $1cc(a2), a4
  00111574  jsr      (a5)
  00111576  moveq    #$6, d1
  00111578  add.l    $25c(a2), d1
  0011157c  moveq    #$24, d0
  0011157e  movea.l  $158(a2), a4
  00111582  jsr      (a5)
  00111584  moveq    #$ff, d1
  00111586  jmp      (a6)
  00111588  move.l   d1, d2
  0011158a  lsl.l    #$2, d2
  0011158c  move.l   $8(a0, d2.l), $4(a1)
  00111592  moveq    #$0, d3
  00111594  moveq    #$1c, d4
  00111596  cmp.l    $8(a0, d2.l), d4
  0011159a  bne.b    $11159e
  0011159c  not.l    d3
  0011159e  move.l   d3, $8(a1)
  001115a2  move.l   $20(a0, d2.l), $c(a1)
  001115a8  move.l   $18(a0, d2.l), d1
  001115ac  move.l   d4, d0
  001115ae  lea.l    $1b0(a4), a4
  001115b2  jsr      (a5)
  001115b4  move.l   d1, $10(a1)
  001115b8  moveq    #$18, d2
  001115ba  add.l    a1, d2
  001115bc  lsr.l    #$2, d2
  001115be  move.l   d2, $14(a1)
  001115c2  tst.l    d1
  001115c4  bne.w    $1115cc
  001115c8  moveq    #$0, d1
  001115ca  jmp      (a6)
  001115cc  tst.l    $8(a1)
  001115d0  beq.w    $1115f4
  001115d4  move.l   $c(a1), d1
  001115d8  lsl.l    #$2, d1
  001115da  moveq    #$0, d2
  001115dc  move.b   (a0, d1.l), d2
  001115e0  moveq    #$4f, d3
  001115e2  cmp.l    d3, d2
  001115e4  ble.w    $1115f4
  001115e8  move.l   #$dc, $26c(a2)
  001115f0  moveq    #$0, d1
  001115f2  jmp      (a6)
  001115f4  move.l   (a1), d1
  001115f6  lsl.l    #$2, d1
  001115f8  move.l   $14(a1), d3
  001115fc  move.l   $1c(a0, d1.l), d2
  00111600  move.l   $10(a1), d1
  00111604  moveq    #$48, d0
  00111606  lea.l    -$ae8(a4), a4
  0011160a  jsr      (a5)
  0011160c  move.l   d1, $10(a1)
  00111610  move.l   $14(a1), d2
  00111614  moveq    #$48, d0
  00111616  lea.l    -$a3c(a4), a4
  0011161a  jsr      (a5)
  0011161c  tst.l    d1
  0011161e  bne.w    $111626
  00111622  moveq    #$0, d1
  00111624  jmp      (a6)
  00111626  move.l   $260(a2), $38(a1)
  0011162c  move.l   $38(a1), d1
  00111630  cmp.l    $25c(a2), d1
  00111634  bne.w    $111644
  00111638  move.l   #$d4, $26c(a2)
  00111640  moveq    #$0, d1
  00111642  jmp      (a6)
  00111644  tst.l    $8(a1)
  00111648  beq.w    $111674
  0011164c  moveq    #$19, d1
  0011164e  add.l    $38(a1), d1
  00111652  moveq    #$14, d2
  00111654  moveq    #$48, d0
  00111656  movea.l  -$50(a2), a4
  0011165a  jsr      (a5)
  0011165c  moveq    #$19, d1
  0011165e  add.l    $38(a1), d1
  00111662  move.l   d1, d2
  00111664  move.l   $c(a1), d1
  00111668  moveq    #$48, d0
  0011166a  movea.l  $1cc(a2), a4
  0011166e  jsr      (a5)
  00111670  bra.w    $1116d2
  00111674  move.l   (a1), d1
  00111676  lsl.l    #$2, d1
  00111678  moveq    #$15, d2
  0011167a  cmp.l    $8(a0, d1.l), d2
  0011167e  bne.w    $111692
  00111682  move.l   $38(a1), d3
  00111686  lsl.l    #$2, d3
  00111688  move.l   $c(a1), $14(a0, d3.l)
  0011168e  bra.w    $1116d2
  00111692  move.l   (a1), d1
  00111694  lsl.l    #$2, d1
  00111696  moveq    #$22, d2
  00111698  cmp.l    $8(a0, d1.l), d2
  0011169c  bne.w    $1116d2
  001116a0  moveq    #$0, d1
  001116a2  move.l   d1, $3c(a1)
  001116a6  moveq    #$2, d2
  001116a8  cmp.l    d2, d1
  001116aa  bgt.w    $1116d2
  001116ae  move.l   $c(a1), d2
  001116b2  moveq    #$4c, d0
  001116b4  movea.l  $1b8(a2), a4
  001116b8  jsr      (a5)
  001116ba  moveq    #$6, d2
  001116bc  add.l    $3c(a1), d2
  001116c0  add.l    $38(a1), d2
  001116c4  lsl.l    #$2, d2
  001116c6  move.l   d1, (a0, d2.l)
  001116ca  moveq    #$1, d1
  001116cc  add.l    $3c(a1), d1
  001116d0  bra.b    $1116a2
  001116d2  moveq    #$6, d1
  001116d4  add.l    $25c(a2), d1
  001116d8  moveq    #$48, d0
  001116da  movea.l  $158(a2), a4
  001116de  jsr      (a5)
  001116e0  moveq    #$ff, d1
  001116e2  jmp      (a6)
  001116e4  move.l   d1, d2
  001116e6  lsl.l    #$2, d2
  001116e8  move.l   $14(a0, d2.l), $4(a1)
  001116ee  move.l   $4(a1), d1
  001116f2  moveq    #$14, d0
  001116f4  lea.l    $54(a4), a4
  001116f8  jsr      (a5)
  001116fa  move.l   d1, $8(a1)
  001116fe  tst.l    d1
  00111700  bne.w    $111708
  00111704  moveq    #$0, d1
  00111706  jmp      (a6)
  00111708  move.l   $8(a1), d1
  0011170c  lsl.l    #$2, d1
  0011170e  move.l   $4(a0, d1.l), $c(a1)
  00111714  clr.l    $26c(a2)
  00111718  tst.l    $c(a1)
  0011171c  bne.w    $111726
  00111720  moveq    #$0, d1
  00111722  bra.w    $111734
  00111726  moveq    #$fe, d2
  00111728  move.l   $c(a1), d1
  0011172c  moveq    #$1c, d0
  0011172e  lea.l    $a8(a4), a4
  00111732  jsr      (a5)
  00111734  jmp      (a6)
  00111736  nop      
  00111738  tst.l    d1
  0011173a  bne.w    $111746
  0011173e  move.l   $25c(a2), d1
  00111742  bra.w    $11178a
  00111746  move.l   $258(a2), $4(a1)
  0011174c  bra.w    $11175c
  00111750  move.l   $4(a1), d1
  00111754  lsl.l    #$2, d1
  00111756  move.l   (a0, d1.l), $4(a1)
  0011175c  tst.l    $4(a1)
  00111760  beq.w    $11176c
  00111764  move.l   $4(a1), d1
  00111768  cmp.l    (a1), d1
  0011176a  bne.b    $111750
  0011176c  tst.l    $4(a1)
  00111770  bne.w    $111782
  00111774  move.l   #$d3, $26c(a2)
  0011177c  moveq    #$0, d1
  0011177e  bra.w    $11178a
  00111782  move.l   (a1), d1
  00111784  lsl.l    #$2, d1
  00111786  move.l   $4(a0, d1.l), d1
  0011178a  jmp      (a6)
  0011178c  move.l   $258(a2), $8(a1)
  00111792  bra.w    $1117a2
  00111796  move.l   $8(a1), d1
  0011179a  lsl.l    #$2, d1
  0011179c  move.l   (a0, d1.l), $8(a1)
  001117a2  tst.l    $8(a1)
  001117a6  beq.w    $1117b8
  001117aa  move.l   $8(a1), d1
  001117ae  lsl.l    #$2, d1
  001117b0  move.l   (a1), d2
  001117b2  cmp.l    $4(a0, d1.l), d2
  001117b6  bne.b    $111796
  001117b8  tst.l    $8(a1)
  001117bc  beq.w    $1117e4
  001117c0  move.l   $8(a1), d1
  001117c4  lsl.l    #$2, d1
  001117c6  moveq    #$ff, d2
  001117c8  cmp.l    $8(a0, d1.l), d2
  001117cc  beq.w    $1117d8
  001117d0  cmp.l    $4(a1), d2
  001117d4  bne.w    $1117e4
  001117d8  move.l   #$ca, $26c(a2)
  001117e0  moveq    #$0, d1
  001117e2  jmp      (a6)
  001117e4  moveq    #$7, d1
  001117e6  moveq    #$18, d0
  001117e8  lea.l    -$f20(a4), a4
  001117ec  jsr      (a5)
  001117ee  move.l   d1, $c(a1)
  001117f2  tst.l    d1
  001117f4  bne.w    $1117fc
  001117f8  moveq    #$0, d1
  001117fa  jmp      (a6)
  001117fc  moveq    #$3c, d0
  001117fe  movea.l  $38(a2), a4
  00111802  jsr      (a5)
  00111804  move.l   d1, $30(a1)
  00111808  move.l   $4(a1), $2c(a1)
  0011180e  move.l   $274(a2), $34(a1)
  00111814  move.l   (a1), d4
  00111816  move.l   $258(a2), d3
  0011181a  moveq    #$7, d2
  0011181c  move.l   $c(a1), d1
  00111820  moveq    #$1c, d0
  00111822  lea.l    $120(a4), a4
  00111826  jsr      (a5)
  00111828  move.l   d1, $258(a2)
  0011182c  jmp      (a6)
  0011182e  nop      
  00111830  tst.l    d1
  00111832  bne.w    $11183c
  00111836  moveq    #$ff, d1
  00111838  bra.w    $1118a8
  0011183c  move.l   #$258, d1
  00111842  add.l    a2, d1
  00111844  lsr.l    #$2, d1
  00111846  move.l   d1, $4(a1)
  0011184a  bra.w    $11185a
  0011184e  move.l   $4(a1), d1
  00111852  lsl.l    #$2, d1
  00111854  move.l   (a0, d1.l), $4(a1)
  0011185a  move.l   $4(a1), d1
  0011185e  lsl.l    #$2, d1
  00111860  tst.l    (a0, d1.l)
  00111864  beq.w    $111870
  00111868  move.l   (a1), d2
  0011186a  cmp.l    (a0, d1.l), d2
  0011186e  bne.b    $11184e
  00111870  move.l   $4(a1), d1
  00111874  lsl.l    #$2, d1
  00111876  tst.l    (a0, d1.l)
  0011187a  bne.w    $11188c
  0011187e  move.l   #$d3, $26c(a2)
  00111886  moveq    #$0, d1
  00111888  bra.w    $1118a8
  0011188c  move.l   (a1), d1
  0011188e  lsl.l    #$2, d1
  00111890  move.l   $4(a1), d2
  00111894  lsl.l    #$2, d2
  00111896  move.l   (a0, d1.l), (a0, d2.l)
  0011189c  move.l   (a1), d1
  0011189e  moveq    #$14, d0
  001118a0  movea.l  $78(a2), a4
  001118a4  jsr      (a5)
  001118a6  moveq    #$ff, d1
  001118a8  jmp      (a6)
  001118aa  nop      
  001118ac  move.l   d2, d3
  001118ae  move.l   d1, d2
  001118b0  moveq    #$8, d1
  001118b2  add.l    a1, d1
  001118b4  lsr.l    #$2, d1
  001118b6  moveq    #$44, d0
  001118b8  movea.l  -$8(a2), a4
  001118bc  jsr      (a5)
  001118be  move.l   (a1), d1
  001118c0  jmp      (a6)
  001118c2  nop      
  001118c4  ori.b    #$0, d0
  001118c8  ori.b    #$1, d0
  001118cc  ori.b    #$4, d0
  001118d0  ori.b    #$23, d0
  001118d4  ori.b    #$e4, d0
  001118d8  ori.b    #$9e, d0
