clear
view 3d
title Cut pyramid
camera pos=12,-14,8 target=0,0,1.4

point A 2 2 0 label=A
point B 2 -2 0 label=B
point C -2 -2 0 label=C
point D -2 2 0 label=D
point S 0 0 3 label=S
polygon base A B C D
segment SA S A
segment SB S B
segment SC S C
segment SD S D
step-name 0 The pyramid

midpoint Ma S A label=Ma step=1
midpoint Mb S B label=Mb step=1
midpoint Mc S C label=Mc step=1
midpoint Md S D label=Md step=1
polygon cut Ma Mb Mc Md fill=none color=#c2410c step=1
step-name 1 Cut parallel to the base

pyramid cap Ma Mb Mc Md S color=#c2410c step=2
step-name 2 A smaller pyramid is removed

polygon fAB A B Mb Ma step=3
polygon fBC B C Mc Mb step=3
polygon fCD C D Md Mc step=3
polygon fDA D A Ma Md step=3
highlight fAB fBC fCD fDA
step-name 3 The frustum remains
