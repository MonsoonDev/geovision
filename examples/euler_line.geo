clear
view 2d
title The Euler line
bounds 0.9 -0.55 9.1 7.65

point A 2 2 label=A color=#1d4ed8
point B 8 2 label=B color=#1d4ed8
point C 3.2 6.4 label=C color=#1d4ed8
polygon tri A B C color=#1d4ed8 fill=#1d4ed81f width=2.4
step-name 0 The triangle

circumcircle circ A B C color=#1d4ed8 fill=none width=1.6
circumcenter O A B C color=#1d4ed8
label labO 5.15 4.35 O color=#1d4ed8
step 1 circ O labO
step-name 1 Circumcircle

line sideBC B C opacity=0
line sideCA C A opacity=0
line sideAB A B opacity=0
perpendicular thruA A sideBC opacity=0
perpendicular thruB B sideCA opacity=0
perpendicular thruC C sideAB opacity=0
project Ha A sideBC color=#c2410c
project Hb B sideCA color=#c2410c
project Hc C sideAB color=#c2410c
segment altA A Ha color=#a8a29e dash=true width=1.25
segment altB B Hb color=#a8a29e dash=true width=1.25
segment altC C Hc color=#a8a29e dash=true width=1.25
orthocenter H A B C color=#c2410c
label labH 2.78 3.7 H color=#c2410c
step 2 Ha Hb Hc altA altB altC H labH
step-name 2 Orthocenter

centroid G A B C color=#7c3aed
label labG 4.25 4.4 G color=#7c3aed
line euler O H color=#c2410c width=2.6 highlight=true
step 3 G labG euler
step-name 3 The Euler line

midpoint Ma B C color=#0f766e
midpoint Mb C A color=#0f766e
midpoint Mc A B color=#0f766e
midpoint Ea A H color=#0f766e
midpoint Eb B H color=#0f766e
midpoint Ec C H color=#0f766e
circumcircle nine Ma Mb Mc color=#0f766e fill=none width=2.4
midpoint N O H color=#0f766e
label labN 4.15 2.68 N color=#0f766e
step 4 Ma Mb Mc Ea Eb Ec nine N labN
step-name 4 Nine-point circle
