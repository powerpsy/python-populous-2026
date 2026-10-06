; Fichier      : l\Port-Handler
; Taille       : 1364 octets
; Nom interne  : ''
; Hunks        : 1 (first=0, last=0)
;   hunk 0: code   1328 octets  relocs=0
;
; Desassembly 68000 (capstone), adresses logiques
; 0x00010000 + i*0x00100000 par hunk.
==============================================================================

; --- chaines detectees --------------------------
;  00010182 : 't(")'
;  00010455 : 'serial.device'
;  00010465 : 'parallel.device'
;  00010479 : 'printer.device'
;  0001048a : '[20l'
;  000104a3 : '4(0X'
;  000104ab : ',p$(j'
;  000104bc : 'p$(j'
;  000104ca : 'p$(j'

; ========== HUNK 0 (code, 1328 octets) ==========

  00010000  ori.b    #$4c, d0
  00010004  move.l   d1, d2
  00010006  lsl.l    #$2, d2
  00010008  move.l   $18(a0, d2.l), $4(a1)
  0001000e  clr.l    $8(a1)
  00010012  clr.l    $c(a1)
  00010016  move.l   $14(a0, d2.l), $10(a1)
  0001001c  moveq    #$18, d3
  0001001e  add.l    a1, d3
  00010020  lsr.l    #$2, d3
  00010022  move.l   d3, $14(a1)
  00010026  moveq    #$2c, d4
  00010028  add.l    a1, d4
  0001002a  lsr.l    #$2, d4
  0001002c  move.l   d4, $28(a1)
  00010030  moveq    #$40, d5
  00010032  add.l    a1, d5
  00010034  lsr.l    #$2, d5
  00010036  move.l   d5, $3c(a1)
  0001003a  move.l   #$c0, d6
  00010040  add.l    a1, d6
  00010042  lsr.l    #$2, d6
  00010044  move.l   d6, $bc(a1)
  00010048  clr.l    $13c(a1)
  0001004c  tst.l    $4(a1)
  00010050  bne.w    $10060
  00010054  lea.l    $450(a4), a3
  00010058  move.l   a3, d1
  0001005a  lsr.l    #$2, d1
  0001005c  bra.w    $1007e
  00010060  moveq    #$1, d1
  00010062  cmp.l    $4(a1), d1
  00010066  bne.w    $10076
  0001006a  lea.l    $460(a4), a3
  0001006e  move.l   a3, d1
  00010070  lsr.l    #$2, d1
  00010072  bra.w    $1007e
  00010076  lea.l    $474(a4), a3
  0001007a  move.l   a3, d1
  0001007c  lsr.l    #$2, d1
  0001007e  move.l   d1, $140(a1)
  00010082  moveq    #$ff, d2
  00010084  move.l   d2, $144(a1)
  00010088  lea.l    $484(a4), a3
  0001008c  move.l   a3, d3
  0001008e  lsr.l    #$2, d3
  00010090  move.l   d3, $148(a1)
  00010094  clr.l    $14c(a1)
  00010098  clr.l    $150(a1)
  0001009c  move.l   (a1), d4
  0001009e  lsl.l    #$2, d4
  000100a0  move.l   $1c(a0, d4.l), $154(a1)
  000100a6  moveq    #$0, d1
  000100a8  move.l   d1, $158(a1)
  000100ac  moveq    #$1e, d2
  000100ae  cmp.l    d2, d1
  000100b0  bgt.w    $100c6
  000100b4  add.l    $3c(a1), d1
  000100b8  lsl.l    #$2, d1
  000100ba  clr.l    (a0, d1.l)
  000100be  moveq    #$1, d1
  000100c0  add.l    $158(a1), d1
  000100c4  bra.b    $100a8
  000100c6  moveq    #$0, d4
  000100c8  move.l   d4, d3
  000100ca  move.l   $140(a1), d2
  000100ce  move.l   $3c(a1), d1
  000100d2  move.l   #$164, d0
  000100d8  movea.l  $7c(a2), a4
  000100dc  jsr      (a5)
  000100de  tst.l    d1
  000100e0  bne.w    $100ea
  000100e4  moveq    #$ff, d1
  000100e6  move.l   d1, $13c(a1)
  000100ea  tst.l    $13c(a1)
  000100ee  beq.w    $1010a
  000100f2  move.l   #$ca, d3
  000100f8  moveq    #$0, d2
  000100fa  move.l   (a1), d1
  000100fc  move.l   #$164, d0
  00010102  movea.l  $c4(a2), a4
  00010106  jsr      (a5)
  00010108  jmp      (a6)
  0001010a  moveq    #$0, d1
  0001010c  move.l   d1, $158(a1)
  00010110  moveq    #$1e, d2
  00010112  cmp.l    d2, d1
  00010114  bgt.w    $10136
  00010118  add.l    $3c(a1), d1
  0001011c  lsl.l    #$2, d1
  0001011e  move.l   $bc(a1), d3
  00010122  add.l    $158(a1), d3
  00010126  lsl.l    #$2, d3
  00010128  move.l   (a0, d1.l), (a0, d3.l)
  0001012e  moveq    #$1, d1
  00010130  add.l    $158(a1), d1
  00010134  bra.b    $1010c
  00010136  moveq    #$2, d1
  00010138  cmp.l    $4(a1), d1
  0001013c  bne.w    $101a4
  00010140  move.l   $10(a1), d2
  00010144  lsl.l    #$2, d2
  00010146  moveq    #$0, d3
  00010148  move.b   (a0, d2.l), d3
  0001014c  moveq    #$4, d4
  0001014e  cmp.l    d4, d3
  00010150  ble.w    $101a4
  00010154  move.l   $148(a1), d3
  00010158  lsl.l    #$2, d3
  0001015a  moveq    #$0, d5
  0001015c  move.b   (a0, d3.l), d5
  00010160  move.l   d5, d4
  00010162  move.l   $16c(a1), d3
  00010166  moveq    #$3, d2
  00010168  move.l   $bc(a1), d1
  0001016c  move.l   #$164, d0
  00010172  movea.l  $18(a2), a4
  00010176  jsr      (a5)
  00010178  move.l   $148(a1), d1
  0001017c  lsl.l    #$2, d1
  0001017e  addq.l   #$1, d1
  00010180  move.l   d1, d3
  00010182  moveq    #$28, d2
  00010184  move.l   $bc(a1), d1
  00010188  move.l   #$164, d0
  0001018e  movea.l  $1bc(a2), a4
  00010192  jsr      (a5)
  00010194  move.l   $bc(a1), d1
  00010198  move.l   #$164, d0
  0001019e  movea.l  $54(a2), a4
  000101a2  jsr      (a5)
  000101a4  move.l   $28(a1), d1
  000101a8  lsl.l    #$2, d1
  000101aa  move.l   #$3ea, $8(a0, d1.l)
  000101b2  move.l   $14(a1), d1
  000101b6  lsl.l    #$2, d1
  000101b8  move.l   #$3e9, $8(a0, d1.l)
  000101c0  move.l   #$164, d0
  000101c6  movea.l  $38(a2), a4
  000101ca  jsr      (a5)
  000101cc  move.l   $154(a1), d2
  000101d0  lsl.l    #$2, d2
  000101d2  move.l   d1, $8(a0, d2.l)
  000101d6  moveq    #$ff, d2
  000101d8  move.l   (a1), d1
  000101da  move.l   #$164, d0
  000101e0  movea.l  $c4(a2), a4
  000101e4  jsr      (a5)
  000101e6  move.l   #$164, d0
  000101ec  movea.l  $a4(a2), a4
  000101f0  jsr      (a5)
  000101f2  move.l   d1, $158(a1)
  000101f6  bra.w    $103d2
  000101fa  move.l   $158(a1), d1
  000101fe  lsl.l    #$2, d1
  00010200  move.l   $14(a0, d1.l), $15c(a1)
  00010206  tst.l    $14c(a1)
  0001020a  beq.w    $1022a
  0001020e  move.l   #$ca, d3
  00010214  moveq    #$0, d2
  00010216  move.l   $158(a1), d1
  0001021a  move.l   #$16c, d0
  00010220  movea.l  $c4(a2), a4
  00010224  jsr      (a5)
  00010226  bra.w    $10420
  0001022a  moveq    #$ff, d1
  0001022c  move.l   d1, $14c(a1)
  00010230  move.l   $15c(a1), d2
  00010234  lsl.l    #$2, d2
  00010236  move.l   d1, $4(a0, d2.l)
  0001023a  move.l   $15c(a1), d2
  0001023e  lsl.l    #$2, d2
  00010240  move.l   #$3ed, $24(a0, d2.l)
  00010248  move.l   d1, d2
  0001024a  move.l   $158(a1), d1
  0001024e  move.l   #$16c, d0
  00010254  movea.l  $c4(a2), a4
  00010258  jsr      (a5)
  0001025a  bra.w    $10420
  0001025e  move.l   $158(a1), d1
  00010262  lsl.l    #$2, d1
  00010264  move.l   $14(a0, d1.l), $15c(a1)
  0001026a  tst.l    $150(a1)
  0001026e  beq.w    $1028e
  00010272  move.l   #$ca, d3
  00010278  moveq    #$0, d2
  0001027a  move.l   $158(a1), d1
  0001027e  move.l   #$16c, d0
  00010284  movea.l  $c4(a2), a4
  00010288  jsr      (a5)
  0001028a  bra.w    $10420
  0001028e  moveq    #$ff, d1
  00010290  move.l   d1, $150(a1)
  00010294  move.l   $15c(a1), d2
  00010298  lsl.l    #$2, d2
  0001029a  move.l   d1, $4(a0, d2.l)
  0001029e  move.l   $15c(a1), d2
  000102a2  lsl.l    #$2, d2
  000102a4  move.l   #$3ee, $24(a0, d2.l)
  000102ac  move.l   d1, d2
  000102ae  move.l   $158(a1), d1
  000102b2  move.l   #$16c, d0
  000102b8  movea.l  $c4(a2), a4
  000102bc  jsr      (a5)
  000102be  bra.w    $10420
  000102c2  move.l   $158(a1), d1
  000102c6  lsl.l    #$2, d1
  000102c8  cmpi.l   #$3ed, $14(a0, d1.l)
  000102d0  bne.w    $102dc
  000102d4  clr.l    $14c(a1)
  000102d8  bra.w    $102e0
  000102dc  clr.l    $150(a1)
  000102e0  tst.l    $14c(a1)
  000102e4  bne.w    $102fa
  000102e8  tst.l    $150(a1)
  000102ec  bne.w    $102fa
  000102f0  move.l   $154(a1), d1
  000102f4  lsl.l    #$2, d1
  000102f6  clr.l    $8(a0, d1.l)
  000102fa  moveq    #$ff, d2
  000102fc  move.l   $158(a1), d1
  00010300  move.l   #$168, d0
  00010306  movea.l  $c4(a2), a4
  0001030a  jsr      (a5)
  0001030c  bra.w    $10420
  00010310  move.l   $158(a1), $14(a1)
  00010316  move.l   $8(a1), d2
  0001031a  move.l   $3c(a1), d1
  0001031e  move.l   #$168, d0
  00010324  lea.l    $4d0(a4), a4
  00010328  jsr      (a5)
  0001032a  bra.w    $10420
  0001032e  move.l   $158(a1), $28(a1)
  00010334  move.l   $c(a1), d2
  00010338  move.l   $bc(a1), d1
  0001033c  move.l   #$168, d0
  00010342  lea.l    $4d0(a4), a4
  00010346  jsr      (a5)
  00010348  bra.w    $10420
  0001034c  move.l   $158(a1), $8(a1)
  00010352  move.l   $14(a1), d4
  00010356  move.l   $158(a1), d3
  0001035a  moveq    #$2, d2
  0001035c  move.l   $3c(a1), d1
  00010360  move.l   #$168, d0
  00010366  lea.l    $48c(a4), a4
  0001036a  jsr      (a5)
  0001036c  clr.l    $14(a1)
  00010370  bra.w    $10420
  00010374  move.l   $158(a1), $c(a1)
  0001037a  move.l   $28(a1), d4
  0001037e  move.l   $158(a1), d3
  00010382  moveq    #$3, d2
  00010384  move.l   $bc(a1), d1
  00010388  move.l   #$168, d0
  0001038e  lea.l    $48c(a4), a4
  00010392  jsr      (a5)
  00010394  clr.l    $28(a1)
  00010398  bra.w    $10420
  0001039c  tst.l    $14c(a1)
  000103a0  bne.w    $103b6
  000103a4  tst.l    $150(a1)
  000103a8  bne.w    $103b6
  000103ac  move.l   $154(a1), d1
  000103b0  lsl.l    #$2, d1
  000103b2  clr.l    $8(a0, d1.l)
  000103b6  move.l   #$d1, d3
  000103bc  moveq    #$0, d2
  000103be  move.l   $158(a1), d1
  000103c2  move.l   #$168, d0
  000103c8  movea.l  $c4(a2), a4
  000103cc  jsr      (a5)
  000103ce  bra.w    $10420
  000103d2  move.l   $158(a1), d1
  000103d6  lsl.l    #$2, d1
  000103d8  move.l   $8(a0, d1.l), d1
  000103dc  moveq    #$52, d2
  000103de  cmp.l    d2, d1
  000103e0  beq.w    $1034c
  000103e4  moveq    #$57, d3
  000103e6  cmp.l    d3, d1
  000103e8  beq.b    $10374
  000103ea  cmpi.l   #$3e9, d1
  000103f0  beq.w    $10310
  000103f4  cmpi.l   #$3ea, d1
  000103fa  beq.w    $1032e
  000103fe  cmpi.l   #$3ed, d1
  00010404  beq.w    $101fa
  00010408  cmpi.l   #$3ee, d1
  0001040e  beq.w    $1025e
  00010412  cmpi.l   #$3ef, d1
  00010418  beq.w    $102c2
  0001041c  bra.w    $1039c
  00010420  tst.l    $14c(a1)
  00010424  bne.w    $101e6
  00010428  tst.l    $150(a1)
  0001042c  bne.w    $101e6
  00010430  tst.l    $28(a1)
  00010434  beq.w    $101e6
  00010438  tst.l    $14(a1)
  0001043c  beq.w    $101e6
  00010440  move.l   $3c(a1), d1
  00010444  move.l   #$164, d0
  0001044a  movea.l  $80(a2), a4
  0001044e  jsr      (a5)
  00010450  jmp      (a6)
  00010452  nop      
  * 00010454  dc.w     0x0e73
  00010456  bcs.b    $104ca
  00010458  bvs.b    $104bb
  0001045a  bge.b    $1048a
  0001045c  bcc.b    $104c3
  0001045e  moveq    #$69, d3
  00010460  bls.b    $104c7
  00010462  ori.b    #$70, d0
  00010466  bsr.b    $104da
  00010468  bsr.b    $104d6
  0001046a  bge.b    $104d1
  0001046c  bge.b    $1049c
  0001046e  bcc.b    $104d5
  00010470  moveq    #$69, d3
  00010472  bls.b    $104d9
  00010474  ori.b    #$0, d0
  00010478  bchg.b   d7, $69(a0, d7.w)
  0001047c  bgt.b    $104f2
  0001047e  bcs.b    $104f2
  00010480  movea.l  -(a4), a7
  00010482  bcs.b    $104fa
  00010484  bvs.b    $104e9
  00010486  bcs.w    $10aa3
  0001048a  subq.b   #$5, $6c(a2, d3.w)
  0001048e  ori.b    #$3, d0
  00010492  lsl.l    #$2, d5
  00010494  move.l   $18(a0, d5.l), $10(a1)
  0001049a  move.l   $1c(a0, d5.l), $14(a1)
  000104a0  clr.l    $34(a1)
  000104a4  move.l   $1c(a0, d5.l), d4
  000104a8  move.l   $2c(a1), d3
  000104ac  moveq    #$24, d0
  000104ae  movea.l  $18(a2), a4
  000104b2  jsr      (a5)
  000104b4  move.l   $10(a1), d3
  000104b8  moveq    #$28, d2
  000104ba  move.l   (a1), d1
  000104bc  moveq    #$24, d0
  000104be  movea.l  $1bc(a2), a4
  000104c2  jsr      (a5)
  000104c4  move.l   $c(a1), d2
  000104c8  move.l   (a1), d1
  000104ca  moveq    #$24, d0
  000104cc  movea.l  $58(a2), a4
  000104d0  jsr      (a5)
  000104d2  jmp      (a6)
  000104d4  move.l   d1, d3
  000104d6  lsl.l    #$2, d3
  000104d8  moveq    #$0, d4
  000104da  move.b   $1f(a0, d3.l), d4
  000104de  move.l   d4, $8(a1)
  000104e2  moveq    #$20, d2
  000104e4  moveq    #$18, d0
  000104e6  movea.l  $1b8(a2), a4
  000104ea  jsr      (a5)
  000104ec  move.l   d1, $c(a1)
  000104f0  tst.l    $8(a1)
  000104f4  bne.w    $1050a
  000104f8  move.l   d1, d2
  000104fa  move.l   $4(a1), d1
  000104fe  moveq    #$1c, d0
  00010500  movea.l  $c4(a2), a4
  00010504  jsr      (a5)
  00010506  bra.w    $1051c
  0001050a  move.l   $8(a1), d3
  0001050e  moveq    #$ff, d2
  00010510  move.l   $4(a1), d1
  00010514  moveq    #$1c, d0
  00010516  movea.l  $c4(a2), a4
  0001051a  jsr      (a5)
  0001051c  jmp      (a6)
  0001051e  nop      
  00010520  ori.b    #$0, d0
  00010524  ori.b    #$1, d0
  00010528  ori.b    #$4, d0
  0001052c  ori.b    #$6f, d0
