; ---- Prusa Core One / 0.6 mm nozzle / PLA ----
; Extracted from a known-good PrusaSlicer 2.9.4 export (firmware 6.4.0+11974).
; Values are already resolved (no PrusaSlicer template braces).
; M555/M486 recomputed for a SINGLE part centred at X125 Y110, OD 66.2 mm.
M73 P0 R60
M201 X10000 Y10000 Z400 E5000 ; sets maximum accelerations, mm/sec^2
M203 X350 Y350 Z12 E100 ; sets maximum feedrates, mm/sec
M204 P7000 R2500 T7000 ; sets acceleration (P, T) and retract acceleration (R), mm/sec^2
M205 X10.00 Y10.00 Z2.00 E10.00 ; sets the jerk limits, mm/sec
M205 S0 T0 ; sets the minimum extruding and travel feed rate, mm/sec

M486 S0
M486 Apolar_crossply_rotor
M486 S-1

;TYPE:Custom
M17 ; enable steppers
M862.1 P0.6 A0 F0 ; nozzle check
M862.3 P "COREONE" ; printer model check
M862.5 P2 ; g-code level check
M862.6 P"Input shaper" ; FW feature check
M115 U6.4.0+11974

M555 X91.9 Y72.9 W66.2 H70.2

G90 ; use absolute coordinates
M83 ; extruder relative mode

M140 S55 ; set bed temp
M109 R170 ; wait for temp

M84 E ; turn off E motor

G28 ; home all without mesh bed level

M141 S20 ; set nominal chamber temp

M106 S70
G0 Z40 F10000
M104 T0 S170
M190 R55 ; wait for bed temp
M107

G29 G ; absorb heat

M109 R170 ; wait for MBL temp

M302 S155 ; lower cold extrusion limit to 155C

G1 E-2 F2400 ; retraction

M84 E ; turn off E motor

G29 P9 X208 Y-2.5 W32 H4

;
; MBL
;
M84 E ; turn off E motor
G29 P1 ; invalidate mbl & probe print area
G29 P1 X150 Y0 W100 H20 C ; probe near purge place
G29 P3.2 ; interpolate mbl probes
G29 P3.13 ; extrapolate mbl outside probe area
G29 A ; activate mbl

; prepare for purge
M104 S220
G0 X249 Y-2.5 Z15 F4800 ; move away and ready for the purge
M109 S220

G92 E0
M569 S0 E ; set spreadcycle mode for extruder

M591 S0 ; disable stuck detection

;
; Extrude purge line
;
G92 E0 ; reset extruder position
G1 E2 F2400 ; deretraction after the initial one
G0 E5 X235 Z0.2 F500 ; purge
G0 X225 E4 F500 ; purge
G0 X215 E4 F650 ; purge
G0 X205 E4 F800 ; purge
G0 X202 Z0.05 F8000 ; wipe, move close to the bed
G0 X199 Z0.2 F8000 ; wipe, move quickly away from the bed

M591 R ; restore stuck detection

G92 E0
M221 S100 ; set flow to 100%
G21 ; set units to millimeters
G90 ; use absolute coordinates
M83 ; use relative distances for extrusion

M572 S0.022 ; Pressure advance

M142 S36 ; set heatbreak target temp
M107 ; fan off for first layer
