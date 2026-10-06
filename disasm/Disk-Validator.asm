; Fichier      : l\Disk-Validator
; Taille       : 1848 octets
; Nom interne  : ''
; Hunks        : 1 (first=0, last=0)
;   hunk 0: code   1812 octets  relocs=0
;
; Desassembly 68000 (capstone), adresses logiques
; 0x00010000 + i*0x00100000 par hunk.
==============================================================================

; --- chaines detectees --------------------------
;  0001002c : 'r $)'
;  0001009e : 't "*'
;  000100b4 : 't #B'
;  000101ce : 'p0(j'
;  00010246 : 'p0(j'
;  00010256 : 'p0(j'
;  00010266 : 'p0(j'
;  0001027a : 'p0(j'
;  000102b6 : 'p8(j'
;  000102ea : 'p0(j'
;  00010304 : 'p0(j'
;  00010334 : 'p8(j'
;  00010394 : 'pD(j'
;  000103ae : 'pD(j'
;  000103e6 : 'p<(j'
;  000103f6 : 'p<(j'
;  00010405 : '(p<(j'
;  0001044a : 'p<(j'
;  00010466 : 'p0(j'
;  0001049c : 'p0(j'
;  000104b0 : 'p4(j'
;  000104cc : 'p0(j'
;  000104f5 : 'in drive 00'
;  00010505 : 'Replace volume'
;  00010515 : 'is out of range'
;  00010531 : '- bad extension'
;  00010559 : 'bitmap checksum error'
;  000105ed : '- bad block type'
;  00010601 : '- unexpected data block&*'
;  00010691 : '- second root block'
;  000106f5 : '- bad header'

