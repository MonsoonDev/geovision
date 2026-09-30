clear
view 2d
title Circumcircle
point A 0 0 label=A
point B 4 0 label=B
point C 1 3 label=C
polygon tri A B C
step-name 0 Given
step-name 1 Circumcircle
circumcircle c A B C
circumcenter O A B C label=O
segment OA O A
segment OB O B
segment OC O C
angle alpha B A C label=α
step 1 c O OA OB OC alpha
highlight c
