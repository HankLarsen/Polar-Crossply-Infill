;TYPE:Custom
; Filament-specific end gcode
G1 Z19.4 F720 ; Move print head up
M104 S0 ; turn off temperature
M140 S0 ; turn off heatbed
M141 S0 ; disable chamber control
M107 ; turn off fan
G1 X242 Y211 F10200 ; park
G4 ; wait
M572 S0 ; reset PA
M486 S-1
M84 X Y E ; disable motors
M73 P100 R0