; ========== HUNK 0 (code, 1812 octets) ==========

  00010000  ori.b    #$c5, d0
  00010004  lea.l    $4f0(a4), a3
  00010008  move.l   a3, d2
  0001000a  lsr.l    #$2, d2
  0001000c  move.l   d2, $4(a1)
  00010010  moveq    #$9, d3
  00010012  cmp.l    $2e8(a2), d3
  00010016  bge.w    $1002c
  0001001a  moveq    #$a, d2
  0001001c  move.l   $2e8(a2), d1
  00010020  jsr      $12(a5)
  00010024  moveq    #$30, d2
  00010026  add.l    d2, d1
  00010028  bra.w    $1002e
  0001002c  moveq    #$20, d1
  0001002e  move.l   $4(a1), d2
  00010032  lsl.l    #$2, d2
  00010034  move.b   d1, $a(a0, d2.l)
  00010038  moveq    #$30, d1
  0001003a  add.l    $2e8(a2), d1
  0001003e  move.l   $4(a1), d2
  00010042  lsl.l    #$2, d2
  00010044  move.b   d1, $b(a0, d2.l)
  00010048  move.l   $258(a2), d1
  0001004c  subq.l   #$3, d1
  0001004e  move.l   d1, $29c(a2)
  00010052  move.l   $2ac(a2), $2a8(a2)
  00010058  move.l   $258(a2), d2
  0001005c  subq.l   #$1, d2
  0001005e  move.l   d2, $2f8(a2)
  00010062  clr.l    $308(a2)
  00010066  move.l   $2fc(a2), d1
  0001006a  moveq    #$14, d0
  0001006c  movea.l  $78(a2), a4
  00010070  jsr      (a5)
  00010072  clr.l    $2fc(a2)
  00010076  move.l   $2bc(a2), $8(a1)
  0001007c  moveq    #$0, d1
  0001007e  move.l   d1, $c(a1)
  00010082  cmp.l    $8(a1), d1
  00010086  bgt.w    $1009e
  0001008a  add.l    $2b4(a2), d1
  0001008e  lsl.l    #$2, d1
  00010090  moveq    #$ff, d2
  00010092  move.l   d2, (a0, d1.l)
  00010096  moveq    #$1, d1
  00010098  add.l    $c(a1), d1
  0001009c  bra.b    $1007e
  0001009e  moveq    #$20, d2
  000100a0  move.l   $28c(a2), d1
  000100a4  jsr      $12(a5)
  000100a8  tst.l    d2
  000100aa  beq.w    $100dc
  000100ae  moveq    #$ff, d1
  000100b0  move.l   d1, $8(a1)
  000100b4  moveq    #$20, d2
  000100b6  move.l   d2, $c(a1)
  000100ba  move.l   $28c(a2), d1
  000100be  jsr      $12(a5)
  000100c2  move.l   $c(a1), d1
  000100c6  sub.l    d2, d1
  000100c8  move.l   $8(a1), d2
  000100cc  lsr.l    d1, d2
  000100ce  move.l   $2b4(a2), d1
  000100d2  add.l    $2bc(a2), d1
  000100d6  lsl.l    #$2, d1
  000100d8  move.l   d2, (a0, d1.l)
  000100dc  move.l   $290(a2), d2
  000100e0  move.l   $2b4(a2), d1
  000100e4  moveq    #$14, d0
  000100e6  movea.l  $324(a2), a4
  000100ea  jsr      (a5)
  000100ec  move.l   $2bc(a2), d2
  000100f0  move.l   $2b4(a2), d1
  000100f4  moveq    #$14, d0
  000100f6  movea.l  $2b0(a2), a4
  000100fa  jsr      (a5)
  000100fc  move.l   d1, $8(a1)
  00010100  move.l   $2bc(a2), d2
  00010104  move.l   $2b8(a2), d1
  00010108  moveq    #$18, d0
  0001010a  movea.l  $2b0(a2), a4
  0001010e  jsr      (a5)
  00010110  add.l    $8(a1), d1
  00010114  move.l   d1, $2c0(a2)
  00010118  bra.w    $10164
  0001011c  move.l   #$120, d2
  00010122  moveq    #$ff, d1
  00010124  moveq    #$14, d0
  00010126  movea.l  $28(a2), a4
  0001012a  jsr      (a5)
  0001012c  move.l   $340(a2), d1
  00010130  lsl.l    #$2, d1
  00010132  move.l   $4(a1), d3
  00010136  move.l   $28(a0, d1.l), d2
  0001013a  lea.l    $500(a4), a3
  0001013e  move.l   a3, d1
  00010140  lsr.l    #$2, d1
  00010142  moveq    #$14, d0
  00010144  movea.l  $d0(a2), a4
  00010148  jsr      (a5)
  0001014a  tst.l    d1
  0001014c  bne.w    $10164
  00010150  move.l   (a1), d1
  00010152  moveq    #$14, d0
  00010154  movea.l  $1b4(a2), a4
  00010158  jsr      (a5)
  0001015a  moveq    #$0, d1
  0001015c  moveq    #$14, d0
  0001015e  movea.l  $320(a2), a4
  00010162  jsr      (a5)
  00010164  move.l   $340(a2), d1
  00010168  lsl.l    #$2, d1
  0001016a  tst.l    $8(a0, d1.l)
  0001016e  beq.b    $1011c
  00010170  move.l   (a1), d1
  00010172  moveq    #$14, d0
  00010174  movea.l  $1b4(a2), a4
  00010178  jsr      (a5)
  0001017a  clr.l    $2c8(a2)
  0001017e  move.l   $288(a2), $8(a1)
  00010184  move.l   $284(a2), d1
  00010188  move.l   d1, $c(a1)
  0001018c  cmp.l    $8(a1), d1
  00010190  bgt.w    $104de
  00010194  sub.l    $284(a2), d1
  00010198  move.l   d1, $10(a1)
  0001019c  moveq    #$1f, d2
  0001019e  and.l    d1, d2
  000101a0  moveq    #$1, d3
  000101a2  lsl.l    d2, d3
  000101a4  move.l   d3, $14(a1)
  000101a8  lsr.l    #$5, d1
  000101aa  move.l   d1, $18(a1)
  000101ae  move.l   $c(a1), d2
  000101b2  cmp.l    $284(a2), d2
  000101b6  blt.w    $101c2
  000101ba  cmp.l    $288(a2), d2
  000101be  ble.w    $101d6
  000101c2  move.l   $c(a1), d2
  000101c6  lea.l    $510(a4), a3
  000101ca  move.l   a3, d1
  000101cc  lsr.l    #$2, d1
  000101ce  moveq    #$30, d0
  000101d0  movea.l  $338(a2), a4
  000101d4  jsr      (a5)
  000101d6  move.l   $2b4(a2), d1
  000101da  add.l    $18(a1), d1
  000101de  lsl.l    #$2, d1
  000101e0  move.l   (a0, d1.l), $1c(a1)
  000101e6  move.l   $2b8(a2), d1
  000101ea  add.l    $18(a1), d1
  000101ee  lsl.l    #$2, d1
  000101f0  move.l   (a0, d1.l), $20(a1)
  000101f6  move.l   $20(a1), d1
  000101fa  and.l    $14(a1), d1
  000101fe  tst.l    d1
  00010200  bne.w    $1020a
  00010204  moveq    #$0, d1
  00010206  bra.w    $1020c
  0001020a  moveq    #$1, d1
  0001020c  move.l   d1, $20(a1)
  00010210  move.l   $1c(a1), d2
  00010214  and.l    $14(a1), d2
  00010218  tst.l    d2
  0001021a  bne.w    $10224
  0001021e  moveq    #$0, d1
  00010220  bra.w    $10226
  00010224  moveq    #$1, d1
  00010226  move.l   d1, $1c(a1)
  0001022a  cmp.l    $20(a1), d1
  0001022e  beq.w    $104d4
  00010232  tst.l    $20(a1)
  00010236  bne.w    $1024e
  0001023a  move.l   $c(a1), d2
  0001023e  lea.l    $520(a4), a3
  00010242  move.l   a3, d1
  00010244  lsr.l    #$2, d1
  00010246  moveq    #$30, d0
  00010248  movea.l  $338(a2), a4
  0001024c  jsr      (a5)
  0001024e  move.l   $c(a1), d2
  00010252  move.l   $2b8(a2), d1
  00010256  moveq    #$30, d0
  00010258  movea.l  $324(a2), a4
  0001025c  jsr      (a5)
  0001025e  addq.l   #$1, $2c4(a2)
  00010262  move.l   $c(a1), d1
  00010266  moveq    #$30, d0
  00010268  movea.l  $328(a2), a4
  0001026c  jsr      (a5)
  0001026e  bra.w    $10472
  00010272  move.l   $2d0(a2), d1
  00010276  add.l    $2a4(a2), d1
  0001027a  moveq    #$30, d0
  0001027c  movea.l  $32c(a2), a4
  00010280  jsr      (a5)
  00010282  move.l   $2ac(a2), $24(a1)
  00010288  moveq    #$6, d1
  0001028a  move.l   d1, $28(a1)
  0001028e  cmp.l    $24(a1), d1
  00010292  bgt.w    $102c6
  00010296  add.l    $2d0(a2), d1
  0001029a  lsl.l    #$2, d1
  0001029c  tst.l    (a0, d1.l)
  000102a0  beq.w    $102be
  000102a4  move.l   $2d0(a2), d1
  000102a8  add.l    $28(a1), d1
  000102ac  lsl.l    #$2, d1
  000102ae  move.l   (a0, d1.l), d2
  000102b2  move.l   $2b4(a2), d1
  000102b6  moveq    #$38, d0
  000102b8  movea.l  $324(a2), a4
  000102bc  jsr      (a5)
  000102be  moveq    #$1, d1
  000102c0  add.l    $28(a1), d1
  000102c4  bra.b    $1028a
  000102c6  move.l   $2d0(a2), d1
  000102ca  add.l    $29c(a2), d1
  000102ce  lsl.l    #$2, d1
  000102d0  tst.l    (a0, d1.l)
  000102d4  beq.w    $102f2
  000102d8  move.l   $2d0(a2), d1
  000102dc  add.l    $29c(a2), d1
  000102e0  lsl.l    #$2, d1
  000102e2  move.l   (a0, d1.l), d2
  000102e6  move.l   $2b4(a2), d1
  000102ea  moveq    #$30, d0
  000102ec  movea.l  $324(a2), a4
  000102f0  jsr      (a5)
  000102f2  moveq    #$ff, d1
  000102f4  move.l   d1, $2c8(a2)
  000102f8  bra.w    $10494
  000102fc  move.l   $2d0(a2), d1
  00010300  add.l    $2a4(a2), d1
  00010304  moveq    #$30, d0
  00010306  movea.l  $32c(a2), a4
  0001030a  jsr      (a5)
  0001030c  clr.l    $24(a1)
  00010310  move.l   $2d0(a2), d1
  00010314  add.l    $29c(a2), d1
  00010318  lsl.l    #$2, d1
  0001031a  tst.l    (a0, d1.l)
  0001031e  beq.w    $10342
  00010322  move.l   $2d0(a2), d1
  00010326  add.l    $29c(a2), d1
  0001032a  lsl.l    #$2, d1
  0001032c  move.l   (a0, d1.l), d2
  00010330  move.l   $2b4(a2), d1
  00010334  moveq    #$38, d0
  00010336  movea.l  $324(a2), a4
  0001033a  jsr      (a5)
  0001033c  moveq    #$ff, d1
  0001033e  move.l   d1, $2c8(a2)
  00010342  move.l   $2d0(a2), d1
  00010346  lsl.l    #$2, d1
  00010348  move.l   $8(a0, d1.l), $2c(a1)
  0001034e  tst.l    $2c(a1)
  00010352  beq.w    $10456
  00010356  move.l   $300(a2), d2
  0001035a  cmp.l    $2c(a1), d2
  0001035e  bge.w    $10366
  00010362  move.l   d2, $2c(a1)
  00010366  move.l   $2a8(a2), $30(a1)
  0001036c  move.l   $2c(a1), d1
  00010370  move.l   $2a8(a2), d2
  00010374  sub.l    d1, d2
  00010376  addq.l   #$1, d2
  00010378  move.l   d2, d1
  0001037a  move.l   d1, $34(a1)
  0001037e  cmp.l    $30(a1), d1
  00010382  bgt.w    $103c6
  00010386  add.l    $2d0(a2), d1
  0001038a  lsl.l    #$2, d1
  0001038c  move.l   (a0, d1.l), d2
  00010390  move.l   $2b4(a2), d1
  00010394  moveq    #$44, d0
  00010396  movea.l  $324(a2), a4
  0001039a  jsr      (a5)
  0001039c  move.l   $2d0(a2), d1
  000103a0  add.l    $34(a1), d1
  000103a4  lsl.l    #$2, d1
  000103a6  move.l   (a0, d1.l), d2
  000103aa  move.l   $2b8(a2), d1
  000103ae  moveq    #$44, d0
  000103b0  movea.l  $324(a2), a4
  000103b4  jsr      (a5)
  000103b6  addq.l   #$1, $2c4(a2)
  000103ba  addq.l   #$1, $24(a1)
  000103be  moveq    #$1, d1
  000103c0  add.l    $34(a1), d1
  000103c4  bra.b    $1037a
  000103c6  move.l   $2d0(a2), d1
  000103ca  add.l    $2f8(a2), d1
  000103ce  lsl.l    #$2, d1
  000103d0  move.l   (a0, d1.l), $28(a1)
  000103d6  tst.l    $28(a1)
  000103da  beq.w    $10456
  000103de  move.l   $28(a1), d2
  000103e2  move.l   $2b4(a2), d1
  000103e6  moveq    #$3c, d0
  000103e8  movea.l  $324(a2), a4
  000103ec  jsr      (a5)
  000103ee  move.l   $28(a1), d2
  000103f2  move.l   $2b8(a2), d1
  000103f6  moveq    #$3c, d0
  000103f8  movea.l  $324(a2), a4
  000103fc  jsr      (a5)
  000103fe  addq.l   #$1, $2c4(a2)
  00010402  move.l   $28(a1), d1
  00010406  moveq    #$3c, d0
  00010408  movea.l  $328(a2), a4
  0001040c  jsr      (a5)
  0001040e  move.l   $2d0(a2), d1
  00010412  lsl.l    #$2, d1
  00010414  moveq    #$10, d2
  00010416  cmp.l    (a0, d1.l), d2
  0001041a  bne.w    $1043e
  0001041e  move.l   $2d0(a2), d3
  00010422  add.l    $294(a2), d3
  00010426  lsl.l    #$2, d3
  00010428  moveq    #$fd, d4
  0001042a  cmp.l    (a0, d3.l), d4
  0001042e  bne.w    $1043e
  00010432  move.l   $28(a1), d3
  00010436  cmp.l    $4(a0, d1.l), d3
  0001043a  beq.w    $10452
  0001043e  move.l   $28(a1), d2
  00010442  lea.l    $52c(a4), a3
  00010446  move.l   a3, d1
  00010448  lsr.l    #$2, d1
  0001044a  moveq    #$3c, d0
  0001044c  movea.l  $338(a2), a4
  00010450  jsr      (a5)
  00010452  bra.w    $10342
  00010456  bra.w    $10494
  0001045a  move.l   $c(a1), d2
  0001045e  lea.l    $53c(a4), a3
  00010462  move.l   a3, d1
  00010464  lsr.l    #$2, d1
  00010466  moveq    #$30, d0
  00010468  movea.l  $338(a2), a4
  0001046c  jsr      (a5)
  0001046e  bra.w    $10494
  00010472  move.l   $c(a1), d2
  00010476  move.l   $2d0(a2), d1
  0001047a  moveq    #$30, d0
  0001047c  lea.l    $56c(a4), a4
  00010480  jsr      (a5)
  00010482  moveq    #$fd, d2
  00010484  cmp.l    d2, d1
  00010486  beq.w    $102fc
  0001048a  moveq    #$2, d3
  0001048c  cmp.l    d3, d1
  0001048e  beq.w    $10272
  00010492  bra.b    $1045a
  00010494  move.l   $2bc(a2), d2
  00010498  move.l   $2b4(a2), d1
  0001049c  moveq    #$30, d0
  0001049e  movea.l  $2b0(a2), a4
  000104a2  jsr      (a5)
  000104a4  move.l   d1, $24(a1)
  000104a8  move.l   $2bc(a2), d2
  000104ac  move.l   $2b8(a2), d1
  000104b0  moveq    #$34, d0
  000104b2  movea.l  $2b0(a2), a4
  000104b6  jsr      (a5)
  000104b8  add.l    $24(a1), d1
  000104bc  cmp.l    $2c0(a2), d1
  000104c0  beq.w    $104d4
  000104c4  lea.l    $554(a4), a3
  000104c8  move.l   a3, d1
  000104ca  lsr.l    #$2, d1
  000104cc  moveq    #$30, d0
  000104ce  movea.l  $334(a2), a4
  000104d2  jsr      (a5)
  000104d4  moveq    #$1, d1
  000104d6  add.l    $c(a1), d1
  000104da  bra.w    $10188
  000104de  tst.l    $2c8(a2)
  000104e2  bne.w    $1017a
  000104e6  moveq    #$ff, d1
  000104e8  moveq    #$14, d0
  000104ea  movea.l  $320(a2), a4
  000104ee  jsr      (a5)
  000104f0  jmp      (a6)
  000104f2  nop      
  000104f4  cmpi.w   #$6e20, $6472(a1)
  000104fa  bvs.b    $10572
  000104fc  bcs.b    $1051e
  000104fe  move.w   (a0, d0.w), d0
  00010502  ori.b    #$52, d0
  00010506  bcs.b    $10578
  00010508  bge.b    $1056b
  0001050a  bls.b    $10571
  0001050c  movea.l  $756d(a6, invalid.w), a0
  00010512  bcs.w    $1147d
  * 00010516  dc.w     0x7320
  00010518  ble.b    $1058f
  0001051a  moveq    #$20, d2
  0001051c  ble.b    $10584
  0001051e  movea.l  ([$6765, a2]), a0
  00010524  eori.w   #$7320, $696e(a1)
  0001052a  moveq    #$61, d3
  0001052c  bge.b    $10597
  0001052e  bcc.w    $1145d
  00010532  movea.l  -(a2), a0
  00010534  bsr.b    $1059a
  00010536  movea.l  -(a5), a0
  00010538  moveq    #$74, d4
  0001053a  bcs.b    $105aa
  * 0001053c  dc.w     0x7369
  0001053e  ble.b    $105ae
  00010540  move.b   $206e(a5), -(a3)
  00010544  ble.b    $105ba
  00010546  movea.l  -(a4), a0
  00010548  bvs.b    $105bc
  0001054a  bcs.b    $105af
  0001054c  moveq    #$6f, d2
  0001054e  moveq    #$79, d1
  00010550  movea.l  $7220(a7), a0
  00010554  bne.b    $105bf
  00010556  bge.b    $105bd
  * 00010558  dc.w     0x1662
  0001055a  bvs.b    $105d0
  0001055c  blt.b    $105bf
  0001055e  moveq    #$20, d0
  00010560  bls.b    $105ca
  00010562  bcs.b    $105c7
  00010564  bmi.b    $105d9
  * 00010566  dc.w     0x756d
  00010568  movea.l  -(a5), a0
  0001056a  moveq    #$72, d1
  0001056c  ble.b    $105e0
  0001056e  ori.b    #$0, d0
  00010572  ori.w    #$2429, -(a2)
  00010576  ori.b    #$ec, d4
  0001057a  ori.w    #$220b, sr
  0001057e  lsr.l    #$2, d1
  00010580  moveq    #$14, d0
  00010582  movea.l  $338(a2), a4
  00010586  jsr      (a5)
  00010588  bra.w    $105ea
  0001058c  move.l   (a1), d1
  0001058e  add.l    $294(a2), d1
  00010592  lsl.l    #$2, d1
  00010594  tst.l    (a0, d1.l)
  00010598  bge.w    $105ac
  0001059c  move.l   $4(a1), d2
  000105a0  move.l   (a1), d1
  000105a2  moveq    #$14, d0
  000105a4  lea.l    $144(a4), a4
  000105a8  jsr      (a5)
  000105aa  jmp      (a6)
  000105ac  move.l   $4(a1), d2
  000105b0  move.l   (a1), d1
  000105b2  moveq    #$14, d0
  000105b4  lea.l    $a8(a4), a4
  000105b8  jsr      (a5)
  000105ba  jmp      (a6)
  000105bc  move.l   $4(a1), d2
  000105c0  lea.l    $90(a4), a3
  000105c4  move.l   a3, d1
  000105c6  lsr.l    #$2, d1
  000105c8  moveq    #$14, d0
  000105ca  movea.l  $338(a2), a4
  000105ce  jsr      (a5)
  000105d0  bra.w    $105ea
  000105d4  move.l   (a1), d1
  000105d6  lsl.l    #$2, d1
  000105d8  move.l   (a0, d1.l), d1
  000105dc  moveq    #$2, d2
  000105de  cmp.l    d2, d1
  000105e0  beq.b    $1058c
  000105e2  moveq    #$8, d3
  000105e4  cmp.l    d3, d1
  000105e6  beq.b    $105bc
  000105e8  bra.b    $10574
  000105ea  jmp      (a6)
  000105ec  move.b   $2062(a5), d0
  000105f0  bsr.b    $10656
  000105f2  movea.l  -(a2), a0
  000105f4  bge.b    $10665
  000105f6  bls.b    $10663
  000105f8  movea.l  $65000000(a4, invalid.w), a0
  00010600  move.b   $2075(a5), -(a3)
  00010604  bgt.b    $1066b
  00010606  moveq    #$70, d4
  00010608  bcs.b    $1066d
  0001060a  moveq    #$65, d2
  0001060c  bcc.b    $1062e
  0001060e  bcc.b    $10671
  00010610  moveq    #$61, d2
  00010612  movea.l  -(a2), a0
  00010614  bge.b    $10685
  00010616  bls.b    $10683
  00010618  move.l   $294(a2), d3
  0001061c  add.l    d1, d3
  0001061e  lsl.l    #$2, d3
  00010620  moveq    #$1, d4
  00010622  cmp.l    (a0, d3.l), d4
  00010626  bne.w    $10650
  0001062a  tst.l    $308(a2)
  0001062e  beq.w    $10646
  00010632  lea.l    $78(a4), a3
  00010636  move.l   a3, d1
  00010638  lsr.l    #$2, d1
  0001063a  moveq    #$14, d0
  0001063c  movea.l  $338(a2), a4
  00010640  jsr      (a5)
  00010642  bra.w    $10650
  00010646  moveq    #$ff, d1
  00010648  move.l   d1, $308(a2)
  0001064c  moveq    #$2, d1
  0001064e  jmp      (a6)
  00010650  move.l   (a1), d1
  00010652  lsl.l    #$2, d1
  00010654  move.l   $4(a1), d2
  00010658  cmp.l    $4(a0, d1.l), d2
  0001065c  bne.w    $10678
  00010660  tst.l    $8(a0, d1.l)
  00010664  bne.w    $10678
  00010668  tst.l    $c(a0, d1.l)
  0001066c  bne.w    $10678
  00010670  tst.l    $10(a0, d1.l)
  00010674  beq.w    $1068c
  00010678  move.l   $4(a1), d2
  0001067c  lea.l    $8c(a4), a3
  00010680  move.l   a3, d1
  00010682  lsr.l    #$2, d1
  00010684  moveq    #$14, d0
  00010686  movea.l  $338(a2), a4
  0001068a  jsr      (a5)
  0001068c  moveq    #$2, d1
  0001068e  jmp      (a6)
  00010690  move.b   $2073(a5), -(a1)
  00010694  bcs.b    $106f9
  00010696  ble.b    $10706
  00010698  bcc.b    $106ba
  0001069a  moveq    #$6f, d1
  0001069c  ble.b    $10712
  0001069e  movea.l  -(a2), a0
  000106a0  bge.b    $10711
  000106a2  bls.b    $1070f
  000106a4  btst.l   d7, $2062(a5)
  000106a8  bsr.b    $1070e
  000106aa  movea.l  -(a4), a0
  000106ac  bvs.b    $10720
  000106ae  bcs.b    $10713
  000106b0  moveq    #$6f, d2
  000106b2  moveq    #$79, d1
  000106b4  move.l   d1, d3
  000106b6  lsl.l    #$2, d3
  000106b8  cmp.l    $4(a0, d3.l), d2
  000106bc  bne.w    $106dc
  000106c0  tst.l    $8(a0, d3.l)
  000106c4  beq.w    $106f0
  000106c8  move.l   $2a8(a2), d4
  000106cc  add.l    d1, d4
  000106ce  lsl.l    #$2, d4
  000106d0  move.l   (a0, d4.l), d5
  000106d4  cmp.l    $10(a0, d3.l), d5
  000106d8  beq.w    $106f0
  000106dc  move.l   $4(a1), d2
  000106e0  lea.l    $40(a4), a3
  000106e4  move.l   a3, d1
  000106e6  lsr.l    #$2, d1
  000106e8  moveq    #$14, d0
  000106ea  movea.l  $338(a2), a4
  000106ee  jsr      (a5)
  000106f0  moveq    #$fd, d1
  000106f2  jmp      (a6)
  000106f4  cmpi.b   #$62, $6164(a5)
  000106fa  movea.l  $6561(a0), a0
  000106fe  bcc.b    $10765
  00010700  moveq    #$0, d1
  00010702  ori.b    #$0, d0
  00010706  ori.b    #$0, d0
  * 0001070a  dc.w     0x00c6
  0001070c  ori.b    #$4, d0
  00010710  ori.b    #$d0, d0
